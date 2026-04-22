import os, sys
os.chdir('/app')
sys.path.insert(0, '/app')
os.environ['DB_PATH'] = '/data/scan_cache.db'
from telegram_alert import send_weekly_summary
send_weekly_summary(force=True)
print('주간보고서 전송 완료')
