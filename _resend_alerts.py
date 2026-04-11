"""오늘 스캔 결과 + 주간 리포트 재전송"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from cache_db import load_scan
from telegram_alert import send_scan_alert, send_weekly_summary

# 오늘 스캔 결과 재전송 (15:40 알림)
results = load_scan()
print(f"스캔 결과: {len(results)}개")
if results:
    send_scan_alert(results, send_charts=True)
    print("스캔 알림 전송 완료")
else:
    print("오늘 스캔 결과 없음")

# 주간 리포트 재전송 (09:10 알림)
send_weekly_summary(force=True)
print("주간 리포트 전송 완료")
