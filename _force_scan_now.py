"""
스케줄러 상태 무시하고 즉시 스캔 실행
"""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from stock_surge_detector import KoreanStockSurgeDetector
from cache_db import save_scan
from telegram_alert import send_scan_alert
import pandas as pd

det = KoreanStockSurgeDetector(max_gap_pct=7, min_below_days=60, max_cross_days=90)
det._ob_days = 90
det._rc_below = 0

print("강제 스캔 시작...")
results = det.analyze_all_stocks()
results = [r for r in results if r.get("total_score", 0) >= 40]
results = sorted(results, key=lambda x: x["total_score"], reverse=True)

def _serialize(r):
    out = {}
    for k, v in r.items():
        if isinstance(v, pd.Series):
            out[k] = v.tolist()
        elif hasattr(v, 'tolist'):
            out[k] = v.tolist()
        else:
            out[k] = v
    return out

save_scan([_serialize(r) for r in results])

if results:
    send_scan_alert(results, send_charts=True)
    print(f"완료: {len(results)}개 종목 → 텔레그램 전송")
else:
    from telegram_alert import send_telegram
    from datetime import date
    send_telegram(f"📊 {date.today()} 강제 스캔 결과\n조건 충족 종목 없음")
    print("조건 충족 종목 없음")
