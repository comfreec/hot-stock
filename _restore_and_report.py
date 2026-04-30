"""
오늘 잘못 expired 처리된 trade_orders 종목 복구 + alert_history 동기화 + 주간 보고서 재전송
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
from datetime import datetime, date

DB = "/data/scan_cache.db"
conn = sqlite3.connect(DB)
today = date.today().isoformat()

print("=== 오늘 expired 처리된 종목 확인 ===", flush=True)
expired_today = conn.execute("""
    SELECT id, symbol, name, avg_price, split_step, entry_price, target_price, stop_price, qty, alert_date
    FROM trade_orders
    WHERE status = 'expired' AND exit_date = ?
    ORDER BY alert_date
""", (today,)).fetchall()

print(f"오늘 expired 종목 {len(expired_today)}개:", flush=True)
for r in expired_today:
    oid, sym, name, avg_p, step, entry, target, stop, qty, adate = r
    print(f"  [{oid}] {name}({sym}) avg={avg_p} step={step} qty={qty} | {adate}", flush=True)

# 복구: expired → active (exit_date, exit_price, return_pct 초기화)
if expired_today:
    print(f"\n=== 복구 시작 ===", flush=True)
    for r in expired_today:
        oid, sym, name, avg_p, step, entry, target, stop, qty, adate = r
        conn.execute("""
            UPDATE trade_orders
            SET status='active', exit_date=NULL, exit_price=NULL, return_pct=NULL
            WHERE id=?
        """, (oid,))
        print(f"  ✅ 복구: {name}({sym})", flush=True)
    conn.commit()
    print("=== trade_orders 복구 완료 ===", flush=True)

# alert_history도 오늘 잘못 처리된 것 복구
print("\n=== alert_history 복구 ===", flush=True)
ah_expired = conn.execute("""
    SELECT id, symbol, name FROM alert_history
    WHERE status IN ('expired','hit_stop','hit_target') AND exit_date = ?
""", (today,)).fetchall()
print(f"alert_history 오늘 종료 처리된 {len(ah_expired)}개:", flush=True)

# trade_orders에서 복구된 심볼 목록
restored_syms = {r[1] for r in expired_today}
for ah_id, sym, name in ah_expired:
    if sym in restored_syms:
        conn.execute("""
            UPDATE alert_history
            SET status='active', exit_date=NULL, exit_price=NULL, return_pct=NULL
            WHERE id=?
        """, (ah_id,))
        print(f"  ✅ alert_history 복구: {name}({sym})", flush=True)
conn.commit()
conn.close()

# 동기화
print("\n=== alert_history 동기화 ===", flush=True)
from cache_db import update_alert_status
update_alert_status()
print("동기화 완료", flush=True)

# 최종 상태 확인
conn3 = sqlite3.connect(DB)
active_now = conn3.execute("""
    SELECT symbol, name, status, avg_price, split_step, target_price, stop_price
    FROM trade_orders WHERE status IN ('active','pending')
    ORDER BY alert_date
""").fetchall()
print(f"\n=== 최종 active/pending 종목 {len(active_now)}개 ===", flush=True)
for r in active_now:
    print(f"  {r[2]:8s} | {r[1]}({r[0]}) avg={r[3]} step={r[4]}", flush=True)
conn3.close()

# 주간 보고서 재전송
print("\n=== 주간 보고서 재전송 ===", flush=True)
from telegram_alert import send_weekly_summary
send_weekly_summary(force=True)
print("=== 완료 ===", flush=True)
