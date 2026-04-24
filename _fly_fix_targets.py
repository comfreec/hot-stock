"""
Fly 서버에서 직접 실행: alert_history 활성 종목 목표가를 손익비 2:1 보장 로직으로 재계산
"""
import sqlite3, os, sys
sys.path.insert(0, '/app')
os.environ.setdefault('DB_PATH', '/data/scan_cache.db')

from telegram_alert import calc_price_levels

DB_PATH = os.environ.get("DB_PATH", "/data/scan_cache.db")
conn = sqlite3.connect(DB_PATH)

rows = conn.execute("""
    SELECT id, symbol, name, entry_price, target_price, stop_price
    FROM alert_history WHERE status IN ('pending','active')
    ORDER BY id
""").fetchall()

print(f"활성 종목 {len(rows)}개 목표가 재계산 중...")
updated = 0
for rid, sym, name, entry, old_target, old_stop in rows:
    lv = calc_price_levels(sym)
    if not lv or not lv.get("target"):
        print(f"  [{sym}] {name}: 계산 실패, 스킵")
        continue

    new_target = lv["target"]
    new_stop   = lv["stop"]
    new_rr     = lv["rr"]

    print(f"  [{sym}] {name}: target {old_target:,.0f}→{new_target:,.0f}  stop {old_stop:,.0f}→{new_stop:,.0f}  RR={new_rr:.2f}:1")
    conn.execute("""
        UPDATE alert_history SET target_price=?, stop_price=?, rr_ratio=?
        WHERE id=?
    """, (new_target, new_stop, new_rr, rid))
    updated += 1

# trade_orders도 동기화
try:
    to_rows = conn.execute("""
        SELECT symbol FROM trade_orders WHERE status IN ('active','pending')
    """).fetchall()
    for (sym,) in to_rows:
        ah = conn.execute(
            "SELECT target_price, stop_price FROM alert_history WHERE symbol=? AND status IN ('pending','active') ORDER BY id DESC LIMIT 1",
            (sym,)
        ).fetchone()
        if ah:
            conn.execute("""
                UPDATE trade_orders SET stop_price=?
                WHERE symbol=? AND status IN ('active','pending')
            """, (ah[1], sym))
    print("trade_orders 손절가 동기화 완료")
except Exception as e:
    print(f"trade_orders 동기화 오류: {e}")

conn.commit()
conn.close()
print(f"\n완료: {updated}개 업데이트됨")
