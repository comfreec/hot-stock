import sqlite3
conn = sqlite3.connect('/data/scan_cache.db')
rows = conn.execute(
    'SELECT alert_date, symbol, name, status FROM alert_history ORDER BY alert_date DESC LIMIT 20'
).fetchall()
print(f"총 {len(rows)}개")
for r in rows:
    print(r)
conn.close()
