"""
일일 알림 + 주간 리포트 테스트 전송
"""
from datetime import datetime
import sys

mode = sys.argv[1] if len(sys.argv) > 1 else "both"
print(f"[{datetime.now().strftime('%H:%M:%S')}] 테스트 전송 중... (mode={mode})")

if mode in ("both", "daily"):
    try:
        from cache_db import load_scan
        from telegram_alert import send_scan_alert
        results = load_scan()
        if results:
            send_scan_alert(results, send_charts=True)
            print(f"  ✅ 일일 알림 전송 완료 ({len(results)}종목)")
        else:
            print("  ⚠️ 오늘 캐시된 스캔 결과 없음")
    except Exception as e:
        print(f"  ❌ 일일 알림 오류: {e}")
        import traceback; traceback.print_exc()

    import time; time.sleep(3)

if mode in ("both", "weekly"):
    try:
        from cache_db import update_alert_status
        update_alert_status()
        from telegram_alert import send_weekly_summary
        send_weekly_summary(force=True)
        print(f"  ✅ 주간 리포트 전송 완료")
    except Exception as e:
        print(f"  ❌ 주간 리포트 오류: {e}")

print(f"[{datetime.now().strftime('%H:%M:%S')}] 완료")
