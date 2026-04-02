"""
독립 스케줄러 - 앱과 별도 프로세스로 실행
평일 15:40 자동 스캔 + 텔레그램 알림
KST(UTC+9) 기준으로 동작
"""
import time
import os
import sys
from datetime import datetime, date, timezone, timedelta

KST = timezone(timedelta(hours=9))

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
    log("성과 업데이트 시작...")
    try:
        from telegram_alert import send_performance_update, send_weekly_summary
        send_performance_update()
        send_weekly_summary()
        log("성과 업데이트 완료")
    except Exception as e:
        log(f"성과 업데이트 오류: {e}")

def main():
    log("스케줄러 시작 (평일 15:40 스캔 / 09:10 성과 업데이트) - KST 기준")
    last_scan_date = None
    last_perf_date = None

    while True:
        now = datetime.now(KST)
        today = now.date()
        is_weekday = now.weekday() < 5  # 월~금

        # 09:10 성과 업데이트
        is_perf_time = now.hour == 9 and now.minute >= 10
        if is_weekday and is_perf_time and last_perf_date != today:
            last_perf_date = today
            run_performance()

        # 15:40 스캔 + 알림
        is_scan_time = now.hour == 15 and now.minute >= 40
        if is_weekday and is_scan_time and last_scan_date != today:
            last_scan_date = today
            run_scan()

        time.sleep(30)

if __name__ == "__main__":
    main()
