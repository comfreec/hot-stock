import sys, os
sys.path.insert(0, '/app')
os.environ.setdefault('DB_PATH', '/data/scan_cache.db')
from telegram_alert import send_weekly_summary
send_weekly_summary()
print('채널 주간보고서 전송 완료')
