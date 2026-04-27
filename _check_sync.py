"""
alert_history vs trade_orders 동기화 상태 확인 및 불일치 종목 동기화
"""
import sqlite3, os, sys
sys.path.insert(0, os.path.dirname(__file__))

DB_PATH = os.environ.get("DB_PATH", "/data/scan_cache.db" if os.path.isdir("/data") else "scan_cache.db")
conn = sqlite3.connect(DB_PATH)

print("=== alert_history (채널 기준 활성 종목) ===")
ah_rows = conn.execute("""
    SELECT id, symbol, name, status, entry_price, stop_price, avg_price, split_step, alert_date
    FROM alert_history WHERE status IN ('pending','active')
    ORDER BY alert_date DESC
""").fetchall()
ah_syms = {}
for r in ah_rows:
    rid, sym, name, status, entry, stop, avg, step, adate = r
    ah_syms[sym] = {"id": rid, "name": name, "status": status, "entry": entry, "stop": stop, "avg": avg, "step": step}
    print(f"  {name}({sym}) status={status} entry={entry} stop={stop} avg={avg} step={step} date={adate}")

print()
print("=== trade_orders (자동매매 활성 종목) ===")
to_syms = {}
try:
    to_rows = conn.execute("""
        SELECT symbol, name, status, avg_price, stop_price, split_step, created_at
        FROM trade_orders WHERE status IN ('active','pending')
        ORDER BY created_at DESC
    """).fetchall()
    for r in to_rows:
        sym, name, status, avg, stop, step, created = r
        to_syms[sym] = {"name": name, "status": status, "avg": avg, "stop": stop, "step": step}
        print(f"  {name}({sym}) status={status} avg={avg} stop={stop} step={step} created={created}")
except Exception as e:
    print(f"  trade_orders 없음: {e}")

print()
print("=== 불일치 분석 ===")
# 채널에는 있는데 자동매매에는 없는 종목
only_channel = set(ah_syms.keys()) - set(to_syms.keys())
# 자동매매에는 있는데 채널에는 없는 종목
only_trade = set(to_syms.keys()) - set(ah_syms.keys())
# 둘 다 있는 종목
both = set(ah_syms.keys()) & set(to_syms.keys())

if only_channel:
    print(f"채널에만 있는 종목 (자동매매 없음): {[ah_syms[s]['name']+'('+s+')' for s in only_channel]}")
if only_trade:
    print(f"자동매매에만 있는 종목 (채널 없음): {[to_syms[s]['name']+'('+s+')' for s in only_trade]}")
if both:
    print(f"양쪽 모두 있는 종목: {[ah_syms[s]['name']+'('+s+')' for s in both]}")

conn.close()
