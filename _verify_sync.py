"""동기화 검증: trade_orders ↔ alert_history 비교"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
DB = "/data/scan_cache.db"

def show_state(label):
    conn = sqlite3.connect(DB)
    print(f"\n{'='*50}", flush=True)
    print(f"[{label}]", flush=True)

    to_rows = conn.execute("""
        SELECT symbol, name, status, avg_price, split_step, exit_price, exit_date, return_pct
        FROM trade_orders ORDER BY alert_date
    """).fetchall()
    print(f"\ntrade_orders ({len(to_rows)}행):", flush=True)
    for r in to_rows:
        sym, name, status, avg_p, step, ep, ed, ret = r
        print(f"  {status:12s} | {name}({sym}) avg={avg_p} step={step}"
              + (f" exit={ep} {ed} ret={ret}%" if ep else ""), flush=True)

    ah_rows = conn.execute("""
        SELECT symbol, name, status, avg_price, split_step, exit_price, exit_date, return_pct
        FROM alert_history ORDER BY alert_date DESC LIMIT 20
    """).fetchall()
    print(f"\nalert_history 최근 20행:", flush=True)
    for r in ah_rows:
        sym, name, status, avg_p, step, ep, ed, ret = r
        print(f"  {status:12s} | {name}({sym}) avg={avg_p} step={step}"
              + (f" exit={ep} {ed} ret={ret}%" if ep else ""), flush=True)

    # 불일치 체크
    print(f"\n불일치 체크:", flush=True)
    to_active = {r[0]: r for r in to_rows if r[2] in ('active','pending')}
    to_closed = {r[0]: r for r in to_rows if r[2] in ('hit_target','hit_stop','expired','cancelled')}
    ah_active = {r[0]: r for r in ah_rows if r[2] in ('active','pending')}
    ah_closed = {r[0]: r for r in ah_rows if r[2] in ('hit_target','hit_stop','expired')}

    issues = []
    for sym in to_active:
        if sym not in ah_active:
            issues.append(f"  ⚠️ trade_orders active인데 alert_history 없음: {to_active[sym][1]}({sym})")
    for sym in to_closed:
        if sym in ah_active:
            issues.append(f"  ⚠️ trade_orders 종료됐는데 alert_history 아직 active: {to_closed[sym][1]}({sym})")
    for sym in ah_active:
        if sym not in to_active:
            issues.append(f"  ℹ️ alert_history active인데 trade_orders 없음 (스캔 전용): {ah_active[sym][1]}({sym})")

    if issues:
        for i in issues: print(i, flush=True)
    else:
        print("  ✅ 불일치 없음", flush=True)

    conn.close()

# 동기화 전 상태
show_state("동기화 전")

# 동기화 실행
print("\n\n>>> update_alert_status() 실행...", flush=True)
from cache_db import update_alert_status
update_alert_status()
print(">>> 완료", flush=True)

# 동기화 후 상태
show_state("동기화 후")
