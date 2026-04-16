import sqlite3, os
db = "/data/scan_cache.db" if os.path.isdir("/data") else "scan_cache.db"
conn = sqlite3.connect(db)
conn.execute("UPDATE trade_orders SET status='active' WHERE status='pending' AND split_step=1")
conn.commit()
rows = conn.execute("SELECT id,symbol,name,status,split_step,avg_price,qty FROM trade_orders").fetchall()
print("=== 업데이트 후 trade_orders ===")
for r in rows:
    print(r)
conn.close()
