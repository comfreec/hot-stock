"""오늘 스캔 결과 재전송 (차트 포함)"""
import sys, os
sys.path.insert(0, '/app')
os.chdir('/app')

from cache_db import load_scan
from telegram_alert import send_scan_alert
from datetime import date

results = load_scan(date.today().isoformat())
if not results:
    print("오늘 스캔 결과 없음")
else:
    print(f"{len(results)}개 종목 재전송 시작...")
    send_scan_alert(results, send_charts=True)
    print("전송 완료")
