"""Fly.io 차트 + 가격 레벨 수평선 테스트"""
from telegram_alert import make_chart_image, send_photo, send_telegram, calc_price_levels

symbol = "005930.KS"
name   = "삼성전자"

send_telegram("🧪 가격 레벨 차트 테스트...")

lv = calc_price_levels(symbol)
print("가격 레벨:", lv)

if lv:
    img = make_chart_image(symbol, name, price_levels=lv)
    if img:
        caption = (
            f"<b>{name}</b>\n"
            f"📍 매수가: ₩{lv['entry']:,.0f}\n"
            f"🎯 목표가: ₩{lv['target']:,.0f} (+{lv['upside']:.1f}%)\n"
            f"🛑 손절가: ₩{lv['stop']:,.0f} ({lv['downside']:.1f}%)\n"
            f"⚖️ 손익비: {lv['rr']:.1f}:1"
        )
        result = send_photo(img, caption)
        print(f"전송: {'성공' if result else '실패'}")
    else:
        print("차트 생성 실패")
        send_telegram("❌ 차트 생성 실패")
else:
    print("가격 레벨 계산 실패")
    send_telegram("❌ 가격 레벨 계산 실패")
