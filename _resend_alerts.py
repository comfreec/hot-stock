"""오늘 스캔 실행 + 결과 저장 + 알림 재전송"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from cache_db import load_scan, save_scan, update_alert_status
from telegram_alert import send_scan_alert, send_weekly_summary
import pandas as _pd

# 오늘 저장된 결과 먼저 확인
results = load_scan()
print(f"저장된 스캔 결과: {len(results)}개")

# 없으면 직접 스캔
if not results:
    print("스캔 시작...")
    from stock_surge_detector import KoreanStockSurgeDetector
    det = KoreanStockSurgeDetector(max_gap_pct=10, min_below_days=120, max_cross_days=60)
    results = det.analyze_all_stocks()
    results = [r for r in results if r.get("total_score", 0) >= 15]
    results = sorted(results, key=lambda x: x["total_score"], reverse=True)

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
    print(f"스캔 완료: {len(results)}개 저장")

# 알림 전송
if results:
    send_scan_alert(results, send_charts=True)
    print("스캔 알림 전송 완료")
    update_alert_status()
else:
    print("조건 충족 종목 없음")

# 주간 리포트
send_weekly_summary(force=True)
print("주간 리포트 전송 완료")
