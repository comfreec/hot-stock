import sqlite3
from datetime import date

conn = sqlite3.connect('/data/scan_cache.db')

# 태림포장, 애경산업 active 복구
for name in ['태림포장', '애경산업']:
    r = conn.execute(
        "UPDATE alert_history SET status='active', exit_date=NULL WHERE name=? AND status='expired'",
        (name,)
    )
    if r.rowcount:
        print(f"  {name} → active 복구")

conn.commit()

rows = conn.execute(
    "SELECT id, alert_date, name, status, entry_price FROM alert_history ORDER BY alert_date DESC LIMIT 15"
).fetchall()
print("전체 현황:")
for r in rows:
    print(f"  id={r[0]} {r[1]} {r[2]} status={r[3]} entry={r[4]}")
conn.close()
