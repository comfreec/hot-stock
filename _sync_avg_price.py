import os, sys
os.chdir('/app')
sys.path.insert(0, '/app')
os.environ['DB_PATH'] = '/data/scan_cache.db'

from cache_db import update_alert_status, _get_conn

# trade_orders → alert_history avg_price 강제 동기화
conn = _get_conn()
trade_rows = conn.execute(
    "SELECT symbol, avg_price, split_step FROM trade_orders WHERE status IN ('active','hit_target','hit_stop') AND avg_price > 0"
).fetchall()
updated = 0
for sym, avg_p, step in trade_rows:
    conn.execute(
        "UPDATE alert_history SET avg_price=?, split_step=? WHERE symbol=? AND status IN ('pending','active')",
        (avg_p, step or 1, sym)
    )
    updated += 1
conn.commit()
conn.close()
print(f'avg_price 동기화: {updated}개')

# 상태 업데이트
update_alert_status()
print('update_alert_status 완료')
