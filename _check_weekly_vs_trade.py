"""주간리포트 active vs 자동매매 active 비교"""
import sqlite3, os

db = "/data/scan_cache.db"
if not os.path.exists(db):
    db = "scan_cache.db"

conn = sqlite3.connect(db)

print("=== alert_history active/pending ===")
rows = conn.execute("""
    SELECT symbol, name, status, entry_price, avg_price, alert_date
    FROM alert_history
    WHERE status IN ('active','pending')
    ORDER BY alert_date DESC
""").fetchall()
for r in rows:
    print(r)

print(f"\n총 {len(rows)}개")

print("\n=== trade_orders active/pending ===")
rows2 = conn.execute("""
    SELECT symbol, name, status, entry_price, avg_price, created_at
    FROM trade_orders
    WHERE status IN ('active','pending')
    ORDER BY created_at DESC
""").fetchall()
for r in rows2:
    print(r)

print(f"\n총 {len(rows2)}개")
conn.close()
