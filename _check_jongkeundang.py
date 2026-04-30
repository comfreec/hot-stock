"""종근당 종목 상태 진단"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
from datetime import date

DB = "/data/scan_cache.db"
conn = sqlite3.connect(DB)

print("=== trade_orders 종근당 상태 ===", flush=True)
rows = conn.execute("""
    SELECT id, symbol, name, status, qty, avg_price, split_step,
           entry_price, target_price, stop_price, alert_date, exit_date, exit_price, return_pct
    FROM trade_orders WHERE symbol LIKE '%185750%' OR name LIKE '%종근당%'
    ORDER BY id
""").fetchall()
for r in rows:
    print(f"  id={r[0]} status={r[3]} qty={r[4]} avg={r[5]} step={r[6]}", flush=True)
    print(f"  entry={r[7]} target={r[8]} stop={r[9]}", flush=True)
    print(f"  alert={r[10]} exit_date={r[11]} exit_price={r[12]} return={r[13]}", flush=True)

print("\n=== KIS 실제 잔고 조회 ===", flush=True)
try:
    from auto_trader import KISClient, is_enabled
    if not is_enabled():
        print("KIS_APP_KEY 없음 - 잔고 조회 불가", flush=True)
    else:
        client = KISClient()
        balance = client.get_balance()
        holdings = balance.get("holdings", {})
        cash = balance.get("cash", 0)
        print(f"예수금: ₩{cash:,.0f}", flush=True)
        print(f"보유 종목 {len(holdings)}개:", flush=True)
        for code, info in holdings.items():
            print(f"  {code}: {info.get('qty')}주 avg=₩{info.get('avg_price'):,.0f}", flush=True)

        # 종근당 코드 확인
        jkd_code = "185750"
        if jkd_code in holdings:
            print(f"\n종근당({jkd_code}) 실제 보유: {holdings[jkd_code]}", flush=True)
        else:
            print(f"\n종근당({jkd_code}) 실제 잔고 없음 (holdings에 미포함)", flush=True)
            print(f"→ holdings가 비어있으면 잔고 조회 실패 가능성", flush=True)
except Exception as e:
    print(f"KIS 조회 오류: {e}", flush=True)
    import traceback; traceback.print_exc()

conn.close()
