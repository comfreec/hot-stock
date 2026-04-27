"""alert_history의 rr_ratio를 entry/target/stop 기준으로 재계산"""
import sqlite3, os
DB_PATH = os.environ.get("DB_PATH", "/data/scan_cache.db")
conn = sqlite3.connect(DB_PATH)
rows = conn.execute("""
    SELECT id, symbol, name, entry_price, target_price, stop_price
    FROM alert_history WHERE status IN ('pending','active')
""").fetchall()
updated = 0
for rid, sym, name, entry, target, stop in rows:
    if entry and target and stop:
        risk = max(entry - stop, 1)
        rr = (target - entry) / risk
        conn.execute("UPDATE alert_history SET rr_ratio=? WHERE id=?", (round(rr, 4), rid))
        print(f"  {name}({sym}): rr={rr:.2f}")
        updated += 1
conn.commit()
conn.close()
print(f"완료: {updated}개 업데이트")
