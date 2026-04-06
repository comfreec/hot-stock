"""
주간 리포트 테스트 전송 (2분 뒤)
"""
import time
from datetime import datetime

print(f"[{datetime.now().strftime('%H:%M:%S')}] 2분 후 전송 시작...")
time.sleep(120)

print(f"[{datetime.now().strftime('%H:%M:%S')}] 전송 중...")

try:
    from cache_db import update_alert_status
    update_alert_status()
    print("  ✅ 상태 업데이트 완료")
except Exception as e:
    print(f"  ❌ 상태 업데이트 오류: {e}")

try:
    from telegram_alert import send_weekly_summary
    send_weekly_summary(force=True)
    print(f"  ✅ 주간 리포트 전송 완료")
except Exception as e:
    print(f"  ❌ 주간 리포트 오류: {e}")

print(f"[{datetime.now().strftime('%H:%M:%S')}] 완료")
