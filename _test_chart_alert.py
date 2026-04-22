import os, sys
os.chdir('/app')
sys.path.insert(0, '/app')
os.environ['DB_PATH'] = '/data/scan_cache.db'

from telegram_alert import make_summary_chart, send_photo, send_telegram
from datetime import date

# 오늘 스캔 결과 로드
from cache_db import load_scan
results = load_scan()

if not results:
    print("오늘 스캔 결과 없음 - 테스트 데이터 사용")
    results = [
        {'name':'애경산업','total_score':110},
        {'name':'셀바스AI','total_score':84},
        {'name':'LX세미콘','total_score':73},
        {'name':'창해에탄올','total_score':65},
        {'name':'카카오페이','total_score':55},
        {'name':'태림포장','total_score':53},
    ]

print(f"종목 {len(results)}개로 차트 생성 중...")
img = make_summary_chart(results)
if img:
    ok = send_photo(img, caption=f"[테스트] {date.today()} 급등 예고 종목 TOP {min(len(results),10)}")
    print("차트 전송:", "OK" if ok else "FAIL")
else:
    print("차트 생성 실패")
    send_telegram("[테스트] 차트 생성 실패")
