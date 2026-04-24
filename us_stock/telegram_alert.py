"""
미국 주식 텔레그램 알림
- 국내 telegram_alert와 동일한 구조
- 달러 단위 표시
"""
import os
import requests
import pandas as pd
from datetime import date


def _get_config():
    token   = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        try:
            import streamlit as st
            token   = token   or st.secrets.get("TELEGRAM_TOKEN", "")
            chat_id = chat_id or st.secrets.get("TELEGRAM_CHAT_ID", "")
        except Exception:
            pass
    return token, chat_id


def send_telegram(message: str) -> bool:
    token, chat_id = _get_config()
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
        return resp.ok
    except Exception:
        return False


def round_to_cent(price: float) -> float:
    """달러 호가 단위 (소수점 2자리)"""
    return round(price, 2)


def calc_us_levels(close: pd.Series, high: pd.Series, low: pd.Series) -> dict:
    """미국 주식 가격 레벨 계산 (국내와 동일 로직, 달러 단위)"""
    try:
        current = float(close.iloc[-1])

        # ATR(14)
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().dropna().iloc[-1])

        # 매수가: 240일선
        ma240_v = float(close.rolling(240).mean().iloc[-1])
        if pd.isna(ma240_v):
            ma240_v = current
        entry = ma240_v if ma240_v < current else current
        entry_label = "장기선" if ma240_v < current else "현재가"

        # 손절가: RSI(20) 30 돌파 직전 5일 저가
        try:
            _d = close.diff()
            _gain = _d.where(_d > 0, 0.0).ewm(alpha=1/20, min_periods=20, adjust=False).mean()
            _loss = (-_d.where(_d < 0, 0.0)).ewm(alpha=1/20, min_periods=20, adjust=False).mean()
            _rsi = (100 - 100 / (1 + _gain / _loss.replace(0, float('nan')))).fillna(50)
            _rsi_vals = _rsi.values
            _oversold_exit = None
            for _i in range(1, len(_rsi_vals)):
                if _rsi_vals[_i-1] <= 30 and _rsi_vals[_i] > 30:
                    _oversold_exit = _i
            if _oversold_exit is not None:
                _lb = max(0, _oversold_exit - 5)
                stop = float(low.iloc[_lb:_oversold_exit].min())
            else:
                stop = ma240_v * 0.95 if ma240_v < entry else entry * 0.95
        except Exception:
            stop = entry * 0.95
        risk = max(entry - stop, entry * 0.01)

        # 목표가: Fib + ATR + BB 가중평균
        n = len(high)
        recent_high = float(high.tail(120).max()) if n >= 120 else float(high.max())
        recent_low  = float(low.tail(120).min())  if n >= 120 else float(low.min())
        swing_range = max(recent_high - recent_low, entry * 0.01)

        fib_1272 = recent_low + swing_range * 1.272
        fib_1618 = recent_low + swing_range * 1.618
        fib_2000 = recent_low + swing_range * 2.000
        prev_high_ext = recent_high * 1.05
        atr_x3 = entry + atr * 3.0
        atr_x5 = entry + atr * 5.0

        ma20_s  = close.rolling(20).mean()
        std20   = close.rolling(20).std()
        bb_upper = float((ma20_s + std20 * 2.0).dropna().iloc[-1])

        min_rr3 = entry + risk * 3.0
        min_rr2 = entry + risk * 2.0
        all_cands = sorted([x for x in [fib_1272, fib_1618, fib_2000,
                                         recent_high, prev_high_ext,
                                         atr_x3, atr_x5, bb_upper]
                            if x > entry * 1.03])
        valid_3 = [x for x in all_cands if x >= min_rr3]
        valid_2 = [x for x in all_cands if x >= min_rr2]

        if valid_3:
            weights = [1 / (x - entry) for x in valid_3]
            target = sum(x * w for x, w in zip(valid_3, weights)) / sum(weights)
        elif valid_2:
            target = valid_2[-1]
        elif all_cands:
            target = all_cands[-1]
        else:
            target = entry + risk * 3.0

        target = min(target, entry * 2.0)

        # 손익비 2:1 보장
        _risk = max(entry - stop, 0.01)
        if (target - entry) < _risk * 2.0:
            _min_t = entry + _risk * 2.0
            _cands = sorted([x for x in all_cands if x >= _min_t])
            target = _cands[0] if _cands else entry + _risk * 2.0

        entry  = round_to_cent(entry)
        stop   = round_to_cent(stop)
        target = round_to_cent(target)
        rr     = (target - entry) / (max(entry - stop, 0.01) + 1e-9)

        return {
            "current":     current,
            "entry":       entry,
            "entry_label": entry_label,
            "target":      target,
            "stop":        stop,
            "rr":          rr,
            "upside":      (target / entry - 1) * 100,
            "downside":    (stop / entry - 1) * 100,
            "ma240":       round_to_cent(ma240_v),
        }
    except Exception as e:
        print(f"[US레벨계산] 오류: {e}")
        return {}


def send_us_scan_alert(results: list):
    """미국 주식 스캔 결과 텔레그램 전송"""
    if not results:
        return

    today = date.today().strftime("%Y-%m-%d")
    lines = [f"🇺🇸 <b>미국 스윙 레이더</b> ({today} 장마감) — {len(results[:10])}개\n{'━'*20}"]

    for i, r in enumerate(results[:10], 1):
        close_s = r.get("close_series")
        high_s  = r.get("high_series")
        low_s   = r.get("low_series")

        lv = {}
        if close_s is not None and len(close_s) > 20:
            def to_s(v):
                if v is None: return None
                if hasattr(v, 'rolling'): return v
                return pd.Series(list(v))
            lv = calc_us_levels(to_s(close_s), to_s(high_s), to_s(low_s))

        cur = r["current_price"]
        entry_str  = f"${lv['entry']:,.2f}" if lv else f"${cur:,.2f}"
        target_str = f"${lv['target']:,.2f} (+{lv['upside']:.1f}%)" if lv else "-"
        stop_str   = f"${lv['stop']:,.2f} ({lv['downside']:.1f}%)" if lv else "-"
        rr_str     = f"{lv['rr']:.1f} : 1" if lv else "-"

        block = (
            f"\n<b>{i}. {r['name']} ({r['symbol']})</b> ⭐ {r['total_score']}점\n"
            f"📍 매수가:  {entry_str}\n"
            f"🎯 목표가:  {target_str}\n"
            f"🛑 손절가:  {stop_str}\n"
            f"⚖️ 손익비:  {rr_str}\n"
            f"━" * 20
        )
        lines.append(block)

    msg = "\n".join(lines)
    if len(msg) > 4000:
        send_telegram("\n".join(lines[:len(lines)//2]))
        send_telegram("\n".join(lines[len(lines)//2:]))
    else:
        send_telegram(msg)
