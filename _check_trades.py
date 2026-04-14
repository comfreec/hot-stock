import sqlite3, os

db = "/data/scan_cache.db" if os.path.isdir("/data") else "scan_cache.db"
conn = sqlite3.connect(db)

# trade_orders 테이블 존재 여부 확인
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("테이블 목록:", [t[0] for t in tables])

try:
    rows = conn.execute("""
        SELECT id, alert_date, symbol, name, entry_price, target_price, stop_price, qty, status, order_no
        FROM trade_orders ORDER BY id DESC LIMIT 20
    """).fetchall()
    if rows:
        print(f"\n[자동매매 주문 내역] {len(rows)}건")
        for r in rows:
            print(f"  {r[1]} | {r[3]}({r[2]}) | 매수:{r[4]:,} 목표:{r[5]:,} 손절:{r[6]:,} | {r[7]}주 | {r[8]} | 주문번호:{r[9]}")
    else:
        print("\n[자동매매] 주문 내역 없음")
except Exception as e:
    print(f"trade_orders 없음: {e}")

conn.close()
