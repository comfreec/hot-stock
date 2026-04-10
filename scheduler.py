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

        det = KoreanStockSurgeDetector(max_gap_pct=10, min_below_days=120, max_cross_days=60)
        results = det.analyze_all_stocks()
        results = [r for r in results if r.get("total_score", 0) >= 15]
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
    # 코인 주간 리포트도 함께 전송
    try:
        from crypto_surge.telegram_alert import send_weekly_summary as crypto_weekly
        crypto_weekly(force=True)
        log("[코인] 주간 리포트 전송 완료")
    except Exception as e:
        log(f"[코인] 주간 리포트 오류: {e}")


def run_crypto_scan():
    log("[코인] 스캔 시작...")
    try:
        from crypto_surge.crypto_surge_detector import CryptoSurgeDetector
        from crypto_surge.cache_db import save_scan as crypto_save_scan, update_alert_status as crypto_update_status
        from crypto_surge.telegram_alert import send_scan_alert as crypto_send_alert, send_telegram as crypto_send_telegram

        det = CryptoSurgeDetector(max_gap_pct=10, min_below_days=120, max_cross_days=60)
        results = det.analyze_all_coins()
        results = [r for r in results if r.get("total_score", 0) >= 15]

        crypto_save_scan(results)

        if results:
            crypto_send_alert(results, send_charts=True)
            log(f"[코인] 완료: {len(results)}개 → 텔레그램 전송")
        else:
            log("[코인] 조건 충족 코인 없음 - 알림 생략")

        crypto_update_status()

    except Exception as e:
        log(f"[코인] 오류: {e}")
        import traceback
        traceback.print_exc()

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

    while True:
        now_kst = datetime.now(KST)
        now_utc = datetime.now(UTC)
        today   = now_kst.date().isoformat()
        is_weekday = now_kst.weekday() < 5

        # 09:10 KST 주간 리포트
        if is_weekday and now_kst.hour == 9 and now_kst.minute >= 10 and last_perf_date != today:
            last_perf_date = today
            _save_state({"last_scan_date": last_scan_date, "last_perf_date": last_perf_date, "last_crypto_hour": last_crypto_hour})
            run_performance()

        # 15:40 KST 주식 스캔
        if is_weekday and now_kst.hour == 15 and now_kst.minute >= 40 and last_scan_date != today:
            last_scan_date = today
            _save_state({"last_scan_date": last_scan_date, "last_perf_date": last_perf_date, "last_crypto_hour": last_crypto_hour})
            run_scan()

        # 4시간 간격 코인 스캔 (UTC 0,4,8,12,16,20시)
        utc_hour = now_utc.hour
        if utc_hour in CRYPTO_SCAN_HOURS_UTC and utc_hour != last_crypto_hour:
            last_crypto_hour = utc_hour
            _save_state({"last_scan_date": last_scan_date, "last_perf_date": last_perf_date, "last_crypto_hour": last_crypto_hour})
            run_crypto_scan()

        time.sleep(30)

if __name__ == "__main__":
    main()
