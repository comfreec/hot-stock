"""alert_history 중복 레코드 정리 - 같은 종목에 active + expired 공존 시 expired 삭제"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
DB = "/data/scan_cache.db"
conn = sqlite3.connect(DB)

# active인 종목 목록
active_syms = {r[0] for r in conn.execute(
    "SELECT DISTINCT symbol FROM alert_history WHERE status IN ('active','pending')"
).fetchall()}

print(f"active/pending 종목: {active_syms}", flush=True)

# 같은 종목에 expired/hit_target/hit_stop이 있고 avg_price가 NULL인 오래된 레코드 삭제
deleted = 0
for sym in active_syms:
    # 해당 종목의 active 레코드 id (최신 것)
    active_ids = [r[0] for r in conn.execute(
        "SELECT id FROM alert_history WHERE symbol=? AND status IN ('active','pending') ORDER BY id DESC",
        (sym,)
    ).fetchall()]

    if len(active_ids) <= 1:
        continue  # active가 1개면 중복 없음

    # 가장 최신 active 1개만 남기고 나머지 active 삭제
    keep_id = active_ids[0]
    for dup_id in active_ids[1:]:
        conn.execute("DELETE FROM alert_history WHERE id=?", (dup_id,))
        deleted += 1
        print(f"  중복 active 삭제: id={dup_id} {sym}", flush=True)

# active 종목과 같은 심볼의 expired 레코드 중 avg_price가 NULL인 것 삭제 (오래된 스캔 전용 레코드)
for sym in active_syms:
    old_expired = conn.execute(
        "SELECT id, avg_price, alert_date FROM alert_history "
        "WHERE symbol=? AND status IN ('expired','hit_target','hit_stop') "
        "AND avg_price IS NULL ORDER BY id",
        (sym,)
    ).fetchall()
    for eid, avg_p, adate in old_expired:
        conn.execute("DELETE FROM alert_history WHERE id=?", (eid,))
        deleted += 1
        print(f"  avg_price NULL expired 삭제: id={eid} {sym} {adate}", flush=True)

conn.commit()
print(f"\n총 {deleted}개 중복/불필요 레코드 삭제 완료", flush=True)

# 최종 상태
print("\n=== 최종 alert_history active/pending ===", flush=True)
rows = conn.execute("""
    SELECT symbol, name, status, avg_price, split_step
    FROM alert_history WHERE status IN ('active','pending')
    ORDER BY alert_date DESC
""").fetchall()
for r in rows:
    print(f"  {r[2]:8s} | {r[1]}({r[0]}) avg={r[3]} step={r[4]}", flush=True)

conn.close()
