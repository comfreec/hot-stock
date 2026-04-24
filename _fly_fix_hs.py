import sqlite3, sys, os
sys.path.insert(0, '/app')
os.environ['DB_PATH'] = '/data/scan_cache.db'
from telegram_alert import calc_price_levels

conn = sqlite3.connect('/data/scan_cache.db')

# 현재 상태 확인
row = conn.execute(
    "SELECT id, symbol, name, entry_price, target_price, stop_price FROM alert_history WHERE symbol='298050.KS' AND status IN ('pending','active')"
).fetchone()
print(f"현재: {row}")

lv = calc_price_levels('298050.KS')
print(f"계산값: target={lv.get('target')}, stop={lv.get('stop')}, rr={lv.get('rr'):.2f}")

conn.execute(
    "UPDATE alert_history SET target_price=?, stop_price=?, rr_ratio=? WHERE symbol='298050.KS' AND status IN ('pending','active')",
    (lv['target'], lv['stop'], lv['rr'])
)
conn.execute(
    "UPDATE trade_orders SET stop_price=? WHERE symbol='298050.KS' AND status IN ('active','pending')",
    (lv['stop'],)
)
conn.commit()
conn.close()
print("HS효성첨단소재 업데이트 완료")
