"""
텔레그램 알림 모듈
- 급등 예고 종목 자동 알림
- 매수가/목표가/손절가/손익비 포함
"""
import requests
import pandas as pd
import numpy as np
from datetime import date

TELEGRAM_TOKEN   = "8686257393:AAGWPuisi_qy995cKC7pIWnCGqpQMljQxgc"
TELEGRAM_CHAT_ID = "-5204726592"  # 주식 급등 알림 그룹

def send_telegram(message: str):
    """텔레그램 메시지 전송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        return resp.ok
    except:
        return False


def calc_price_levels(symbol: str) -> dict:
    """목표가/손절가/손익비 계산"""
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).history(period="2y")
        df = df.dropna(subset=["Open","High","Low","Close"])
        if len(df) < 30:
            return {}

        close = df["Close"]
        high  = df["High"]
        low   = df["Low"]
        current = float(close.iloc[-1])

        # ATR
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr_s = tr.rolling(14).mean().dropna()
        atr = float(atr_s.iloc[-1]) if len(atr_s) > 0 else current * 0.02

        # 손절가 (Van Tharp)
        swing_low = float(low.tail(20).min())
        ma20 = float(close.rolling(20).mean().dropna().iloc[-1])
        stop = max(swing_low - atr * 1.5, ma20 - atr * 1.0)
        stop = max(stop, current * 0.88)
        stop = min(stop, current * 0.95)
        risk = max(current - stop, current * 0.01)

        # 목표가 (피보나치 + ATR)
        recent_high = float(high.tail(120).max())
        recent_low  = float(low.tail(120).min())
        swing_range = max(recent_high - recent_low, current * 0.01)

        candidates = sorted([
            x for x in [
                recent_low + swing_range * 1.272,
                recent_low + swing_range * 1.618,
                recent_low + swing_range * 2.0,
                recent_high * 1.05,
                current + atr * 3.0,
                current + atr * 5.0,
            ] if x > current * 1.03
        ])

        min_rr3 = current + risk * 3.0
        valid = [x for x in candidates if x >= min_rr3]
        if valid:
            weights = [1 / (x - current) for x in valid]
            target = sum(x * w for x, w in zip(valid, weights)) / sum(weights)
        elif candidates:
            target = candidates[-1]
        else:
            target = current + risk * 3.0

        target = min(target, current * 2.0)
        rr = (target - current) / (current - stop + 1e-9)

        return {
            "current": current,
            "target":  target,
            "stop":    stop,
            "rr":      rr,
            "upside":  (target / current - 1) * 100,
            "downside": (stop / current - 1) * 100,
        }
    except:
        return {}


def format_signals(signals: dict) -> str:
    """활성 신호 포맷"""
    sig_map = {
        "vol_at_cross":          "📦 돌파 거래량",
        "recent_vol":            "📊 거래량 급증",
        "bb_squeeze_expand":     "🔥 BB수축→확장",
        "macd_cross":            "📈 MACD골든크로스",
        "ma240_turning_up":      "🔼 240선 상승전환",
        "ma_align":              "⚡ 이평선 정배열",
        "obv_rising":            "💹 OBV 상승",
        "ichimoku_bull":         "☁️ 일목균형표",
        "near_52w_high":         "🏆 52주 신고가",
        "stoch_cross":           "📉 스토캐스틱",
        "mfi_oversold_recovery": "💰 MFI 반등",
    }
    active = [sig_map[k] for k, v in signals.items() if v is True and k in sig_map]
    return "  ".join(active[:6]) if active else ""


def send_scan_alert(results: list):
    """스캔 결과 텔레그램 전송"""
    if not results:
        return

    today = date.today().strftime("%Y-%m-%d")
    lines = [f"🚀 <b>급등 예고 종목</b> ({today} 장마감)\n{'━'*20}"]

    for i, r in enumerate(results[:10], 1):  # 최대 10개
        lv = calc_price_levels(r["symbol"])
        s  = r.get("signals", {})

        sig_str = format_signals(s)

        entry = f"₩{lv['current']:,.0f}" if lv else f"₩{r['current_price']:,.0f}"
        target_str = f"₩{lv['target']:,.0f}  (+{lv['upside']:.1f}%)" if lv else "-"
        stop_str   = f"₩{lv['stop']:,.0f}  ({lv['downside']:.1f}%)" if lv else "-"
        rr_str     = f"{lv['rr']:.1f} : 1" if lv else "-"

        block = (
            f"\n<b>{i}. {r['name']} ({r['symbol']})</b> ⭐ {r['total_score']}점\n"
            f"📍 매수가:  {entry}\n"
            f"🎯 목표가:  {target_str}\n"
            f"🛑 손절가:  {stop_str}\n"
            f"⚖️ 손익비:  {rr_str}\n"
        )
        if sig_str:
            block += f"{sig_str}\n"
        block += "━" * 20

        lines.append(block)

    lines.append("\n⚠️ 투자 참고용 정보이며 투자 권유가 아닙니다.")
    message = "\n".join(lines)

    # 메시지가 너무 길면 분할 전송
    if len(message) > 4000:
        chunks = [lines[0]]
        for line in lines[1:]:
            if sum(len(c) for c in chunks[-1:]) + len(line) > 3800:
                send_telegram("\n".join(chunks))
                chunks = [line]
            else:
                chunks.append(line)
        if chunks:
            send_telegram("\n".join(chunks))
    else:
        send_telegram(message)


def send_test_alert():
    """테스트 메시지 전송"""
    return send_telegram(
        "✅ <b>HotStock 알림 봇 연결 완료!</b>\n"
        "매일 장 마감 후 급등 예고 종목을 자동으로 알려드립니다. 🚀"
    )
