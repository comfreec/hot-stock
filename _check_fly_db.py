import sqlite3, os

db = os.environ.get("DB_PATH", "/data/scan_cache.db")
print(f"DB: {db}")

if not os.path.exists(db):
    print("DB 파일 없음 (아직 스캔 안 됨)")
else:
    conn = sqlite3.connect(db)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("테이블:", [t[0] for t in tables])

    print("\n=== alert_history ===")
    rows = conn.execute("""
        SELECT alert_date, name, status, entry_price, target_price, stop_price, return_pct
        FROM alert_history ORDER BY alert_date DESC
    """).fetchall()
    if rows:
        for r in rows:
            print(f"  {r[0]} | {r[1]:<15} | {r[2]:<12} | entry={r[3]} target={r[4]} stop={r[5]} ret={r[6]}")
    else:
        print("  데이터 없음")

    print("\n=== scan_results (최근 3개) ===")
    rows = conn.execute("SELECT scan_date, created_at FROM scan_results ORDER BY scan_date DESC LIMIT 3").fetchall()
    if rows:
        for r in rows: print(f"  {r[0]} | {r[1]}")
    else:
        print("  데이터 없음")

    conn.close()
