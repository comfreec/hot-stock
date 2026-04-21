import sqlite3
conn = sqlite3.connect('/data/scan_cache.db')
try:
    rows = conn.execute('SELECT name, symbol, entry_price, stop_price, status, alert_date FROM trade_orders ORDER BY id DESC LIMIT 10').fetchall()
    print(f'trade_orders {len(rows)}건:')
    for r in rows:
        name, sym, entry, stop, status, adate = r
        entry = entry or 1
        pct = round((stop/entry-1)*100,1) if stop else 0
        print(f'[{adate}] {name}({sym}) 매수={entry} 손절={stop}({pct}%) [{status}]')
except Exception as e:
    print(f'오류: {e}')
conn.close()
