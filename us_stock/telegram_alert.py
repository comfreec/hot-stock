"""
미국 주식 텔레그램 알림
- 국내 telegram_alert와 동일한 구조
- 달러 단위 표시
"""
import os
import io
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


def send_photo(image_bytes: bytes, caption: str = "") -> bool:
    token, chat_id = _get_config()
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
            files={"photo": ("chart.png", image_bytes, "image/png")},
            timeout=30
        )
        return resp.ok
    except Exception:
        return False


def make_us_chart_image(symbol: str, name: str, price_levels: dict = None, df=None) -> bytes | None:
    """미국 주식 캔들차트 이미지 생성 (달러 단위)"""
    try:
        import yfinance as yf
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if df is None:
            df = yf.Ticker(symbol).history(period="6mo", auto_adjust=False)
            df = df.dropna(subset=["Open", "High", "Low", "Close"])
            if len(df) < 20:
                return None
            # MA240 계산용 2년 데이터 (df가 None일 때만 yfinance 재호출)
            try:
                df2y = yf.Ticker(symbol).history(period="2y", auto_adjust=False).dropna(subset=["Close"])
                ma240_full = df2y["Close"].rolling(240).mean()
            except Exception:
                ma240_full = df["Close"].rolling(240).mean()
            ma240 = ma240_full.reindex(df.index)
        else:
            df = df.dropna(subset=["Open", "High", "Low", "Close"]).tail(120)
            if len(df) < 20:
                return None
            # 스캔 데이터로 MA240 직접 계산 (yfinance 재호출 없음)
            ma240 = df["Close"].rolling(240).mean()

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7),
                                        gridspec_kw={"height_ratios": [3, 1]},
                                        facecolor="#0e1117")
        ax1.set_facecolor("#0e1117")
        ax2.set_facecolor("#0e1117")

        # Heikin-Ashi
        ha_close = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4
        ha_open = ha_close.copy()
        for i in range(1, len(ha_open)):
            ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
        ha_high = pd.concat([df["High"], ha_open, ha_close], axis=1).max(axis=1)
        ha_low  = pd.concat([df["Low"],  ha_open, ha_close], axis=1).min(axis=1)

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

        if price_levels:
            target   = price_levels.get("target")
            stop     = price_levels.get("stop")
            entry    = price_levels.get("entry", current)
            upside   = price_levels.get("upside", 0)
            downside = price_levels.get("downside", 0)

            if target:
                ax1.axhline(y=target, color="#00ff88", linewidth=1.5, linestyle="--", alpha=0.9)
                ax1.text(len(df)-1, target, f" Target ${target:,.2f} (+{upside:.1f}%)",
                         color="#00ff88", fontsize=7, va="bottom", ha="right")
                ax1.axhspan(entry, target, alpha=0.05, color="#00ff88")
            if entry < current:
                ax1.axhline(y=entry, color="#ffd700", linewidth=1.5, linestyle="-.", alpha=0.9)
                ax1.text(len(df)-1, entry, f" Buy ${entry:,.2f}",
                         color="#ffd700", fontsize=7, va="bottom", ha="right")
            ax1.axhline(y=current, color="#ffffff", linewidth=1.0, linestyle="--", alpha=0.6)
            ax1.text(len(df)-1, current, f" ${current:,.2f}",
                     color="#ffffff", fontsize=7, va="bottom", ha="right")
            if stop:
                ax1.axhline(y=stop, color="#ff3355", linewidth=1.5, linestyle="--", alpha=0.9)
                ax1.text(len(df)-1, stop, f" Stop ${stop:,.2f} ({downside:.1f}%)",
                         color="#ff3355", fontsize=7, va="top", ha="right")
                ax1.axhspan(stop, entry, alpha=0.05, color="#ff3355")
        else:
            ax1.axhline(y=current, color="#ffffff", linewidth=0.8, linestyle="--", alpha=0.5)

        ax1.set_title(f"{name} ({symbol})", color="#e0e6f0", fontsize=12, pad=8)
        ax1.tick_params(colors="#8b92a5", labelsize=8)
        ax1.spines[:].set_color("#2d3555")
        ax1.yaxis.set_label_position("right")
        ax1.yaxis.tick_right()
        ax1.legend(loc="upper left", fontsize=7, facecolor="#1a1f35",
                   labelcolor="#8b92a5", edgecolor="#2d3555")

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
        print(f"[US차트] {symbol} 생성 실패: {e}")
        return None


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


def _to_series(v):
    """list/array → pd.Series 변환 헬퍼"""
    if v is None: return None
    if hasattr(v, 'rolling'): return v
    return pd.Series(list(v))


def send_us_scan_alert(results: list):
    """미국 주식 스캔 결과 텔레그램 전송 (차트 이미지 포함)"""
    if not results:
        return

    today = date.today().strftime("%Y-%m-%d")
    lines = [f"🇺🇸 <b>미국 스윙 레이더</b> ({today} 장마감) — {len(results[:10])}개\n{'━'*20}"]

    for i, r in enumerate(results[:10], 1):
        close_s = _to_series(r.get("close_series"))
        high_s  = _to_series(r.get("high_series"))
        low_s   = _to_series(r.get("low_series"))

        lv = {}
        if close_s is not None and len(close_s) > 20:
            lv = calc_us_levels(close_s, high_s if high_s is not None else close_s,
                                low_s  if low_s  is not None else close_s)

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
            f"{'━'*20}"
        )
        lines.append(block)

    msg = "\n".join(lines)
    if len(msg) > 4000:
        send_telegram("\n".join(lines[:len(lines)//2]))
        send_telegram("\n".join(lines[len(lines)//2:]))
    else:
        send_telegram(msg)

    # 상위 5개 차트 이미지 전송
    for r in results[:5]:
        close_s = _to_series(r.get("close_series"))
        high_s  = _to_series(r.get("high_series"))
        low_s   = _to_series(r.get("low_series"))
        open_s  = _to_series(r.get("open_series"))
        lv = {}
        if close_s is not None and len(close_s) > 20:
            lv = calc_us_levels(close_s, high_s if high_s is not None else close_s,
                                low_s  if low_s  is not None else close_s)

        # 스캔 시 받아둔 데이터로 차트 생성 (yfinance 재호출 없음)
        df_chart = None
        if close_s is not None and len(close_s) > 20:
            try:
                import pandas as _pd
                df_chart = _pd.DataFrame({
                    "Open":   open_s  if open_s  is not None else close_s,
                    "High":   high_s  if high_s  is not None else close_s,
                    "Low":    low_s   if low_s   is not None else close_s,
                    "Close":  close_s,
                    "Volume": _to_series(r.get("volume_series")) or _pd.Series(0, index=close_s.index),
                })
            except Exception:
                df_chart = None

        img = make_us_chart_image(r["symbol"], r["name"], lv if lv else None, df=df_chart)
        if img:
            caption = (f"🇺🇸 {r['name']} ({r['symbol']}) ⭐{r['total_score']}점\n"
                      f"${r['current_price']:,.2f} | 240선 +{r['ma240_gap']:.1f}%")
            send_photo(img, caption=caption)
