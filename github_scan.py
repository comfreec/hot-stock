"""
GitHub Actions용 스캔 스크립트
환경변수에서 텔레그램 토큰/채팅ID 읽어서 알림 전송
"""
import os
import sys

# 환경변수에서 텔레그램 설정 읽기
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("❌ TELEGRAM_TOKEN 또는 TELEGRAM_CHAT_ID 환경변수 없음")
    sys.exit(1)

# telegram_alert.py의 설정 오버라이드
import telegram_alert
telegram_alert.TELEGRAM_TOKEN   = TELEGRAM_TOKEN
telegram_alert.TELEGRAM_CHAT_ID = TELEGRAM_CHAT_ID

from stock_surge_detector import KoreanStockSurgeDetector
from telegram_alert import send_scan_alert, send_telegram
from datetime import date

print(f"[{date.today()}] 스캔 시작...")

try:
    det = KoreanStockSurgeDetector(max_gap_pct=15, min_below_days=60, max_cross_days=90)
    results = det.analyze_all_stocks()

    if results:
        print(f"조건 충족 종목: {len(results)}개")
        send_scan_alert(results)
        print("텔레그램 전송 완료")
    else:
        print("조건 충족 종목 없음")
        send_telegram(f"📊 {date.today()} 장마감\n오늘은 조건을 충족하는 급등 예고 종목이 없습니다.")

except Exception as e:
    print(f"오류: {e}")
    send_telegram(f"⚠️ 스캔 오류: {e}")
    sys.exit(1)
