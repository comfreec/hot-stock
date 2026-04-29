"""Fly 서버에서 주간 보고서 강제 재전송"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== 동기화 시작 ===", flush=True)
from cache_db import update_alert_status
update_alert_status()
print("=== 동기화 완료 ===", flush=True)

from cache_db import _get_conn
conn = _get_conn()
rows = conn.execute("""
    SELECT symbol, name, status, avg_price, split_step, entry_price, target_price, stop_price
    FROM alert_history
    WHERE status IN ('active','pending')
    ORDER BY status, symbol
""").fetchall()
print(f"\n[alert_history] active/pending 종목 {len(rows)}개:", flush=True)
for r in rows:
    sym, name, status, avg_p, step, entry, target, stop = r
    print(f"  {status:8s} | {name}({sym}) | avg={avg_p} step={step} entry={entry} target={target} stop={stop}", flush=True)
conn.close()

print("\n=== 주간 보고서 전송 시작 ===", flush=True)
from telegram_alert import send_weekly_summary
send_weekly_summary(force=True)
print("=== 주간 보고서 전송 완료 ===", flush=True)
