"""스케줄러 상태 및 최근 동작 확인"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
from datetime import datetime, date, timezone, timedelta

KST = timezone(timedelta(hours=9))
now_kst = datetime.now(KST)
print(f"현재 시각 (KST): {now_kst.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

# 스케줄러 상태 파일
state_file = "/data/.scheduler_state"
try:
    import json
    with open(state_file) as f:
        state = json.load(f)
    print(f"\n=== 스케줄러 상태 ===", flush=True)
    for k, v in state.items():
        print(f"  {k}: {v}", flush=True)
except Exception as e:
    print(f"상태 파일 없음: {e}", flush=True)

# trade_orders 현재 상태
DB = "/data/scan_cache.db"
conn = sqlite3.connect(DB)
print(f"\n=== trade_orders active/pending ===", flush=True)
rows = conn.execute("""
    SELECT id, symbol, name, status, qty, avg_price, split_step,
           entry_price, target_price, stop_price
    FROM trade_orders WHERE status IN ('active','pending')
    ORDER BY alert_date
""").fetchall()
print(f"총 {len(rows)}개:", flush=True)
for r in rows:
    oid, sym, name, status, qty, avg_p, step, entry, target, stop = r
    print(f"  [{oid}] {status:8s} | {name}({sym}) | qty={qty} avg={avg_p} step={step}", flush=True)
    print(f"         entry={entry} target={target} stop={stop}", flush=True)

# 오늘 expired/cancelled 된 것
today = date.today().isoformat()
print(f"\n=== 오늘({today}) 종료 처리된 종목 ===", flush=True)
closed = conn.execute("""
    SELECT id, symbol, name, status, exit_date, exit_price, return_pct
    FROM trade_orders WHERE exit_date = ?
    ORDER BY id
""", (today,)).fetchall()
for r in closed:
    print(f"  [{r[0]}] {r[2]}({r[1]}) → {r[3]} exit={r[5]} ret={r[6]}", flush=True)
if not closed:
    print("  없음", flush=True)

conn.close()

# KIS 잔고 현재 조회
print(f"\n=== KIS 실제 잔고 ===", flush=True)
try:
    from auto_trader import KISClient, is_enabled, is_market_open
    print(f"장 시간 여부: {is_market_open()}", flush=True)
    if is_enabled():
        client = KISClient()
        balance = client.get_balance()
        holdings = balance.get("holdings", {})
        cash = balance.get("cash", 0)
        print(f"예수금: ₩{cash:,.0f}", flush=True)
        print(f"보유 종목 {len(holdings)}개:", flush=True)
        for code, info in holdings.items():
            print(f"  {code}: {info.get('qty')}주 avg=₩{info.get('avg_price'):,.0f}", flush=True)
        if not holdings:
            print("  ⚠️ holdings 비어있음 - 잔고 조회 실패 가능성!", flush=True)
    else:
        print("KIS_APP_KEY 없음", flush=True)
except Exception as e:
    print(f"KIS 조회 오류: {e}", flush=True)
