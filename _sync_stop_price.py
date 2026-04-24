import os, sys
os.chdir('/app')
sys.path.insert(0, '/app')
os.environ['DB_PATH'] = '/data/scan_cache.db'

from cache_db import _get_conn

conn = _get_conn()
trade_rows = conn.execute(
    "SELECT symbol, avg_price, split_step, stop_price FROM trade_orders WHERE status IN ('active','hit_target','hit_stop') AND avg_price > 0"
).fetchall()
updated = 0
for sym, avg_p, step, stop_p in trade_rows:
    if stop_p:
        conn.execute(
            "UPDATE alert_history SET avg_price=?, split_step=?, stop_price=? WHERE symbol=? AND status IN ('pending','active')",
            (avg_p, step or 1, stop_p, sym)
        )
        updated += 1
        print(f'  {sym}: avg={avg_p} stop={stop_p}')
conn.commit()
conn.close()
print(f'stop_price 동기화: {updated}개')
