import sqlite3

conn = sqlite3.connect('fly_check_now.db')

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('테이블:', [t[0] for t in tables])

print()
print('=== alert_history (채널 기준 활성) ===')
ah = conn.execute("""
    SELECT id, symbol, name, status, entry_price, stop_price, avg_price, split_step, alert_date
    FROM alert_history WHERE status IN ('pending','active')
    ORDER BY alert_date DESC
""").fetchall()
ah_syms = {}
for r in ah:
    rid, sym, name, status, entry, stop, avg, step, adate = r
    ah_syms[sym] = {"id": rid, "name": name, "status": status, "entry": entry, "stop": stop, "avg": avg, "step": step}
    print(f"  {name}({sym}) status={status} entry={entry} stop={stop} avg={avg} step={step} date={adate}")

print()
print('=== trade_orders (자동매매 활성) ===')
to_syms = {}
try:
    to = conn.execute("""
        SELECT symbol, name, status, avg_price, stop_price, split_step, created_at
        FROM trade_orders WHERE status IN ('active','pending')
        ORDER BY created_at DESC
    """).fetchall()
    for r in to:
        sym, name, status, avg, stop, step, created = r
        to_syms[sym] = {"name": name, "status": status, "avg": avg, "stop": stop, "step": step}
        print(f"  {name}({sym}) status={status} avg={avg} stop={stop} step={step} created={created}")
    if not to:
        print('  (없음)')
except Exception as e:
    print(f'  오류: {e}')

print()
print('=== 불일치 분석 ===')
only_channel = set(ah_syms.keys()) - set(to_syms.keys())
only_trade   = set(to_syms.keys()) - set(ah_syms.keys())
both         = set(ah_syms.keys()) & set(to_syms.keys())

if only_channel:
    print(f"채널에만 있는 종목: {[ah_syms[s]['name']+'('+s+')' for s in only_channel]}")
if only_trade:
    print(f"자동매매에만 있는 종목: {[to_syms[s]['name']+'('+s+')' for s in only_trade]}")
if both:
    print(f"양쪽 모두 있는 종목: {[ah_syms[s]['name']+'('+s+')' for s in both]}")

conn.close()
