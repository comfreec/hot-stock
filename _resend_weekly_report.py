from cache_db import update_alert_status
from telegram_alert import send_weekly_summary
update_alert_status()
send_weekly_summary(force=True)
print("주간 리포트 전송 완료")
