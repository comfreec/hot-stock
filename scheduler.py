"""
독립 스케줄러 - 앱과 별도 프로세스로 실행
평일 15:40 자동 스캔 + 텔레그램 알림
"""
import time
import os
import sys
from datetime import datetime, date

# 작업 디렉토리 설정
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def run_scan():
    log("스캔 시작...")
    try:
        from stock_surge_detector import KoreanStockSurgeDetector
        from cache_db import save_scan
        from telegram_alert import send_scan_alert

        det = KoreanStockSurgeDetector(max_gap_pct=10, min_below_days=120, max_cross_days=60)
        results = det.analyze_all_stocks()

        if results:
            save_scan(results)
            send_scan_alert(results)
            log(f"완료: {len(results)}개 종목 → 텔레그램 전송")
        else:
            log("조건 충족 종목 없음")
    except Exception as e:
        log(f"오류: {e}")

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
    log("스케줄러 시작 (평일 15:40 스캔 / 09:10 성과 업데이트)")
    last_scan_date = None
    last_perf_date = None

    while True:
        now = datetime.now()
        today = date.today()
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
