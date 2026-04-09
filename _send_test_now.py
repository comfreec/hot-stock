"""
오늘 캐시된 스캔 결과로 일일 알림 테스트 전송
"""
from datetime import datetime
print(f"[{datetime.now().strftime('%H:%M:%S')}] 알림 테스트 전송 중...")

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
    print(f"  ❌ 오류: {e}")
    import traceback; traceback.print_exc()

print(f"[{datetime.now().strftime('%H:%M:%S')}] 완료")
