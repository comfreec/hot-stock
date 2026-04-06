import sqlite3
from datetime import date
conn = sqlite3.connect('/data/scan_cache.db')
rows = conn.execute(
    "SELECT id, alert_date, name, status, entry_price FROM alert_history WHERE status='pending' ORDER BY alert_date"
).fetchall()
today = date.today()
print(f"pending 종목 {len(rows)}개:")
for r in rows:
    rid, alert_date, name, status, entry = r
    from datetime import date as d
    days = (today - d.fromisoformat(alert_date)).days
    print(f"  id={rid} {alert_date} {name} entry={entry} {days}일경과")
conn.close()
