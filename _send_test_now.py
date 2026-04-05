"""
2분 뒤 일일 스캔 알림 + 주간 리포트 둘 다 전송
"""
import time
from datetime import datetime

print(f"[{datetime.now().strftime('%H:%M:%S')}] 2분 후 전송 시작...")
time.sleep(120)

print(f"[{datetime.now().strftime('%H:%M:%S')}] 전송 중...")

# 1. 일일 스캔 알림 (오늘 캐시된 결과 사용)
try:
    from cache_db import load_scan
    from telegram_alert import send_scan_alert
    results = load_scan()
    if results:
        send_scan_alert(results)
        print(f"  ✅ 일일 스캔 알림 전송 완료 ({len(results)}종목)")
    else:
        from telegram_alert import send_telegram
        send_telegram("📭 오늘 스캔 결과가 없습니다. (캐시 없음)")
        print("  ⚠️ 스캔 결과 없음 - 빈 알림 전송")
except Exception as e:
    print(f"  ❌ 일일 알림 오류: {e}")

time.sleep(3)

# 2. 주간 리포트
try:
    from telegram_alert import send_weekly_summary
    send_weekly_summary(force=True)
    print(f"  ✅ 주간 리포트 전송 완료")
except Exception as e:
    print(f"  ❌ 주간 리포트 오류: {e}")

print(f"[{datetime.now().strftime('%H:%M:%S')}] 완료")
