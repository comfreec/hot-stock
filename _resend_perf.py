"""
채널 성과 업데이트 알림 재전송 (DB 연결 직접 사용)
"""
import os, sys, sqlite3
os.chdir('/app')
sys.path.insert(0, '/app')

DB = '/data/scan_cache.db'
os.environ['DB_PATH'] = DB

# cache_db 초기화 강제
import cache_db
cache_db._db_initialized = False
cache_db._local = type('obj', (object,), {})()

from telegram_alert import send_performance_update
print("성과 업데이트 알림 전송 중...")
try:
    send_performance_update()
    print("완료")
except Exception as e:
    print(f"오류: {e}")
    import traceback; traceback.print_exc()
