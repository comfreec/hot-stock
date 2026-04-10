"""
수동 스캔 실행 스크립트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone
from crypto_surge_detector import CryptoSurgeDetector
from telegram_alert import send_scan_alert, send_telegram
from cache_db import save_scan

print(f"[{datetime.now(timezone.utc)}] 코인 스캔 시작...")

det = CryptoSurgeDetector(max_gap_pct=15, min_below_days=60, max_cross_days=45)
results = det.analyze_all_coins()
results = [r for r in results if r.get("total_score", 0) >= 10]
results.sort(key=lambda x: x["total_score"], reverse=True)

print(f"조건 충족 코인: {len(results)}개")
for r in results:
    print(f"  {r['symbol']:15s} {r['name']:12s} 점수:{r['total_score']:3d} 이격:{r['gap_pct']:.1f}%")

save_scan(results)
print("DB 저장 완료")

if results:
    send_scan_alert(results, send_charts=True)
    print("텔레그램 전송 완료")
