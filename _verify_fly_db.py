import sqlite3
conn = sqlite3.connect('/data/scan_cache.db')
s = conn.execute('SELECT COUNT(*) FROM scan_results').fetchone()[0]
a = conn.execute('SELECT COUNT(*) FROM alert_history').fetchone()[0]
print(f'scan_results: {s}건, alert_history: {a}건')
rows = conn.execute('SELECT alert_date, symbol, name, status FROM alert_history ORDER BY alert_date DESC').fetchall()
for r in rows:
    print(r)
conn.close()
