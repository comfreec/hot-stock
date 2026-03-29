"""
GitHub Actions용 스캔 스크립트 v2.0
- 병렬 처리로 빠른 스캔
- 재무 데이터 포함
- 공시 알림
- 차트 이미지 첨부
"""
import os
import sys
from datetime import date

# 환경변수에서 텔레그램 설정 읽기
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("❌ TELEGRAM_TOKEN 또는 TELEGRAM_CHAT_ID 환경변수 없음")
    sys.exit(1)

import telegram_alert
telegram_alert.TELEGRAM_TOKEN   = TELEGRAM_TOKEN
telegram_alert.TELEGRAM_CHAT_ID = TELEGRAM_CHAT_ID

from stock_surge_detector import KoreanStockSurgeDetector, ALL_SYMBOLS, STOCK_NAMES
from telegram_alert import send_scan_alert, send_telegram

print(f"[{date.today()}] 스캔 시작 (병렬 처리)...")

try:
    det = KoreanStockSurgeDetector(max_gap_pct=15, min_below_days=120, max_cross_days=120)
    results = det.analyze_all_stocks()

    # 최소 종합점수 10점 이상 (앱 최적 셋팅 기본값과 동일)
    results = [r for r in results if r.get("total_score", 0) >= 15]
    results = sorted(results, key=lambda x: x["total_score"], reverse=True)

    print(f"조건 충족 종목: {len(results)}개")

    if results:
        send_scan_alert(results, send_charts=True)
        print("텔레그램 전송 완료 (차트 포함)")
    else:
        send_telegram(f"📊 {date.today()} 장마감\n오늘은 조건을 충족하는 급등 예고 종목이 없습니다.")

except Exception as e:
    print(f"오류: {e}")
    import traceback
    traceback.print_exc()
    send_telegram(f"⚠️ 스캔 오류: {e}")
    sys.exit(1)
