"""텔레그램 알림 3종 테스트"""
import time
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
print(f"현재 시각: {datetime.now(KST).strftime('%H:%M:%S')}")

from telegram_alert import send_telegram, send_scan_alert, send_weekly_summary
import pandas as pd

# 1. 연결 테스트
r1 = send_telegram("✅ <b>[테스트] 연결 확인</b>\n텔레그램 알림 정상 작동 중입니다.")
print(f"1. 연결 테스트: {'성공' if r1 else '실패'}")
time.sleep(2)

# 2. 급등 예고 종목 알림 (샘플)
sample_close = pd.Series(list(range(80000, 80000 + 300, 100)) + [95000]*60)
sample_results = [{
    "symbol": "086520.KQ",
    "name": "에코프로",
    "total_score": 28,
    "current_price": 95000,
    "signals": {"bb_squeeze_expand": True, "macd_cross": True, "ma_align": True},
    "close_series": sample_close,
    "high_series": sample_close * 1.01,
    "low_series": sample_close * 0.99,
    "open_series": sample_close * 1.002,
    "volume_series": pd.Series([500000] * len(sample_close)),
}]
send_scan_alert(sample_results, send_charts=False)
print("2. 급등 예고 알림: 전송 완료")
time.sleep(2)

# 3. 주간 보고서 (force=True 로 요일 무관 강제 전송)
send_weekly_summary(force=True)
print("3. 주간 보고서: 전송 완료")

print("테스트 완료!")
