import sqlite3
from datetime import date, timedelta

conn = sqlite3.connect('/data/scan_cache.db')
today = date.today().isoformat()

# 태림포장, 애경산업 expired → active 복구
targets = ['태림포장', '애경산업']
for name in targets:
    r = conn.execute(
        "UPDATE alert_history SET status='active', exit_date=NULL WHERE name=? AND status='expired'",
        (name,)
    )
    print(f"  {name} 복구: {r.rowcount}건")

conn.commit()

# 전체 현황 확인
rows = conn.execute(
    "SELECT id, alert_date, name, status, entry_price FROM alert_history ORDER BY alert_date DESC LIMIT 20"
).fetchall()
print("전체 현황:")
for r in rows:
    print(f"  id={r[0]} {r[1]} {r[2]} status={r[3]} entry={r[4]}")

conn.close()
