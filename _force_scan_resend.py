"""
스캔 강제 재실행 후 채널 재전송
"""
import os, sys
os.chdir('/app')
sys.path.insert(0, '/app')

# /data 볼륨이 있으면 명시적으로 DB 경로 설정
if os.path.isdir('/data'):
    os.environ['DB_PATH'] = '/data/scan_cache.db'

from stock_surge_detector import KoreanStockSurgeDetector
from cache_db import save_scan
from telegram_alert import send_scan_alert, send_telegram
from cache_db import load_app_setting
from datetime import date
import pandas as _pd

print("[재스캔] 시작...")

scan_mode = load_app_setting("scan_mode", "rcycle")
print(f"[재스캔] 전략: {scan_mode}")

det = KoreanStockSurgeDetector(max_gap_pct=7, min_below_days=60, max_cross_days=90)
det._ob_days = 180
det._rc_below = 0

if scan_mode == "classic":
    results = det.analyze_all_stocks_classic()
elif scan_mode == "both":
    r1 = det.analyze_all_stocks()
    r2 = det.analyze_all_stocks_classic()
    seen = {}
    for r in r1 + r2:
        sym = r["symbol"]
        if sym not in seen or r["total_score"] > seen[sym]["total_score"]:
            seen[sym] = r
    results = list(seen.values())
else:
    results = det.analyze_all_stocks()

results = [r for r in results if r.get("total_score", 0) >= 40]
results = sorted(results, key=lambda x: x["total_score"], reverse=True)

print(f"[재스캔] {len(results)}개 종목 발견")
for r in results:
    print(f"  - {r.get('name')} ({r.get('symbol')}) {r.get('total_score')}점")

def _serialize(r):
    out = {}
    for k, v in r.items():
        if isinstance(v, _pd.Series):
            out[k] = v.tolist()
        elif hasattr(v, 'tolist'):
            out[k] = v.tolist()
        else:
            out[k] = v
    return out

save_scan([_serialize(r) for r in results])

if results:
    send_scan_alert(results, send_charts=True)
    print("[재스캔] 채널 전송 완료")
else:
    send_telegram(f"📊 <b>{date.today()} 재스캔 결과</b>\n조건 충족 종목 없음")
    print("[재스캔] 결과 없음 알림 전송")
