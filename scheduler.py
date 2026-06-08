"""
독립 스케줄러 - 앱과 별도 프로세스로 실행
주식: 평일 15:40 스캔 + 텔레그램 알림 (KST)
코인: 4시간 간격 스캔 (UTC 0,4,8,12,16,20시)
"""
import time
import os
import sys
from datetime import datetime, date, timezone, timedelta

KST = timezone(timedelta(hours=9))
UTC = timezone.utc

CRYPTO_SCAN_HOURS_UTC = {0, 4, 8, 12, 16, 20}

# 작업 디렉토리 설정
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def log(msg):
    now_kst = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')
    print(f"[{now_kst}] {msg}", flush=True)

def run_scan():
    log("스캔 시작...")
    try:
        from stock_surge_detector import KoreanStockSurgeDetector
        from cache_db import save_scan, update_alert_status
        from telegram_alert import send_scan_alert, send_telegram
        import pandas as _pd

        scan_mode = os.environ.get("SCAN_MODE", "").lower()
        if not scan_mode:
            # 환경변수 없으면 DB에서 읽기 (웹 UI에서 설정한 값)
            try:
                from cache_db import load_app_setting
                scan_mode = load_app_setting("scan_mode", "rcycle")
            except:
                scan_mode = "rcycle"
        log(f"스캔 전략: {scan_mode}")

        det = KoreanStockSurgeDetector(max_gap_pct=7, min_below_days=60, max_cross_days=90)
        det._ob_days = 90  # R-cycle 70이탈 후 최대 경과일
        det._rc_below = 0  # 장기선 아래 진행 기간 제한 없음

        if scan_mode == "classic":
            results = det.analyze_all_stocks_classic()
        elif scan_mode == "both":
            r1 = det.analyze_all_stocks()
            r2 = det.analyze_all_stocks_classic()
            # 중복 제거 (symbol 기준), 점수 높은 것 우선
            seen = {}
            for r in r1 + r2:
                sym = r["symbol"]
                if sym not in seen or r["total_score"] > seen[sym]["total_score"]:
                    seen[sym] = r
            results = list(seen.values())
        elif scan_mode == "divergence":
            results = det.analyze_all_stocks_divergence()
        else:  # rcycle (기본)
            results = det.analyze_all_stocks()

        results = [r for r in results if r.get("total_score", 0) >= 40]
        results = sorted(results, key=lambda x: x["total_score"], reverse=True)

        # Series 직렬화 후 DB 저장
        def _serialize(r):
            out = {}
            for k, v in r.items():
                if isinstance(v, _pd.Series):
                    out[k] = v.tolist()
                elif hasattr(v, 'tolist'):
                    out[k] = v.tolist()
                else:
                    out[k] = v
            return out
        save_scan([_serialize(r) for r in results])

        if results:
            send_scan_alert(results, send_charts=True)
            log(f"완료: {len(results)}개 종목 → 텔레그램 전송")
        else:
            import yfinance as yf
            from datetime import date
            try:
                kospi = yf.Ticker("^KS11").history(period="1y").dropna(subset=["Close"])
                kospi_cur  = float(kospi["Close"].iloc[-1])
                kospi_prev = float(kospi["Close"].iloc[-2])
                kospi_chg  = (kospi_cur - kospi_prev) / kospi_prev * 100
                market_msg = f"📊 KOSPI {kospi_cur:,.0f} ({kospi_chg:+.2f}%)"
            except:
                market_msg = "📊 KOSPI 데이터 없음"
            send_telegram(
                f"📊 <b>{date.today()} 장마감 스캔 결과</b>\n"
                f"{'━'*20}\n\n"
                f"오늘 급등 예고 종목 없음\n\n"
                f"{market_msg}\n"
                f"💡 조건 충족 종목이 없습니다."
            )
            log("조건 충족 종목 없음 → 알림 전송")

        # 성과 추적 업데이트
        update_alert_status()
        log("성과 추적 업데이트 완료")

    except Exception as e:
        log(f"오류: {e}")
        import traceback
        traceback.print_exc()

def run_db_backup():
    """매일 새벽 2시 DB 백업 (7일치 보관) + DB 정리 + 개인 알림"""
    if not os.path.isdir("/data"):
        return
    try:
        import shutil
        from datetime import datetime as _dt
        backup_dir = "/data/backup"
        os.makedirs(backup_dir, exist_ok=True)
        today_str = _dt.now(KST).strftime("%Y%m%d")
        src = "/data/scan_cache.db"
        dst = f"{backup_dir}/scan_cache_{today_str}.db"

        # ── DB 정리 (백업 전 실행) ────────────────────────────────
        cleaned_msg = ""
        try:
            import sqlite3
            # WAL + timeout으로 잠금 충돌 방지
            conn = sqlite3.connect(src, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            # 1. scan_results: 30일 이상 된 것 삭제
            cutoff_scan = (_dt.now(KST).date() - __import__('datetime').timedelta(days=30)).isoformat()
            r1 = conn.execute("DELETE FROM scan_results WHERE scan_date < ?", (cutoff_scan,))
            # 2. alert_history: 종료된 것 중 90일 이상 된 것 삭제 (성과 통계 보존)
            cutoff_alert = (_dt.now(KST).date() - __import__('datetime').timedelta(days=90)).isoformat()
            r2 = conn.execute("""
                DELETE FROM alert_history
                WHERE status IN ('hit_target','hit_stop','expired','cancelled')
                  AND alert_date < ?
            """, (cutoff_alert,))
            # 3. trade_orders: 종료된 것 중 90일 이상 된 것 삭제
            r3 = conn.execute("""
                DELETE FROM trade_orders
                WHERE status IN ('hit_target','hit_stop','expired','cancelled')
                  AND alert_date < ?
            """, (cutoff_alert,))
            conn.commit()
            conn.close()
            cleaned_msg = (
                f"\n🧹 DB 정리: scan_results -{r1.rowcount}건 "
                f"/ alert_history -{r2.rowcount}건 "
                f"/ trade_orders -{r3.rowcount}건"
            )
            log(f"[백업] DB 정리 완료{cleaned_msg}")
        except Exception as ce:
            log(f"[백업] DB 정리 오류: {ce}")

        if os.path.exists(src):
            shutil.copy2(src, dst)
            # VACUUM은 원본 대신 백업 파일에만 적용 (원본 잠금 방지)
            try:
                import sqlite3 as _sq
                _vc = _sq.connect(dst, timeout=60)
                _vc.execute("VACUUM")
                _vc.close()
                log(f"[백업] 백업 파일 VACUUM 완료")
            except Exception as _ve:
                log(f"[백업] VACUUM 오류(무시): {_ve}")
            size_mb = os.path.getsize(dst) / 1024 / 1024
            log(f"[백업] DB 백업 완료: {dst} ({size_mb:.1f}MB)")
            try:
                from auto_trader import _send_admin
                _send_admin(
                    f"✅ <b>DB 백업 완료</b>\n"
                    f"파일: scan_cache_{today_str}.db\n"
                    f"크기: {size_mb:.1f}MB\n"
                    f"시각: {_dt.now(KST).strftime('%Y-%m-%d %H:%M KST')}"
                    + cleaned_msg
                )
            except Exception:
                pass

        # 7일 이상 된 백업 삭제
        for fname in os.listdir(backup_dir):
            fpath = os.path.join(backup_dir, fname)
            import time as _time
            if _time.time() - os.path.getmtime(fpath) > 86400 * 7:
                os.remove(fpath)
                log(f"[백업] 오래된 백업 삭제: {fname}")
    except Exception as e:
        log(f"[백업] 오류: {e}")
        try:
            from auto_trader import _send_admin
            _send_admin(f"⚠️ <b>DB 백업 실패</b>\n오류: {e}")
        except Exception:
            pass


def run_performance():
    log("주간 리포트 전송 시작...")
    try:
        from cache_db import update_alert_status
        from telegram_alert import send_weekly_summary
        update_alert_status()
        log("성과 추적 업데이트 완료")
        send_weekly_summary(force=True)
        log("주간 리포트 전송 완료")
    except Exception as e:
        log(f"주간 리포트 오류: {e}")


def run_crypto_scan():
    log("[코인] 스캔 비활성화 - 알림 생략")
    return

def main():
    log("스케줄러 시작 (주식: 평일 15:40 / 코인: 4시간 간격 / 리포트: 09:10) - KST 기준")

    _state_file = "/data/.scheduler_state" if os.path.isdir("/data") else ".scheduler_state"

    def _load_state():
        try:
            with open(_state_file) as f:
                import json
                return json.load(f)
        except:
            return {}

    def _save_state(state):
        try:
            import json
            with open(_state_file, "w") as f:
                json.dump(state, f)
        except:
            pass

    state = _load_state()
    last_scan_date   = state.get("last_scan_date")
    last_perf_date   = state.get("last_perf_date")
    last_crypto_hour = state.get("last_crypto_hour", -1)
    last_reorder_date = state.get("last_reorder_date")
    last_backup_date = state.get("last_backup_date")
    last_us_scan_date = state.get("last_us_scan_date")

    while True:
        now_kst = datetime.now(KST)
        now_utc = datetime.now(UTC)
        today   = now_kst.date().isoformat()
        # 평일 + 공휴일 아닌 날만 거래일로 처리
        try:
            from auto_trader import is_trading_day
            is_weekday = is_trading_day()
        except Exception:
            is_weekday = now_kst.weekday() < 5

        # 02:00 KST DB 백업 (매일)
        if now_kst.hour == 2 and now_kst.minute >= 0 and now_kst.minute < 5 and last_backup_date != today:
            last_backup_date = today
            _save_state({"last_scan_date": last_scan_date, "last_perf_date": last_perf_date,
                         "last_crypto_hour": last_crypto_hour, "last_reorder_date": last_reorder_date,
                         "last_backup_date": last_backup_date})
            run_db_backup()

        # 09:05 KST 자동매매 주문 - 비활성화
        # if is_weekday and now_kst.hour == 9 and now_kst.minute >= 5 and last_reorder_date != today:
        #     (자동매매 비활성화)

        # 09:10 KST 채널 주간 리포트만 전송 (자동매매 리포트 비활성화)
        if is_weekday and now_kst.hour == 9 and now_kst.minute >= 10 and last_perf_date != today:
            last_perf_date = today
            _save_state({"last_scan_date": last_scan_date, "last_perf_date": last_perf_date,
                         "last_crypto_hour": last_crypto_hour, "last_reorder_date": last_reorder_date})
            run_performance()
            # 자동매매 잔고검증/리포트 비활성화
            # try:
            #     from auto_trader import verify_positions, send_trade_report, get_active_modes
            #     ...
            # except Exception as e:
            #     log(f"[자동매매] 리포트 초기화 오류: {e}")

        # 장중 모니터링 비활성화
        # if is_weekday:
        #     ...monitor_positions...

        # 멀티유저 장중 모니터링 비활성화
        # if is_weekday:
        #     ...run_all_users_monitor...

        # 봇 커맨드 폴링 비활성화
        # try:
        #     from auto_trader_multi import poll_bot_commands
        #     poll_bot_commands()
        # except Exception as e:
        #     log(f"[멀티유저] 봇 폴링 오류: {e}")

        # 15:40 KST 주식 스캔
        if is_weekday and now_kst.hour == 15 and now_kst.minute >= 40 and last_scan_date != today:
            last_scan_date = today
            _save_state({"last_scan_date": last_scan_date, "last_perf_date": last_perf_date,
                         "last_crypto_hour": last_crypto_hour, "last_reorder_date": last_reorder_date})
            run_scan()

        # 06:30 KST 미국 주식 스캔 (일시 비활성화)
        # us_scan_hour = now_kst.hour == 6 and now_kst.minute >= 30
        # us_scan_hour_alt = now_kst.hour == 7 and now_kst.minute >= 30
        # if is_weekday and (us_scan_hour or us_scan_hour_alt) and last_us_scan_date != today:
        #     ... (미국 주식 스캔 비활성화)        # 4시간 간격 코인 스캔 비활성화
        # utc_hour = now_utc.hour
        # if utc_hour in CRYPTO_SCAN_HOURS_UTC and utc_hour != last_crypto_hour:
        #     last_crypto_hour = utc_hour
        #     _save_state(...)
        #     run_crypto_scan()

        time.sleep(30)

        # 7번: 스케줄러 heartbeat 기록 비활성화
        # try:
        #     from auto_trader import scheduler_heartbeat
        #     scheduler_heartbeat()
        # except Exception:
        #     pass

if __name__ == "__main__":
    main()
