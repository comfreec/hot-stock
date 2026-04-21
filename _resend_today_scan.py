"""
오늘 스캔 결과 재전송 (필터 오류로 빈 알림 나간 경우)
"""
from datetime import date
from cache_db import load_scan
from telegram_alert import send_scan_alert

today = date.today().isoformat()
results = load_scan(today)

if not results:
    print(f"[재전송] {today} 스캔 결과 없음")
else:
    print(f"[재전송] {today} 스캔 결과 {len(results)}개 종목")
    for r in results:
        print(f"  - {r.get('name')} ({r.get('symbol')}) {r.get('total_score')}점")
    
    # 채널로 재전송
    send_scan_alert(results, send_charts=True)
    print("[재전송] 텔레그램 전송 완료")
