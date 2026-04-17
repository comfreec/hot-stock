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
    det = KoreanStockSurgeDetector(max_gap_pct=10, min_below_days=60, max_cross_days=90)
    results = det.analyze_all_stocks()
    results = [r for r in results if r.get("total_score", 0) >= 15]

    # 최소 종합점수 10점 이상 (앱 최적 셋팅 기본값과 동일)
    results = [r for r in results if r.get("total_score", 0) >= 15]
    results = sorted(results, key=lambda x: x["total_score"], reverse=True)

    print(f"조건 충족 종목: {len(results)}개")

    if results:
        send_scan_alert(results, send_charts=True)
        print("텔레그램 전송 완료 (차트 포함)")
    else:
        # 종목 없을 때 이유 분석해서 전송
        import yfinance as yf
        import pandas as pd

        reasons = []

        # 1. 시장 상태 확인
        try:
            kospi = yf.Ticker("^KS11").history(period="1y").dropna(subset=["Close"])
            kospi_cur   = float(kospi["Close"].iloc[-1])
            kospi_prev  = float(kospi["Close"].iloc[-2])
            kospi_chg   = (kospi_cur - kospi_prev) / kospi_prev * 100
            kospi_ma200 = float(kospi["Close"].rolling(200).mean().iloc[-1])
            kospi_ma60  = float(kospi["Close"].rolling(60).mean().iloc[-1])

            if kospi_cur < kospi_ma200 * 0.97:
                reasons.append(f"📉 KOSPI 하락장 ({kospi_cur:,.0f} / 200일선 {kospi_ma200:,.0f} 아래)")
            elif kospi_chg < -1.5:
                reasons.append(f"📉 KOSPI 당일 급락 ({kospi_chg:.1f}%)")
            else:
                reasons.append(f"📊 KOSPI {kospi_cur:,.0f} ({kospi_chg:+.2f}%)")
        except:
            pass

        # 2. 조건 설명
        reasons.append(f"🔍 스캔 조건: 240선 돌파 후 {det.max_cross_days}일 이내 + 이격 {det.max_gap_pct}% 이내 + 조정 {det.min_below_days}일+")
        reasons.append(f"📋 추가 필터: 거래대금 50억+ / 손익비 2.5:1+ / 핵심신호 2개+ / 종합점수 15점+")
        reasons.append(f"💡 조건이 엄격해 해당 종목이 없습니다. 내일 다시 확인하세요.")

        msg = f"📊 <b>{date.today()} 장마감 스캔 결과</b>\n{'━'*20}\n\n"
        msg += "오늘 급등 예고 종목 없음\n\n"
        msg += "\n".join(reasons)
        send_telegram(msg)

    # ── 기존 알림 종목 성과 상태 DB 업데이트만 (알림은 09:10에 별도 전송) ──
    try:
        from cache_db import update_alert_status
        update_alert_status()
        print("성과 추적 DB 업데이트 완료")
    except Exception as e:
        print(f"성과 추적 오류: {e}")

except Exception as e:
    print(f"오류: {e}")
    import traceback
    traceback.print_exc()
    send_telegram(f"⚠️ 스캔 오류: {e}")
    sys.exit(1)
