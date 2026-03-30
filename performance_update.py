"""
성과 추적 업데이트 스크립트
- GitHub Actions 09:10 (KST) 실행
- 매수가 도달 여부 / 목표가 / 손절가 확인 후 텔레그램 알림
"""
import os
import sys

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("❌ TELEGRAM_TOKEN 또는 TELEGRAM_CHAT_ID 환경변수 없음")
    sys.exit(1)

import telegram_alert
telegram_alert.TELEGRAM_TOKEN   = TELEGRAM_TOKEN
telegram_alert.TELEGRAM_CHAT_ID = TELEGRAM_CHAT_ID

from telegram_alert import send_performance_update, send_weekly_summary

print("성과 추적 업데이트 시작...")
send_performance_update()
send_weekly_summary()
print("완료")
