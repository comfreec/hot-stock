cd /app && python3 << 'EOF'
import sqlite3
db = "/data/scan_cache.db"
conn = sqlite3.connect(db)
print("=== alert_history active/pending ===")
rows = conn.execute("SELECT symbol, name, status FROM alert_history WHERE status IN ('active','pending') ORDER BY alert_date DESC").fetchall()
for r in rows: print(r)
print(f"총 {len(rows)}개")
print("\n=== trade_orders active/pending ===")
rows2 = conn.execute("SELECT symbol, name, status FROM trade_orders WHERE status IN ('active','pending') ORDER BY created_at DESC").fetchall()
for r in rows2: print(r)
print(f"총 {len(rows2)}개")
conn.close()
EOF
