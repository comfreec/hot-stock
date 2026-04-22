"""
잔고검증 오류로 cancelled된 주문을 active로 복구
"""
import sqlite3
from datetime import date

conn = sqlite3.connect('/data/scan_cache.db')

# cancelled된 주문 확인
rows = conn.execute(
    "SELECT id, name, symbol, alert_date FROM trade_orders WHERE status='cancelled' ORDER BY id DESC"
).fetchall()
print(f'cancelled 주문: {len(rows)}건')
for r in rows:
    print(f'  [{r[3]}] {r[1]}({r[2]})')

# 전부 active로 복구
conn.execute("UPDATE trade_orders SET status='active' WHERE status='cancelled'")
conn.commit()

# 확인
rows2 = conn.execute("SELECT id, name, symbol, status FROM trade_orders ORDER BY id DESC").fetchall()
print(f'\n복구 후:')
for r in rows2:
    print(f'  {r[1]}({r[2]}) → {r[3]}')

conn.close()
print('\n복구 완료')
