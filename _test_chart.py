"""Fly.io 차트 생성 + 텔레그램 전송 테스트"""
import os
from telegram_alert import make_chart_image, send_photo, send_telegram

symbol = "005930.KS"  # 삼성전자
name   = "삼성전자"

send_telegram("🧪 차트 테스트 시작...")

img = make_chart_image(symbol, name)
if img:
    result = send_photo(img, f"<b>{name}</b> 차트 테스트 ✅")
    print(f"차트 전송: {'성공' if result else '실패'}")
else:
    send_telegram("❌ 차트 생성 실패 (matplotlib/yfinance 문제)")
    print("차트 생성 실패")
