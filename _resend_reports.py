"""
주간보고서 + 자동매매 리포트 수동 재전송
"""
import os, sys
os.chdir('/app')
sys.path.insert(0, '/app')
if os.path.isdir('/data'):
    os.environ['DB_PATH'] = '/data/scan_cache.db'

# 1. 채널 성과 주간보고서
print("[1] 채널 성과 업데이트 알림...")
try:
    from run_performance import send_performance_update
    send_performance_update()
    print("  완료")
except Exception as e:
    print(f"  오류: {e}")
    try:
        from telegram_alert import send_performance_update
        send_performance_update()
        print("  완료 (telegram_alert)")
    except Exception as e2:
        print(f"  오류2: {e2}")

# 2. 자동매매 리포트 (개인 DM)
print("[2] 자동매매 리포트...")
try:
    from auto_trader import send_trade_report
    send_trade_report()
    print("  완료")
except Exception as e:
    print(f"  오류: {e}")
    import traceback; traceback.print_exc()
