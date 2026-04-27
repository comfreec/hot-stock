"""
alert_history ↔ trade_orders 동기화
- 현대해상: 채널에만 있고 자동매매 미체결 → alert_history에서 제거
- HS효성첨단소재: 자동매매에만 있고 채널 누락 → alert_history에 추가
"""
import sqlite3, os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "/data/scan_cache.db" if os.path.isdir("/data") else "fly_check_now.db")
conn = sqlite3.connect(DB_PATH)

# 1. 현대해상 - 자동매매 미체결이므로 alert_history에서 삭제
rows = conn.execute(
    "SELECT id, symbol, name, status FROM alert_history WHERE symbol='001450.KS' AND status IN ('pending','active')"
).fetchall()
if rows:
    for r in rows:
        print(f"현대해상({r[1]}) id={r[0]} status={r[3]} → 삭제")
    conn.execute("DELETE FROM alert_history WHERE symbol='001450.KS' AND status IN ('pending','active')")
else:
    print("현대해상: alert_history에 없음 (이미 처리됨)")

# 2. HS효성첨단소재 - trade_orders에서 정보 가져와 alert_history에 추가
to_row = conn.execute(
    "SELECT symbol, name, status, avg_price, stop_price, split_step, created_at FROM trade_orders WHERE symbol='298050.KS' AND status='active'"
).fetchone()
if to_row:
    sym, name, status, avg, stop, step, created = to_row
    # 이미 alert_history에 있는지 확인
    existing = conn.execute(
        "SELECT id FROM alert_history WHERE symbol=? AND status IN ('pending','active')", (sym,)
    ).fetchone()
    if not existing:
        alert_date = created[:10] if created else datetime.now().strftime("%Y-%m-%d")
        conn.execute("""
            INSERT INTO alert_history
            (alert_date, symbol, name, score, entry_price, entry_label,
             target_price, stop_price, rr_ratio, status, created_at, avg_price, split_step)
            VALUES (?,?,?,?,?,?,?,?,?,'active',?,?,?)
        """, (
            alert_date, sym, name, 0,
            avg, "장기선",
            None, stop,
            None,
            datetime.now().isoformat(),
            avg, step or 1
        ))
        print(f"HS효성첨단소재({sym}) → alert_history 추가 (avg={avg}, stop={stop}, step={step})")
    else:
        print(f"HS효성첨단소재({sym}): 이미 alert_history에 있음 (id={existing[0]})")
else:
    print("HS효성첨단소재: trade_orders에 없음")

conn.commit()

# 결과 확인
print()
print("=== 동기화 후 alert_history 활성 종목 ===")
rows = conn.execute("""
    SELECT symbol, name, status, avg_price, split_step, alert_date
    FROM alert_history WHERE status IN ('pending','active')
    ORDER BY alert_date DESC
""").fetchall()
for r in rows:
    print(f"  {r[1]}({r[0]}) status={r[2]} avg={r[3]} step={r[4]} date={r[5]}")

conn.close()
