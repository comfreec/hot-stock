"""
코인 스케줄러 - 24/7 운영
매 4시간마다 스캔 (코인은 장 마감 없음)
UTC 기준 0, 4, 8, 12, 16, 20시 실행
"""
import time
import os
import sys
from datetime import datetime, timezone, timedelta

os.chdir(os.path.dirname(os.path.abspath(__file__)))

UTC = timezone.utc

SCAN_HOURS_UTC = {0, 4, 8, 12, 16, 20}  # 4시간 간격


def log(msg):
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now}] {msg}", flush=True)


def run_scan():
    log("스캔 시작...")
    try:
        from crypto_surge_detector import CryptoSurgeDetector
        from cache_db import save_scan, update_alert_status
        from telegram_alert import send_scan_alert, send_telegram

        det = CryptoSurgeDetector(max_gap_pct=15, min_below_days=60, max_cross_days=45)
        results = det.analyze_all_coins()
        results = [r for r in results if r.get("total_score", 0) >= 10]

        save_scan(results)

        if results:
            send_scan_alert(results, send_charts=True)
            log(f"완료: {len(results)}개 → 텔레그램 전송")
        else:
            try:
                import ccxt
                ex = ccxt.binance()
                btc = ex.fetch_ticker("BTC/USDT")
                btc_price = float(btc["last"])
                btc_chg   = float(btc.get("percentage", 0))
                market_msg = f"₿ BTC ${btc_price:,.0f} ({btc_chg:+.2f}%)"
            except:
                market_msg = "₿ BTC 데이터 없음"

            send_telegram(
                f"🪙 <b>{datetime.now(UTC).strftime('%Y-%m-%d %H:%M')} UTC 스캔 결과</b>\n"
                f"{'━'*20}\n\n"
                f"조건 충족 코인 없음\n\n"
                f"{market_msg}\n"
                f"💡 다음 스캔까지 대기 중..."
            )
            log("조건 충족 코인 없음")

        update_alert_status()

    except Exception as e:
        log(f"오류: {e}")
        import traceback
        traceback.print_exc()


def main():
    log("코인 스케줄러 시작 (4시간 간격)")
    last_run_hour = -1

    while True:
        now = datetime.now(UTC)
        hour = now.hour

        if hour in SCAN_HOURS_UTC and hour != last_run_hour:
            run_scan()
            last_run_hour = hour

        time.sleep(60)


if __name__ == "__main__":
    main()
