"""
?”ë ˆê·¸ë¨ ?Œë¦¼ ëª¨ë“ˆ v2.0
- ê¸‰ë“± ?ˆê³  ì¢…ëª© ?ë™ ?Œë¦¼
- ë§¤ìˆ˜ê°€/ëª©í‘œê°€/?ì ˆê°€/?ìµë¹??¬í•¨
- ìº”ë“¤ì°¨íŠ¸ ?´ë?ì§€ ì²¨ë?
- ?¬ë¬´ ?°ì´??(PER/PBR)
"""
import requests
import pandas as pd
import numpy as np
import io
from datetime import date

import os

def _get_telegram_config():
    """?˜ê²½ë³€????Streamlit secrets ?œìœ¼ë¡??”ë ˆê·¸ë¨ ?¤ì • ë¡œë“œ"""
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

TELEGRAM_TOKEN, TELEGRAM_CHAT_ID = _get_telegram_config()

def send_telegram(message: str) -> bool:
    token, chat_id = _get_telegram_config()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        return resp.ok
    except:
        return False


def send_photo(image_bytes: bytes, caption: str = "") -> bool:
    """?´ë?ì§€ ?„ì†¡"""
    token, chat_id = _get_telegram_config()
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        resp = requests.post(url, data={
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "HTML"
        }, files={"photo": ("chart.png", image_bytes, "image/png")}, timeout=30)
        return resp.ok
    except:
        return False


def make_chart_image(symbol: str, name: str, price_levels: dict = None, df=None) -> bytes | None:
    """ìº”ë“¤ì°¨íŠ¸ + 240?¼ì„  + ëª©í‘œê°€/?ì ˆê°€ ?˜í‰???´ë?ì§€ ?ì„±"""
    try:
        import yfinance as yf
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if df is None:
            df = yf.Ticker(symbol).history(period="6mo", auto_adjust=False)
            df = df.dropna(subset=["Open","High","Low","Close"])
            if len(df) < 20:
                return None
            df2y = yf.Ticker(symbol).history(period="2y", auto_adjust=False).dropna(subset=["Close"])
            ma240_full = df2y["Close"].rolling(240).mean()
        else:
            df = df.dropna(subset=["Open","High","Low","Close"]).tail(120)
            if len(df) < 20:
                return None
            # dfê°€ ì§§ìœ¼ë©?2y ?°ì´?°ë¡œ MA240 ê³„ì‚°
            try:
                df2y = yf.Ticker(symbol).history(period="2y", auto_adjust=False).dropna(subset=["Close"])
                ma240_full = df2y["Close"].rolling(240).mean()
            except Exception:
                ma240_full = df["Close"].rolling(240).mean()

        ma240 = ma240_full.reindex(df.index)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7),
                                        gridspec_kw={"height_ratios": [3, 1]},
                                        facecolor="#0e1117")
        ax1.set_facecolor("#0e1117")
        ax2.set_facecolor("#0e1117")

        # Heikin-Ashi ê³„ì‚°
        ha_close = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4
        ha_open = ha_close.copy()
        for i in range(1, len(ha_open)):
            ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
        ha_high = pd.concat([df["High"], ha_open, ha_close], axis=1).max(axis=1)
        ha_low  = pd.concat([df["Low"],  ha_open, ha_close], axis=1).min(axis=1)

        # Heikin-Ashi ìº”ë“¤ì°¨íŠ¸
        for i in range(len(df)):
            color = "#ff3355" if ha_close.iloc[i] >= ha_open.iloc[i] else "#4f8ef7"
            ax1.plot([i, i], [ha_low.iloc[i], ha_high.iloc[i]], color=color, linewidth=0.8)
            ax1.bar(i, abs(ha_close.iloc[i] - ha_open.iloc[i]),
                    bottom=min(ha_open.iloc[i], ha_close.iloc[i]),
                    color=color, width=0.6, alpha=0.9)

        close = df["Close"]
        x = range(len(df))
        ax1.plot(x, close.rolling(20).mean().values, color="#ffd700", linewidth=1.2, label="MA20")
        ax1.plot(x, close.rolling(60).mean().values, color="#ff8c42", linewidth=1.2, label="MA60")
        if ma240.notna().any():
            ax1.plot(x, ma240.values, color="#ff4b6e", linewidth=2.0, label="MA240")

        current = float(close.iloc[-1])

        # ?€?€ ëª©í‘œê°€ / ?„ì¬ê°€ / ?ì ˆê°€ ?˜í‰???€?€
        if price_levels:
            target  = price_levels.get("target")
            stop    = price_levels.get("stop")
            entry   = price_levels.get("entry", current)
            entry_label = price_levels.get("entry_label", "ë§¤ìˆ˜")
            upside  = price_levels.get("upside", 0)
            downside = price_levels.get("downside", 0)

            if target:
                ax1.axhline(y=target, color="#00ff88", linewidth=1.5, linestyle="--", alpha=0.9)
                ax1.text(len(df)-1, target, f" Target ??target:,.0f} (+{upside:.1f}%)",
                         color="#00ff88", fontsize=7, va="bottom", ha="right")
                ax1.axhspan(entry, target, alpha=0.05, color="#00ff88")

            # ë§¤ìˆ˜ê°€ (240??ê·¼ê±°)
            if entry < current:
                label_en = {"240??: "MA240", "240??ë²„í¼": "MA240", "MA20": "MA20", "?¤ìœ™?€??: "SwingLow", "?„ì¬ê°€": "Close"}.get(entry_label, entry_label)
                ax1.axhline(y=entry, color="#ffd700", linewidth=1.5, linestyle="-.", alpha=0.9)
                ax1.text(len(df)-1, entry, f" Buy ??entry:,.0f}",
                         color="#ffd700", fontsize=7, va="bottom", ha="right")

            ax1.axhline(y=current, color="#ffffff", linewidth=1.0, linestyle="--", alpha=0.6)
            ax1.text(len(df)-1, current, f" Close ??current:,.0f}",
                     color="#ffffff", fontsize=7, va="bottom", ha="right")

            if stop:
                ax1.axhline(y=stop, color="#ff3355", linewidth=1.5, linestyle="--", alpha=0.9)
                ax1.text(len(df)-1, stop, f" Stop ??stop:,.0f} ({downside:.1f}%)",
                         color="#ff3355", fontsize=7, va="top", ha="right")
                ax1.axhspan(stop, entry, alpha=0.05, color="#ff3355")
        else:
            ax1.axhline(y=current, color="#ffffff", linewidth=0.8, linestyle="--", alpha=0.5)

        ax1.set_title(f"{symbol}", color="#e0e6f0", fontsize=12, pad=8)
        ax1.tick_params(colors="#8b92a5", labelsize=8)
        ax1.spines[:].set_color("#2d3555")
        ax1.yaxis.set_label_position("right")
        ax1.yaxis.tick_right()
        ax1.legend(loc="upper left", fontsize=7, facecolor="#1a1f35",
                   labelcolor="#8b92a5", edgecolor="#2d3555")

        # ê±°ë˜??
        vol = df["Volume"]
        vol_colors = ["#ff3355" if df["Close"].iloc[i] >= df["Open"].iloc[i]
                      else "#4f8ef7" for i in range(len(df))]
        ax2.bar(x, vol.values, color=vol_colors, alpha=0.7, width=0.6)
        ax2.plot(x, vol.rolling(20).mean().values, color="#ffd700", linewidth=1.0)
        ax2.tick_params(colors="#8b92a5", labelsize=7)
        ax2.spines[:].set_color("#2d3555")
        ax2.yaxis.set_label_position("right")
        ax2.yaxis.tick_right()
        ax2.set_ylabel("Vol", color="#8b92a5", fontsize=7)

        step = max(1, len(df) // 6)
        ax1.set_xticks([])
        ax2.set_xticks(range(0, len(df), step))
        ax2.set_xticklabels(
            [df.index[i].strftime("%m/%d") for i in range(0, len(df), step)],
            color="#8b92a5", fontsize=7
        )

        plt.tight_layout(pad=0.5)
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#0e1117")
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        print(f"ì°¨íŠ¸ ?ì„± ?¤íŒ¨ {symbol}: {e}")
        return None


def _get_korean_font():
    """?œê? ?°íŠ¸ ë°˜í™˜ (?†ìœ¼ë©?None)"""
    try:
        from matplotlib import font_manager
        for name in ["Malgun Gothic", "NanumGothic", "AppleGothic", "NotoSansCJK"]:
            try:
                return font_manager.FontProperties(family=name)
            except:
                pass
    except:
        pass
    return None


def round_to_tick(price: float) -> int:
    """?œêµ­ ì£¼ì‹ ?¸ê? ?¨ìœ„ë¡?ë°˜ì˜¬ë¦?""
    if price < 2000:      tick = 1
    elif price < 5000:    tick = 5
    elif price < 20000:   tick = 10
    elif price < 50000:   tick = 50
    elif price < 200000:  tick = 100
    elif price < 500000:  tick = 500
    else:                 tick = 1000
    return int(round(price / tick) * tick)


def get_financial_data(symbol: str) -> dict:
    """?¬ë¬´ ?°ì´??(PER, PBR) ì¡°íšŒ"""
    try:
        import yfinance as yf
        info = yf.Ticker(symbol).info
        per = info.get("trailingPE") or info.get("forwardPE")
        pbr = info.get("priceToBook")
        eps = info.get("trailingEps")
        return {
            "per": round(per, 1) if per and per > 0 else None,
            "pbr": round(pbr, 2) if pbr and pbr > 0 else None,
            "eps": round(eps, 0) if eps else None,
        }
    except:
        return {}


def _calc_levels_core(close, high, low) -> dict:
    """
    ê³µí†µ ê°€ê²??ˆë²¨ ê³„ì‚° ì½”ì–´ (app.py make_candleê³??„ì „ ?™ì¼ ë¡œì§)
    close/high/low: pd.Series
    ë°˜í™˜: entry, entry_label, stop, target, rr, upside, downside, ma240_v, ma1000_v
    """
    current = float(close.iloc[-1])

    # ATR(14)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr_s = tr.rolling(14).mean().dropna()
    atr = float(atr_s.iloc[-1]) if len(atr_s) > 0 else float((high - low).mean())

    # ë§¤ìˆ˜ê°€: 240?¼ì„ 
    ma240_s  = close.rolling(240).mean()
    ma1000_s = close.rolling(1000).mean()
    ma240_v  = float(ma240_s.iloc[-1])  if not pd.isna(ma240_s.iloc[-1])  else None
    ma1000_v = float(ma1000_s.iloc[-1]) if not pd.isna(ma1000_s.iloc[-1]) else None

    if ma240_v and ma240_v < current:
        entry_label, entry = "?¥ê¸°??, ma240_v
    else:
        entry_label, entry = "?„ì¬ê°€", current

    # ?ì ˆê°€: RSI(20) 30 ?ŒíŒŒ ì§ì „ 5???€ê°€
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
            stop = ma240_v * 0.95 if (ma240_v and ma240_v < entry) else entry * 0.95
    except Exception:
        stop = ma240_v * 0.95 if (ma240_v and ma240_v < entry) else entry * 0.95
    risk = max(entry - stop, entry * 0.01)

    # ëª©í‘œê°€: ?¤ì¤‘ ê¸°ë²• (Fib Ã— ATR Ã— BB Ã— ?€??„  ê°€ì¤‘í‰ê·?
    n = len(high)
    recent_high = float(high.tail(120).max()) if n >= 120 else float(high.max())
    recent_low  = float(low.tail(120).min())  if n >= 120 else float(low.min())
    high_52w    = float(high.tail(252).max()) if n >= 252 else float(high.max())
    swing_range = max(recent_high - recent_low, entry * 0.01)

    # ?¼ë³´?˜ì¹˜ ?•ì¥ (?¤ìœ™ ?€??ê¸°ì?)
    fib_1272 = recent_low + swing_range * 1.272
    fib_1618 = recent_low + swing_range * 1.618
    fib_2000 = recent_low + swing_range * 2.000
    fib_2618 = recent_low + swing_range * 2.618  # ì¶”ê?: ê³µê²©??ëª©í‘œ

    # ê³ ì  ê¸°ë°˜ ?€??„ 
    prev_high_ext  = recent_high * 1.05   # ì§ì „ ê³ ì  ?ŒíŒŒ +5%
    prev_high_ext2 = recent_high * 1.10   # ì§ì „ ê³ ì  ?ŒíŒŒ +10%
    high_52w_ext   = high_52w * 1.03      # 52ì£?ê³ ì  ?ŒíŒŒ +3%

    # ATR ë©€?°í”Œ
    atr_x3 = entry + atr * 3.0
    atr_x5 = entry + atr * 5.0

    # ë³¼ë¦°?€ë°´ë“œ ?ë‹¨
    ma20_s  = close.rolling(20).mean()
    std20   = close.rolling(20).std()
    bb_upper = float((ma20_s + std20 * 2.0).dropna().iloc[-1])

    min_rr3 = entry + risk * 3.0
    min_rr2 = entry + risk * 2.0
    all_cands = sorted([x for x in [fib_1272, fib_1618, fib_2000, fib_2618,
                                     recent_high, prev_high_ext, prev_high_ext2,
                                     high_52w_ext, atr_x3, atr_x5, bb_upper]
                        if x > entry * 1.03])
    valid_3 = [x for x in all_cands if x >= min_rr3]
    valid_2 = [x for x in all_cands if x >= min_rr2]

    if valid_3:
        # ?ìµë¹?3:1 ?´ìƒ ?„ë³´?¤ì˜ ê°€ì¤‘í‰ê·?(ê°€ê¹Œìš¸?˜ë¡ ê°€ì¤‘ì¹˜ ?’ìŒ)
        weights = [1 / (x - entry) for x in valid_3]
        target = sum(x * w for x, w in zip(valid_3, weights)) / sum(weights)
    elif valid_2:
        target = valid_2[-1]
    elif all_cands:
        target = all_cands[-1]
    else:
        target = entry + risk * 3.0

    target = min(target, entry * 2.5)  # ?í•œ 150% (ê¸°ì¡´ 100%?ì„œ ?„í™”)

    # ?¸ê? ?¨ìœ„
    entry  = round_to_tick(entry)
    stop   = round_to_tick(stop)
    target = round_to_tick(target)

    # ?€?€ ?ìµë¹?2:1 ìµœì†Œ ë³´ì¥ ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
    # ê³„ì‚°??ëª©í‘œê°€ë¡??ìµë¹„ê? 2:1 ë¯¸ë§Œ?´ë©´ ê·¼ê±° ?ˆëŠ” ìµœì†Œ ëª©í‘œê°€ë¡?ë³´ì •
    _risk = max(entry - stop, 1)
    if (target - entry) < _risk * 2.0:
        # ?„ë³´ ì¤??ìµë¹?2:1 ?´ìƒ??ê°€??ê°€ê¹Œìš´ ê°??¬íƒ??(?í•œ ?œê±°)
        _min_t = entry + _risk * 2.0
        _cands_no_cap = sorted([x for x in [fib_1272, fib_1618, fib_2000,
                                             recent_high, prev_high_ext,
                                             atr_x3, atr_x5, bb_upper]
                                if x >= _min_t])
        if _cands_no_cap:
            target = round_to_tick(_cands_no_cap[0])  # ê°€??ê°€ê¹Œìš´ ê·¼ê±° ?ˆëŠ” ëª©í‘œê°€
        else:
            target = round_to_tick(entry + _risk * 2.0)  # ìµœí›„ ?˜ë‹¨: ?•í™•??2:1

    rr = (target - entry) / (max(entry - stop, 1) + 1e-9)

    return {
        "current":     current,
        "entry":       entry,
        "entry_label": entry_label,
        "target":      target,
        "stop":        stop,
        "rr":          rr,
        "upside":      (target / entry - 1) * 100,
        "downside":    (stop / entry - 1) * 100,
        "ma240":       round_to_tick(ma240_v)  if ma240_v  else entry,
        "ma1000":      round_to_tick(ma1000_v) if ma1000_v else None,
    }


def calc_price_levels(symbol: str) -> dict:
    """ëª©í‘œê°€/?ì ˆê°€/?ìµë¹?ê³„ì‚° (yfinance ?¬í˜¸ì¶?"""
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).history(period="5y", auto_adjust=False)
        df = df.dropna(subset=["Open","High","Low","Close"])
        if len(df) < 30:
            return {}
        return _calc_levels_core(df["Close"], df["High"], df["Low"])
    except Exception as e:
        print(f"[calc_price_levels] {symbol} ?¤ë¥˜: {e}")
        import traceback; traceback.print_exc()
        return {}


def _calc_levels_from_result(r: dict) -> dict:
    """?¤ìº” ê²°ê³¼?ì„œ ì§ì ‘ ê°€ê²??ˆë²¨ ê³„ì‚° (yfinance ?¬í˜¸ì¶??†ìŒ)"""
    try:
        def to_s(v):
            if v is None: return None
            if hasattr(v, 'rolling'): return v
            return pd.Series(list(v))

        close_s = to_s(r.get("close_series"))
        high_s  = to_s(r.get("high_series"))
        low_s   = to_s(r.get("low_series"))

        if close_s is None or len(close_s) < 20:
            return {}

        high_s = high_s if high_s is not None else close_s
        low_s  = low_s  if low_s  is not None else close_s

        return _calc_levels_core(close_s, high_s, low_s)
    except Exception as e:
        print(f"[_calc_levels_from_result] {r.get('symbol')} ?¤ë¥˜: {e}")
        import traceback; traceback.print_exc()
        return {}


def format_signals(signals: dict) -> str:
    sig_map = {
        "rsi_cycle_pullback":    "?”„ RSI?¬ì´?´ëˆŒë¦¼ëª©",
        "vol_at_cross":          "?“¦ ?ŒíŒŒ ê±°ë˜??,
        "recent_vol":            "?“Š ê±°ë˜??ê¸‰ì¦",
        "bb_squeeze_expand":     "?”¥ BB?˜ì¶•?’í™•??,
        "macd_cross":            "?“ˆ MACDê³¨ë“ ?¬ë¡œ??,
        "ma240_turning_up":      "?”¼ ?¥ê¸°???ìŠ¹?„í™˜",
        "ma_align":              "???´í‰???•ë°°??,
        "obv_rising":            "?’¹ OBV ?ìŠ¹",
        "ichimoku_bull":         "?ï¸ ?¼ëª©ê· í˜•??,
        "near_52w_high":         "?† 52ì£?? ê³ ê°€",
        "stoch_cross":           "?“‰ ?¤í† ìºìŠ¤??,
        "mfi_oversold_recovery": "?’° MFI ë°˜ë“±",
    }
    active = [sig_map[k] for k, v in signals.items() if v is True and k in sig_map]
    return "  ".join(active[:6]) if active else ""


def make_summary_chart(results: list) -> bytes | None:
    """ê¸‰ë“± ?ˆê³  ì¢…ëª© ?ìˆ˜ ?”ì•½ ì°¨íŠ¸ - ?¤í¬ ?Œë§ˆ ê³ ê¸‰ ?”ì??""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib import font_manager
        import numpy as np

        # ?œê? ?°íŠ¸ ?¤ì •
        import os
        font_paths = [
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "C:/Windows/Fonts/malgun.ttf",
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                font_manager.fontManager.addfont(fp)
                plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
                break
        plt.rcParams["axes.unicode_minus"] = False

        top = sorted(results, key=lambda x: x["total_score"], reverse=True)[:10]
        names  = [r["name"] for r in top]
        scores = [r["total_score"] for r in top]
        n = len(names)

        # ?€?€ ìº”ë²„???¤ì • ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
        fig_h = max(5, n * 0.72 + 3.2)
        fig, ax = plt.subplots(figsize=(10, fig_h))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#0d1117")

        # ?€?€ ê·¸ë¼?°ì´???‰ìƒ (?ìˆ˜ ?’ì„?˜ë¡ ë°ì? ê³¨ë“œ) ?€?€?€?€?€?€?€?€?€?€
        max_s = max(scores) if scores else 1
        colors = []
        for s in scores:
            ratio = s / max_s
            if ratio >= 0.85:
                colors.append("#FFD700")
            elif ratio >= 0.65:
                colors.append("#4f8ef7")
            elif ratio >= 0.45:
                colors.append("#00d4aa")
            else:
                colors.append("#6b7280")

        y_pos = np.arange(n)[::-1]

        # ?€?€ ë°°ê²½ ê·¸ë¦¬???€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
        ax.set_xlim(0, max_s * 1.18)
        ax.set_ylim(-0.6, n - 0.4)
        for x in np.linspace(0, max_s * 1.15, 6):
            ax.axvline(x, color="#1e2433", linewidth=0.8, zorder=0)

        # ?€?€ ë§‰ë? ê·¸ë˜???€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
        bars = ax.barh(y_pos, scores, height=0.72, color=colors,
                       alpha=0.88, zorder=3, edgecolor="none")

        # ?€?€ ë§‰ë? ?ˆì— ì¢…ëª©ëª?+ ?ìˆ˜ ?ìŠ¤???€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
        for i, (name, s, c, bar) in enumerate(zip(names, scores, colors, bars)):
            bar_w = bar.get_width()
            ax.text(bar_w * 0.04, y_pos[i], name,
                    va="center", ha="left",
                    fontsize=28, fontweight="bold",
                    color="#0d1117", zorder=5)
            ax.text(bar_w + max_s * 0.012, y_pos[i], f"{s}??,
                    va="center", ha="left",
                    fontsize=26, fontweight="bold",
                    color=c, zorder=5)

        # ?€?€ ?œìœ„ ë±ƒì? (ë§‰ë? ?¼ìª½) ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
        medals = {0: "1", 1: "2", 2: "3"}
        medal_bg = {0: "#FFD700", 1: "#C0C0C0", 2: "#CD7F32"}
        for i in range(min(3, n)):
            circle = plt.Circle((-max_s * 0.055, y_pos[i]), 0.22,
                                 color=medal_bg[i], zorder=6)
            ax.add_patch(circle)
            ax.text(-max_s * 0.055, y_pos[i], medals[i],
                    va="center", ha="center", fontsize=9,
                    fontweight="bold", color="#0d1117", zorder=7)

        # ?€?€ Yì¶??¨ê? ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
        ax.set_yticks([])
        ax.set_yticklabels([])

        # ?€?€ Xì¶??¤í????€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
        ax.set_xlabel("ì¢…í•© ?ìˆ˜", color="#6b7280", fontsize=10, labelpad=8)
        ax.tick_params(axis="x", colors="#4a5568", labelsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color("#1e2433")

        # ?€?€ ?€?´í? ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
        today_str = date.today().strftime("%Y.%m.%d")
        fig.text(0.5, 0.98, "J.A.R.V.I.S.  SWING RADAR",
                 ha="center", va="top",
                 fontsize=36, fontweight="bold", color="#f0f4ff")
        fig.text(0.5, 0.89, f"ê¸‰ë“± ?ˆê³  ì¢…ëª©  TOP {n}   |   {today_str}",
                 ha="center", va="top",
                 fontsize=24, color="#a0b4d0", style="italic")

        # ?€?€ ?˜ë‹¨ ?Œí„°ë§ˆí¬ ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
        fig.text(0.98, 0.01, "SWING RADAR  |  ë§¤ì¼ 15:40 ?ë™ ë¶„ì„",
                 ha="right", va="bottom",
                 fontsize=7.5, color="#2d3555", style="italic")

        plt.tight_layout(rect=[0.04, 0.02, 1, 0.86])

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=200,
                    facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        print(f"[?”ì•½ì°¨íŠ¸] ?ì„± ?¤ë¥˜: {e}")
        return None


def send_scan_alert(results: list, send_charts: bool = True):
    """?¤ìº” ê²°ê³¼ ?”ë ˆê·¸ë¨ ?„ì†¡ (ì°¨íŠ¸ ?´ë?ì§€ ?¬í•¨)"""
    if not results:
        return

    today = date.today().strftime("%Y-%m-%d")

    # ?€?€ ?”ì•½ ì°¨íŠ¸ ë¨¼ì? ?„ì†¡ ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
    summary_img = make_summary_chart(results)
    if summary_img:
        send_photo(summary_img, caption=f"?“¡ {today} ê¸‰ë“± ?ˆê³  ì¢…ëª© TOP {min(len(results),10)}")

    # ?”ì•½ ë©”ì‹œì§€ ë¨¼ì? ?„ì†¡
    # ? ê·œ / ì¶”ì  ì¤?ë¶„ë¥˜
    new_items = []
    tracking_items = []

    for r in results[:10]:
        lv = _calc_levels_from_result(r)
        already_tracking = False
        try:
            from cache_db import _get_conn as _db_conn
            _conn = _db_conn()
            # ?¤ëŠ˜ ?´ì „???Œë¦¼ ë³´ë‚¸ ???ˆê³  ?„ì§ ì§„í–‰ ì¤‘ì¸ ì¢…ëª© = ì¶”ì  ì¤?
            _row = _conn.execute(
                "SELECT entry_price, target_price, stop_price, rr_ratio FROM alert_history "
                "WHERE symbol=? AND status IN ('pending','active') AND alert_date < ? "
                "ORDER BY id DESC LIMIT 1",
                (r["symbol"], date.today().isoformat())
            ).fetchone()
            if _row and _row[0]:
                lv = {"entry": _row[0], "target": _row[1], "stop": _row[2], "rr": _row[3],
                      "upside": (_row[1]/_row[0]-1)*100 if _row[0] else 0,
                      "downside": (_row[2]/_row[0]-1)*100 if _row[0] else 0}
                # rr_ratio ?¤ì‹œê°??¬ê³„??(?ì ˆê°€ ?…ë°?´íŠ¸ ??DB ê°’ê³¼ ?¤ë? ???ˆìŒ)
                if _row[0] and _row[1] and _row[2]:
                    _risk = max(_row[0] - _row[2], 1)
                    lv["rr"] = (_row[1] - _row[0]) / _risk
                already_tracking = True
        except Exception:
            pass
        if already_tracking:
            tracking_items.append((r, lv))
        else:
            new_items.append((r, lv))

    def _make_block(r, lv, idx):
        fin = get_financial_data(r["symbol"])
        s   = r.get("signals", {})
        sig_str = format_signals(s)
        entry_str  = f"??lv['entry']:,.0f}" if lv else f"??r['current_price']:,.0f}"
        target_str = f"??lv['target']:,.0f} (+{lv['upside']:.1f}%)" if lv else "-"
        stop_str   = f"??lv['stop']:,.0f} ({lv['downside']:.1f}%)" if lv else "-"
        rr_str     = f"{lv['rr']:.1f} : 1" if lv else "-"
        per_str = f"PER {fin['per']}" if fin.get("per") else ""
        pbr_str = f"PBR {fin['pbr']}" if fin.get("pbr") else ""
        fin_str = "  ".join(filter(None, [per_str, pbr_str]))
        block = (
            f"\n<b>{idx}. {r['name']} ({r['symbol']})</b> â­?{r['total_score']}??n"
            f"?“ ë§¤ìˆ˜ê°€:  {entry_str}\n"
            f"?¯ ëª©í‘œê°€:  {target_str}\n"
            f"?›‘ ?ì ˆê°€:  {stop_str}\n"
            f"?–ï¸ ?ìµë¹?  {rr_str}\n"
        )
        if fin_str:
            block += f"?“Š {fin_str}\n"
        if sig_str:
            block += f"{sig_str}\n"
        block += "?? * 20
        return block

    summary_lines = [f"?“¡ <b>?¤ìœ™ ?ˆì´??/b> ({today} ?¥ë§ˆê°? ??{len(results[:10])}ê°?n{'??*20}"]

    idx = 1
    if new_items:
        summary_lines.append(f"\n?†• <b>? ê·œ ?ì?</b>\n{'??*20}")
        for r, lv in new_items:
            summary_lines.append(_make_block(r, lv, idx))
            idx += 1
    else:
        summary_lines.append(f"\n?†• <b>? ê·œ ?ì?</b>  ?†ìŒ\n{'??*20}")

    if tracking_items:
        summary_lines.append(f"\n?”„ <b>?¬íƒì§€ (ì¶”ì  ì¤?</b>\n{'??*20}")
        for r, lv in tracking_items:
            summary_lines.append(_make_block(r, lv, idx))
            idx += 1

    summary_lines.append("\n? ï¸ ?¬ì ì°¸ê³ ???•ë³´?´ë©° ?¬ì ê¶Œìœ ê°€ ?„ë‹™?ˆë‹¤.")
    message = "\n".join(summary_lines)

    if len(message) > 4000:
        chunks = [summary_lines[0]]
        for line in summary_lines[1:]:
            if sum(len(c) for c in chunks) + len(line) > 3800:
                send_telegram("\n".join(chunks))
                chunks = [line]
            else:
                chunks.append(line)
        if chunks:
            send_telegram("\n".join(chunks))
    else:
        send_telegram(message)

    # ì°¨íŠ¸ ?´ë?ì§€ ?„ì†¡ (ì¢…ëª©ë³?
    # ì°¨íŠ¸ ?´ë?ì§€ ?„ì†¡ + ?±ê³¼ ì¶”ì  ?€??
    price_levels_map = {}
    if send_charts:
        for r in results[:5]:
            lv = _calc_levels_from_result(r)
            # ?´ë? ì¶”ì  ì¤‘ì¸ ì¢…ëª©?€ DB ê¸°ì¡´ ê°€ê²??¬ìš©
            try:
                from cache_db import _get_conn as _db_conn
                _conn = _db_conn()
                _row = _conn.execute(
                    "SELECT entry_price, target_price, stop_price, rr_ratio FROM alert_history "
                    "WHERE symbol=? AND status IN ('pending','active') ORDER BY id DESC LIMIT 1",
                    (r["symbol"],)
                ).fetchone()
                if _row and _row[0]:
                    lv = {"entry": _row[0], "target": _row[1], "stop": _row[2], "rr": _row[3],
                          "upside": (_row[1]/_row[0]-1)*100 if _row[0] else 0,
                          "downside": (_row[2]/_row[0]-1)*100 if _row[0] else 0}
                    # rr_ratio ?¤ì‹œê°??¬ê³„??
                    if _row[0] and _row[1] and _row[2]:
                        _risk = max(_row[0] - _row[2], 1)
                        lv["rr"] = (_row[1] - _row[0]) / _risk
            except Exception:
                pass
            price_levels_map[r["symbol"]] = lv
            close_s = r.get("close_series")
            img = None
            try:
                if close_s is not None:
                    if not hasattr(close_s, 'rolling'):
                        close_s = pd.Series(list(close_s))
                    # datetime ?¸ë±?¤ê? ?ˆìœ¼ë©??¤ìº” ?°ì´?°ë¡œ ì°¨íŠ¸ ?ì„±
                    if len(close_s) > 20 and hasattr(close_s.index[0], 'strftime'):
                        def _s(v, idx):
                            if v is None: return pd.Series([0]*len(idx), index=idx)
                            if not hasattr(v, 'index'): return pd.Series(list(v), index=idx)
                            return v
                        idx = close_s.index
                        df_chart = pd.DataFrame({
                            "Open":   _s(r.get("open_series"),   idx),
                            "High":   _s(r.get("high_series"),   idx),
                            "Low":    _s(r.get("low_series"),    idx),
                            "Close":  close_s,
                            "Volume": _s(r.get("volume_series"), idx),
                        })
                        img = make_chart_image(r["symbol"], r["name"], price_levels=lv, df=df_chart)
            except Exception as ce:
                print(f"?¤ìº”?°ì´??ì°¨íŠ¸ ?¤ë¥˜ {r['symbol']}: {ce}")
            # ?¤ìº” ?°ì´?°ë¡œ ?¤íŒ¨?˜ë©´ yfinanceë¡??´ë°±
            if img is None:
                img = make_chart_image(r["symbol"], r["name"], price_levels=lv)
            if img:
                if lv:
                    caption = (
                        f"<b>{r['name']}</b> â­?r['total_score']}??n"
                        f"?“ ë§¤ìˆ˜ê°€: ??lv['entry']:,.0f}\n"
                        f"?¯ ëª©í‘œê°€: ??lv['target']:,.0f} (+{lv['upside']:.1f}%)\n"
                        f"?›‘ ?ì ˆê°€: ??lv['stop']:,.0f} ({lv['downside']:.1f}%)\n"
                        f"?–ï¸ ?ìµë¹? {lv['rr']:.1f}:1"
                    )
                else:
                    caption = f"<b>{r['name']}</b>"
                send_photo(img, caption)

    # ?€?€ ?±ê³¼ ì¶”ì  DB ?€???€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
    try:
        from cache_db import save_alert_history
        # ì°¨íŠ¸ ?†ëŠ” ì¢…ëª©???¬í•¨?´ì„œ ?„ì²´ ?€??
        for r in results:
            if r["symbol"] not in price_levels_map:
                price_levels_map[r["symbol"]] = calc_price_levels(r["symbol"])
        save_alert_history(results, price_levels_map)
        print(f"[?±ê³¼ì¶”ì ] {len(results)}ê°?ì¢…ëª© ?€???„ë£Œ")
    except Exception as e:
        print(f"[?±ê³¼ì¶”ì ] ?€???¤ë¥˜: {e}")


def send_test_alert():
    return send_telegram(
        "??<b>HotStock ?Œë¦¼ ë´??°ê²° ?„ë£Œ!</b>\n"
        "ë§¤ì¼ ??ë§ˆê° ??ê¸‰ë“± ?ˆê³  ì¢…ëª©???ë™?¼ë¡œ ?Œë ¤?œë¦½?ˆë‹¤. ??"
    )


def send_performance_update():
    """?±ê³¼ ?…ë°?´íŠ¸ ?Œë¦¼"""
    try:
        from cache_db import update_alert_status, get_alert_history, get_performance_summary
        import yfinance as yf

        update_alert_status()

        today = date.today().isoformat()
        today_fmt = date.today().strftime("%Y.%m.%d")
        history = get_alert_history(200)

        hit_target_today = [h for h in history if h["status"] == "hit_target" and h.get("exit_date") == today]
        hit_stop_today   = [h for h in history if h["status"] == "hit_stop"   and h.get("exit_date") == today]
        # symbol ê¸°ì? ì¤‘ë³µ ?œê±°
        _seen_a = set()
        active_list = []
        for h in history:
            if h["status"] == "active" and h["symbol"] not in _seen_a:
                active_list.append(h); _seen_a.add(h["symbol"])
        _seen_p = set()
        still_pending = []
        for h in history:
            if h["status"] == "pending" and h["symbol"] not in _seen_a and h["symbol"] not in _seen_p:
                still_pending.append(h); _seen_p.add(h["symbol"])

        if not hit_target_today and not hit_stop_today and not active_list and not still_pending:
            print("[?±ê³¼ì¶”ì ] ?¤ëŠ˜ ?íƒœ ë³€ê²??†ìŒ - ?Œë¦¼ ?ëµ")
            return

        lines = [
            f"?“Š <b>?¬íŠ¸?´ë¦¬???„í™©</b>  {today_fmt}",
            "?€" * 16,
        ]

        # ?€?€ ?¤ëŠ˜ ì²?‚° ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
        if hit_target_today or hit_stop_today:
            lines.append("\n?”” <b>?¤ëŠ˜ ì²?‚°</b>")
            lines.append("?€" * 16)
            for h in hit_target_today:
                ret  = h['return_pct'] if h.get('return_pct') is not None else 0
                exit_p = f"??h['exit_price']:,.0f}" if h.get('exit_price') else "?"
                lines.append(
                    f"??<b>{h['name']}</b>\n"
                    f"   ì²´ê²°ê°€ {exit_p}  |  ?˜ìµ <b>+{ret:.1f}%</b> ?‰"
                )
            for h in hit_stop_today:
                ret  = h['return_pct'] if h.get('return_pct') is not None else 0
                exit_p = f"??h['exit_price']:,.0f}" if h.get('exit_price') else "?"
                lines.append(
                    f"?›‘ <b>{h['name']}</b>\n"
                    f"   ì²´ê²°ê°€ {exit_p}  |  ?ì‹¤ {ret:.1f}%"
                )

        # ?€?€ ë§¤ìˆ˜ ì¤??€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
        if active_list:
            lines.append(f"\n?Ÿ¢ <b>ë§¤ìˆ˜ ì¤?/b>  ({len(active_list)}ì¢…ëª©)")
            lines.append("?€" * 16)
            for h in active_list:
                days       = (date.today() - date.fromisoformat(h["alert_date"])).days
                base_price = h.get("avg_price") or h.get("entry_price")
                avg_str    = f"??base_price:,.0f}" if base_price else "ë¯¸ì •"
                target_str = f"??h['target_price']:,.0f}" if h.get("target_price") else "?"
                stop_str   = f"??h['stop_price']:,.0f}"   if h.get("stop_price")   else "?"
                # ë¶„í• ë§¤ìˆ˜ ì°¨ìˆ˜ ?œì‹œ
                split_step = h.get("split_step", 1) or 1
                split_tag  = f" <i>({split_step}ì°??‰ê· )</i>" if split_step > 1 else ""

                cur_line = ""
                try:
                    if base_price:
                        cur = float(yf.Ticker(h["symbol"]).history(period="1d")["Close"].iloc[-1])
                        ret = (cur - base_price) / base_price * 100
                        entry  = base_price
                        target = h.get("target_price")
                        stop   = h.get("stop_price")
                        if target and stop:
                            if ret >= 0 and target > entry:
                                ratio = min((cur - entry) / (target - entry), 1.0)
                                bar_filled = round(ratio * 8)
                                bar = "?Ÿ©" * bar_filled + "â¬? * (8 - bar_filled)
                            elif ret < 0 and stop < entry:
                                ratio = min((entry - cur) / (entry - stop), 1.0)
                                bar_filled = round(ratio * 8)
                                bar = "?Ÿ¥" * bar_filled + "â¬? * (8 - bar_filled)
                            else:
                                bar = "â¬? * 8
                        else:
                            bar_filled = min(int(abs(ret) / 2), 8)
                            bar = ("?Ÿ©" if ret >= 0 else "?Ÿ¥") * bar_filled + "â¬? * (8 - bar_filled)
                        cur_line = f"\n   {bar}  <b>??cur:,.0f}  ({ret:+.1f}%)</b>"
                except:
                    pass

                lines.append(
                    f"?“Œ <b>{h['name']}</b>  {split_icons}  <i>{days}?¼ì§¸</i>\n"
                    f"   ?‰ê· ?¨ê? {avg_str}  ?? ëª©í‘œ {target_str}  /  ?ì ˆ {stop_str}"
                    + cur_line
                )

        lines.append("\n?€" * 8)
        lines.append("? ï¸ <i>?¬ì ì°¸ê³ ???•ë³´?…ë‹ˆ??/i>")

        send_telegram("\n".join(lines))
        print("[?±ê³¼ì¶”ì ] ?…ë°?´íŠ¸ ?Œë¦¼ ?„ì†¡ ?„ë£Œ")

    except Exception as e:
        print(f"[?±ê³¼ì¶”ì ] ?Œë¦¼ ?¤ë¥˜: {e}")
        import traceback; traceback.print_exc()



def send_weekly_summary(force: bool = False):
    """ì£¼ê°„ ?±ê³¼ ?”ì•½ - ë§¤ì£¼ ê¸ˆìš”???„ì†¡"""
    try:
        from cache_db import get_performance_summary, get_alert_history
        from datetime import datetime, timedelta
        import yfinance as yf

        if not force and datetime.now().weekday() != 4:
            return

        # ?„ì²´ ?„ì  ?µê³„
        perf       = get_performance_summary()
        history    = get_alert_history(200)
        today      = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_start_str = week_start.isoformat()

        # ?´ë²ˆ ì£?? ê·œ ?Œë¦¼ ì¢…ëª©
        this_week    = [h for h in history if h["alert_date"] >= week_start_str]
        # ?„ì¬ ì§„í–‰ ì¤‘ì¸ ì¢…ëª© (?„ì²´ ê¸°ê°„, active/pending ëª¨ë‘ ë§¤ìˆ˜ ì¤‘ìœ¼ë¡??œì‹œ)
        _seen = set()
        active_list = []
        for h in history:
            if h["status"] in ("active", "pending") and h["symbol"] not in _seen:
                active_list.append(h)
                _seen.add(h["symbol"])
        _seen2 = set()
        pending_list = []
        # pending?€ active_list???´ë? ?¬í•¨??- ë³„ë„ ?œì‹œ ????
        # ?´ë²ˆ ì£?ì²?‚°??ì¢…ëª©
        closed_this_week = [h for h in this_week if h["status"] in ("hit_target", "hit_stop", "expired")]

        if perf["total"] == 0 and not this_week and not active_list and not pending_list:
            print("[?±ê³¼ì¶”ì ] ì£¼ê°„ ?”ì•½ ?°ì´???†ìŒ - ?ëµ")
            return

        win_rate = perf["win_rate"]
        avg_ret  = perf["avg_return"]
        period   = f"{week_start.strftime('%m/%d')} ~ {today.strftime('%m/%d')}"

        lines = [f"?“… <b>ì£¼ê°„ ë¦¬í¬??/b>  {period}", "?€" * 16]

        # ?€?€ 1. ë§¤ìˆ˜ ì¤?(?„ì²´ ê¸°ê°„ active) ?€?€?€?€?€?€?€?€?€?€
        if active_list:
            lines.append(f"\n?Ÿ¢ <b>ë§¤ìˆ˜ ì¤?/b>  ({len(active_list)}ì¢…ëª©)")
            lines.append("?€" * 16)
            for h in active_list:
                base_price = h.get("avg_price") or h.get("entry_price")  # ?ë™ë§¤ë§¤ ?‰ë‹¨ê°€ ?°ì„ 
                avg_str    = f"??base_price:,.0f}" if base_price else "ë¯¸ì •"
                target_str = f"??h['target_price']:,.0f}" if h.get("target_price") else "?"
                stop_str   = f"??h['stop_price']:,.0f}"   if h.get("stop_price")   else "?"
                split_step = h.get("split_step", 1) or 1
                split_tag  = f" <i>({split_step}ì°??‰ê· )</i>" if split_step > 1 else ""
                # ë¶„í• ë§¤ìˆ˜ ?´ëª¨ì§€ (?”µ=ë§¤ìˆ˜?„ë£Œ, ???€ê¸?
                split_icons = "".join(["?”µ" if i <= split_step else "?? for i in range(1, 4)])
                cur_line = ""
                try:
                    if base_price:
                        df_cur = yf.Ticker(h["symbol"]).history(period="5d").dropna(subset=["Close"])
                        if len(df_cur) == 0:
                            raise ValueError("no data")
                        cur = float(df_cur["Close"].iloc[-1])
                        ret = (cur - base_price) / base_price * 100
                        target = h.get("target_price")
                        stop   = h.get("stop_price")
                        entry_p = base_price
                        if target and stop:
                            if ret >= 0 and target > entry_p:
                                ratio = min((cur - entry_p) / (target - entry_p), 1.0)
                                filled = round(ratio * 8)
                                bar = "?Ÿ©" * filled + "â¬? * (8 - filled)
                            elif ret < 0 and stop < entry_p:
                                ratio = min((entry_p - cur) / (entry_p - stop), 1.0)
                                filled = round(ratio * 8)
                                bar = "?Ÿ¥" * filled + "â¬? * (8 - filled)
                            else:
                                bar = "â¬? * 8
                        else:
                            filled = min(int(abs(ret) / 2), 8)
                            bar = ("?Ÿ©" if ret >= 0 else "?Ÿ¥") * filled + "â¬? * (8 - filled)
                        cur_line = f"\n   {bar}  ??cur:,.0f}  <b>({ret:+.1f}%)</b>"
                except:
                    pass
                lines.append(
                    f"?“Œ <b>{h['name']}</b>  {split_icons}\n"
                    f"   ?‰ê· ?¨ê? {avg_str}  ?¯{target_str}  ?›‘{stop_str}"
                    + cur_line
                )

        # ?€?€ 2. ?„ì  ?±ê³¼ ?µê³„ (?„ì²´ ê¸°ê°„) ?€?€?€?€?€?€?€?€?€?€
        lines.append("\n?“Š <b>?„ì  ?±ê³¼</b>  <i>(?„ì²´ ê¸°ê°„)</i>")
        lines.append("?€" * 16)
        if perf["total"] > 0:
            filled = round(win_rate / 10)
            bar = "?Ÿ©" * filled + "â¬? * (10 - filled)
            wr_label = "?°ìˆ˜" if win_rate >= 60 else "ë³´í†µ" if win_rate >= 40 else "ë¶€ì§?
            lines.append(f"  {bar}  {win_rate}%  <i>{wr_label}</i>")
            lines.append(f"  ??{perf['win']}ê±? ?›‘ {perf['loss']}ê±? ??{perf.get('expired',0)}ê±?)
            ret_arrow = "?“ˆ" if avg_ret >= 0 else "?“‰"
            lines.append(f"  {ret_arrow} ?‰ê·  ?˜ìµë¥? <b>{avg_ret:+.1f}%</b>")
            if perf["win"] > 0:
                lines.append(f"     ?˜ìµ ?‰ê·   <b>+{perf['avg_win']:.1f}%</b>")
            if perf["loss"] > 0:
                lines.append(f"     ?ì‹¤ ?‰ê·   <b>{perf['avg_loss']:.1f}%</b>")
        else:
            lines.append("  ?„ì§ ì²?‚° ?°ì´???†ìŒ")

        # ?€?€ ìµœê·¼ ì²?‚° ?´ì—­ 5ê±??€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
        try:
            from cache_db import get_recent_closed
            recent = get_recent_closed(5)
            if recent:
                lines.append(f"\n?“‹ <b>ìµœê·¼ ì²?‚° ?´ì—­</b>")
                lines.append("?€" * 16)
                for r in recent:
                    icon = "?’°" if r["status"] == "hit_target" else ("?›‘" if r["status"] == "hit_stop" else "??)
                    ret_str = f"  <b>{r['return_pct']:+.1f}%</b>" if r["return_pct"] is not None else ""
                    date_str = r["exit_date"][5:] if r["exit_date"] else ""  # MM-DD
                    lines.append(f"  {icon} {r['name']}{ret_str}  <i>({date_str})</i>")
        except Exception:
            pass

        # ?€?€ ?¸í„° ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
        lines.append(f"\n?Ÿ¢ ë§¤ìˆ˜ ì¤?{len(active_list)}ì¢…ëª©")
        lines.append("?€" * 16)
        lines.append("? ï¸ <i>?¬ì ì°¸ê³ ???•ë³´?…ë‹ˆ??/i>")

        send_telegram("\n".join(lines))
        print("[?±ê³¼ì¶”ì ] ì£¼ê°„ ?”ì•½ ?„ì†¡ ?„ë£Œ")

    except Exception as e:
        print(f"[?±ê³¼ì¶”ì ] ì£¼ê°„ ?”ì•½ ?¤ë¥˜: {e}")
        import traceback; traceback.print_exc()
