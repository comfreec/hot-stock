import sqlite3, os
from auto_trader import KISClient

# KIS 연결 확인
c = KISClient()
p = c.get_price("005930")
print("삼성전자:", p)
b = c.get_balance()
print("예수금:", b.get("cash"))

# trade_orders DB 확인
db = "/data/scan_cache.db" if os.path.isdir("/data") else "scan_cache.db"
conn = sqlite3.connect(db)
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("테이블:", tables)

if "trade_orders" in tables:
    rows = conn.execute("SELECT id,alert_date,symbol,name,entry_price,target_price,stop_price,qty,status FROM trade_orders ORDER BY id DESC LIMIT 10").fetchall()
    if rows:
        print(f"\n[자동매매 주문] {len(rows)}건")
        for r in rows:
            print(f"  {r[1]} | {r[3]}({r[2]}) | 매수:{r[4]:,} 목표:{r[5]:,} | {r[7]}주 | {r[8]}")
    else:
        print("\n[자동매매] 주문 내역 없음 (테이블 비어있음)")
else:
    print("\n[자동매매] trade_orders 테이블 없음 - 아직 주문 없음")
conn.close()
