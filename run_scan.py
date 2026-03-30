"""
로컬 자동 실행용 스캔 스크립트
Windows 작업 스케줄러로 매일 KST 15:40에 실행
"""
import sys
import os

# 스크립트 위치 기준으로 경로 설정
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from stock_surge_detector import KoreanStockSurgeDetector
from telegram_alert import send_scan_alert, send_telegram
from cache_db import update_alert_status

print(f"[{date.today()}] 스캔 시작...")

try:
    det = KoreanStockSurgeDetector(max_gap_pct=10, min_below_days=120, max_cross_days=60)
    results = det.analyze_all_stocks()
    results = [r for r in results if r.get("total_score", 0) >= 15]
    results = sorted(results, key=lambda x: x["total_score"], reverse=True)

    print(f"조건 충족 종목: {len(results)}개")

    # DB 저장 (앱에서 캐시로 사용)
    try:
        from cache_db import save_scan
        import pandas as _pd
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
        print(f"DB 저장 완료 ({len(results)}개)")
    except Exception as e:
        print(f"DB 저장 오류: {e}")

    if results:
        send_scan_alert(results, send_charts=True)
        print("텔레그램 전송 완료")
    else:
        import yfinance as yf
        try:
            kospi = yf.Ticker("^KS11").history(period="1y").dropna(subset=["Close"])
            kospi_cur  = float(kospi["Close"].iloc[-1])
            kospi_prev = float(kospi["Close"].iloc[-2])
            kospi_chg  = (kospi_cur - kospi_prev) / kospi_prev * 100
            market_msg = f"📊 KOSPI {kospi_cur:,.0f} ({kospi_chg:+.2f}%)"
        except:
            market_msg = "📊 KOSPI 데이터 없음"

        send_telegram(
            f"📊 <b>{date.today()} 장마감 스캔 결과</b>\n"
            f"{'━'*20}\n\n"
            f"오늘 급등 예고 종목 없음\n\n"
            f"{market_msg}\n"
            f"💡 조건 충족 종목이 없습니다."
        )

    # 성과 추적 업데이트
    update_alert_status()
    print("성과 추적 업데이트 완료")

except Exception as e:
    print(f"오류: {e}")
    import traceback
    traceback.print_exc()
    send_telegram(f"⚠️ 스캔 오류: {e}")
