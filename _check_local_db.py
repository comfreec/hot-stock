import sqlite3, os
conn = sqlite3.connect('scan_cache.db')

print('=== 테이블 목록 ===')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    print(t[0])

print()
print('=== scan_results ===')
cnt = conn.execute('SELECT COUNT(*) FROM scan_results').fetchone()[0]
print(f'총 {cnt}건')
rows = conn.execute('SELECT scan_date, created_at FROM scan_results ORDER BY scan_date DESC LIMIT 5').fetchall()
for r in rows:
    print(r)

print()
print('=== alert_history ===')
cnt2 = conn.execute('SELECT COUNT(*) FROM alert_history').fetchone()[0]
print(f'총 {cnt2}건')
rows2 = conn.execute('SELECT alert_date, symbol, name, score, status FROM alert_history ORDER BY alert_date DESC LIMIT 10').fetchall()
for r in rows2:
    print(r)

conn.close()
