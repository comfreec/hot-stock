"""코인 알림 모듈 테스트"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crypto_surge'))
os.chdir('crypto_surge')

try:
    from telegram_alert import _get_usd_krw, _fmt_krw, send_telegram, send_scan_alert
    print("[1] 모듈 임포트 OK")
except Exception as e:
    print(f"[1] 모듈 임포트 FAIL: {e}")
    sys.exit(1)

# 환율 테스트
try:
    rate = _get_usd_krw()
    print(f"[2] 환율 조회 OK: {rate:.0f}원/USD")
    print(f"    BTC $100 = {_fmt_krw(100, rate)}")
except Exception as e:
    print(f"[2] 환율 조회 FAIL: {e}")

# 텔레그램 연결 테스트
try:
    ok = send_telegram("🧪 [테스트] 코인 알림 모듈 정상 작동 확인\n환율: " + f"{_get_usd_krw():.0f}원/USD")
    print(f"[3] 텔레그램 전송: {'OK' if ok else 'FAIL (토큰/채팅ID 확인 필요)'}")
except Exception as e:
    print(f"[3] 텔레그램 전송 FAIL: {e}")

# 가격 레벨 계산 테스트 (BTC)
try:
    import ccxt
    from telegram_alert import calc_price_levels as _calc
    ex = ccxt.binance({"enableRateLimit": True})
    btc_price = float(ex.fetch_ticker("BTC/USDT")["last"])
    lv = _calc("BTC/USDT", btc_price)
    rate = _get_usd_krw()
    print(f"[4] 가격 레벨 계산 OK:")
    print(f"    현재가: {_fmt_krw(btc_price, rate)}")
    print(f"    매수가: {_fmt_krw(lv['entry'], rate)}")
    print(f"    목표가: {_fmt_krw(lv['target'], rate)} (+{lv['upside']:.1f}%)")
    print(f"    손절가: {_fmt_krw(lv['stop'], rate)} ({lv['downside']:.1f}%)")
    print(f"    손익비: {lv['rr']:.1f}:1")
except Exception as e:
    print(f"[4] 가격 레벨 계산 FAIL: {e}")

os.chdir('..')
print("\n테스트 완료")
