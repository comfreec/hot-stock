import sqlite3
from datetime import date
conn = sqlite3.connect('/data/scan_cache.db')
today = date.today().isoformat()
print(f'오늘: {today}')
for sym in ['018250.KS', '011280.KS']:
    rows = conn.execute(
        'SELECT symbol, status, alert_date, entry_price FROM alert_history '
        'WHERE symbol=? ORDER BY id DESC LIMIT 3', (sym,)
    ).fetchall()
    print(f'\n{sym}:')
    for r in rows:
        print(f'  {r}')
    # 추적중 판단 쿼리
    row = conn.execute(
        'SELECT entry_price, status FROM alert_history '
        'WHERE symbol=? AND status IN (?,?) AND alert_date < ? '
        'ORDER BY id DESC LIMIT 1',
        (sym, 'pending', 'active', today)
    ).fetchone()
    print(f'  → 추적중 판단: {row}')
conn.close()
