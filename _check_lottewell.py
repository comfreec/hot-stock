"""롯데웰푸드 상태 및 스캔 결과 확인"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
from datetime import date, timedelta
DB = "/data/scan_cache.db"
conn = sqlite3.connect(DB)

print("=== alert_history 롯데웰푸드 ===", flush=True)
rows = conn.execute("""
    SELECT id, alert_date, status, avg_price, entry_price, target_price, stop_price
    FROM alert_history WHERE symbol='280360.KS'
    ORDER BY id DESC
""").fetchall()
for r in rows:
    print(f"  id={r[0]} date={r[1]} status={r[2]} avg={r[3]} entry={r[4]} target={r[5]} stop={r[6]}", flush=True)

print("\n=== trade_orders 롯데웰푸드 ===", flush=True)
rows2 = conn.execute("""
    SELECT id, alert_date, status, avg_price, qty FROM trade_orders WHERE symbol='280360.KS'
""").fetchall()
if rows2:
    for r in rows2:
        print(f"  id={r[0]} date={r[1]} status={r[2]} avg={r[3]} qty={r[4]}", flush=True)
else:
    print("  없음 (자동매매 주문 미진입)", flush=True)

print("\n=== 최근 스캔 결과에 롯데웰푸드 포함 여부 ===", flush=True)
from cache_db import load_scan, list_scan_dates
dates = list_scan_dates()
print(f"저장된 스캔 날짜: {[d['date'] for d in dates[:5]]}", flush=True)
for d in dates[:3]:
    results = load_scan(d['date'])
    syms = [r.get('symbol') for r in results]
    if '280360.KS' in syms:
        r = next(r for r in results if r.get('symbol') == '280360.KS')
        print(f"  {d['date']}: ✅ 포함 (점수={r.get('total_score')})", flush=True)
    else:
        print(f"  {d['date']}: 없음", flush=True)

conn.close()
