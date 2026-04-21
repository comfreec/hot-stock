"""
오늘 매수된 카카오페이/코스모화학 손절가를 RSI 바닥 저점으로 수정
"""
import sqlite3

DB = '/data/scan_cache.db'

fixes = [
    ('377300.KS', 43650, '카카오페이'),
    ('005420.KS', 13280, '코스모화학'),
]

conn = sqlite3.connect(DB)
for sym, new_stop, name in fixes:
    # trade_orders 수정
    row = conn.execute('SELECT id, stop_price FROM trade_orders WHERE symbol=? AND alert_date=? ORDER BY id DESC LIMIT 1', (sym, '2026-04-21')).fetchone()
    if row:
        old_stop = row[1]
        conn.execute('UPDATE trade_orders SET stop_price=? WHERE id=?', (new_stop, row[0]))
        print(f'{name}: trade_orders 손절가 {old_stop:,} → {new_stop:,}')
    else:
        print(f'{name}: trade_orders 오늘 주문 없음')

    # trade_orders_multi도 수정
    row2 = conn.execute('SELECT id, stop_price FROM trade_orders_multi WHERE symbol=? AND alert_date=? ORDER BY id DESC LIMIT 1', (sym, '2026-04-21')).fetchone()
    if row2:
        old_stop2 = row2[1]
        conn.execute('UPDATE trade_orders_multi SET stop_price=? WHERE id=?', (new_stop, row2[0]))
        print(f'{name}: trade_orders_multi 손절가 {old_stop2:,} → {new_stop:,}')

conn.commit()
conn.close()
print('완료')
