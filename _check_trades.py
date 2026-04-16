import sqlite3, os
db = "/data/scan_cache.db" if os.path.isdir("/data") else "scan_cache.db"
conn = sqlite3.connect(db)

print("=== trade_orders ===")
rows = conn.execute("SELECT id,symbol,name,status,split_step,avg_price,qty,alert_date FROM trade_orders ORDER BY id DESC LIMIT 10").fetchall()
if rows:
    for r in rows:
        print(r)
else:
    print("없음")

print("\n=== alert_history (최근 5개) ===")
rows2 = conn.execute("SELECT id,symbol,name,status,entry_price,alert_date FROM alert_history ORDER BY id DESC LIMIT 5").fetchall()
for r in rows2:
    print(r)

conn.close()
