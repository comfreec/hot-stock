"""
텔레그램 알림 모듈 - 코인 버전
"""
import requests
import pandas as pd
import numpy as np
import io
import os
from datetime import date


def _get_config():
    token   = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        try:
            import streamlit as st
            token   = token   or st.secrets.get("TELEGRAM_TOKEN", "")
            chat_id = chat_id or st.secrets.get("TELEGRAM_CHAT_ID", "")
        except:
            pass
    return token, chat_id


def send_telegram(message: str) -> bool:
    token, chat_id = _get_config()
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
        return resp.ok
    except:
        return False


def send_photo(image_bytes: bytes, caption: str = "") -> bool:
    token, chat_id = _get_config()
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
            files={"photo": ("chart.png", image_bytes, "image/png")},
            timeout=30
        )
        return resp.ok
    except:
        return False


def calc_price_levels(symbol: str, current: float) -> dict:
    """목표가/손절가/손익비 계산 (ATR 기반)"""
    try:
        from crypto_surge_detector import fetch_ohlcv
        df = fetch_ohlcv(symbol, limit=100)
        if df is None or len(df) < 20:
            return {}

        close = df["Close"]
        high  = df["High"]
        low   = df["Low"]

        # ATR
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().dropna().iloc[-1])

        # 매수가: 현재가 (코인은 24/7 거래 → 현재가 기준)
        entry = current
        # 손절가: -5% 또는 ATR*1.5 중 더 가까운 것
        stop = max(entry * 0.95, entry - atr * 1.5)
        risk = entry - stop

        # 목표가: 손익비 3:1 이상
        target_candidates = sorted([
            entry + risk * 3.0,
            entry + atr * 4.0,
            entry + atr * 6.0,
        ])
        target = next((t for t in target_candidates if t > entry * 1.05), entry + risk * 3.0)
        rr = (target - entry) / risk if risk > 0 else 0

        return {
            "entry":  round(entry, 6),
            "stop":   round(stop, 6),
            "target": round(target, 6),
            "rr":     round(rr, 2),
        }
    except:
        return {}


def make_chart_image(symbol: str, name: str, price_levels: dict = None) -> bytes | None:
    """캔들차트 + 200일선 이미지 생성"""
    try:
        from crypto_surge_detector import fetch_ohlcv
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        df = fetch_ohlcv(symbol, limit=120)
        if df is None or len(df) < 20:
            return None

        df2y = fetch_ohlcv(symbol, limit=300)
        ma200_full = df2y["Close"].rolling(200).mean() if df2y is not None else df["Close"].rolling(200).mean()
        ma200 = ma200_full.reindex(df.index)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7),
                                        gridspec_kw={"height_ratios": [3, 1]},
                                        facecolor="#0e1117")
        ax1.set_facecolor("#0e1117")
        ax2.set_facecolor("#0e1117")

        # Heikin-Ashi
        ha_close = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4
        ha_open  = ha_close.copy()
        for i in range(1, len(ha_open)):
            ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
        ha_high = pd.concat([df["High"], ha_open, ha_close], axis=1).max(axis=1)
        ha_low  = pd.concat([df["Low"],  ha_open, ha_close], axis=1).min(axis=1)

        x = range(len(df))
        for i, xi in enumerate(x):
            color = "#26a69a" if ha_close.iloc[i] >= ha_open.iloc[i] else "#ef5350"
            ax1.plot([xi, xi], [ha_low.iloc[i], ha_high.iloc[i]], color=color, linewidth=0.8)
            ax1.bar(xi, abs(ha_close.iloc[i] - ha_open.iloc[i]),
                    bottom=min(ha_open.iloc[i], ha_close.iloc[i]),
                    color=color, width=0.8, alpha=0.9)

        # MA200
        ma200_vals = [float(ma200.iloc[i]) if not pd.isna(ma200.iloc[i]) else None for i in range(len(df))]
        valid_x = [xi for xi, v in zip(x, ma200_vals) if v is not None]
        valid_v = [v for v in ma200_vals if v is not None]
        if valid_x:
            ax1.plot(valid_x, valid_v, color="#ff9800", linewidth=1.5, label="MA200", zorder=5)

        # 가격 레벨
        if price_levels:
            ax1.axhline(price_levels.get("entry", 0),  color="#4f8ef7", linewidth=1, linestyle="--", alpha=0.8)
            ax1.axhline(price_levels.get("target", 0), color="#00d4aa", linewidth=1, linestyle="--", alpha=0.8)
            ax1.axhline(price_levels.get("stop", 0),   color="#ef5350", linewidth=1, linestyle="--", alpha=0.8)

        ax1.set_title(f"{name} ({symbol})", color="#e8edf8", fontsize=13, fontweight="bold", pad=10)
        ax1.tick_params(colors="#6b7280", labelsize=8)
        ax1.spines[:].set_color("#1e2540")
        ax1.legend(loc="upper left", fontsize=8, facecolor="#0e1117", labelcolor="#e8edf8")

        # 거래량
        vol_colors = ["#26a69a" if ha_close.iloc[i] >= ha_open.iloc[i] else "#ef5350" for i in range(len(df))]
        ax2.bar(x, df["Volume"].values, color=vol_colors, alpha=0.7, width=0.8)
        ax2.tick_params(colors="#6b7280", labelsize=7)
        ax2.spines[:].set_color("#1e2540")
        ax2.set_ylabel("Volume", color="#6b7280", fontsize=8)

        plt.tight_layout(pad=1.5)
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                    facecolor="#0e1117", edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        print(f"[차트 생성 오류] {e}")
        return None


def send_scan_alert(results: list, send_charts: bool = True):
    """스캔 결과 텔레그램 전송"""
    if not results:
        return

    today = date.today().isoformat()
    header = (
        f"🪙 <b>{today} 코인 급등 예고</b>\n"
        f"{'━'*20}\n"
        f"200일선 돌파 후 급등 예상 코인\n\n"
    )

    lines = []
    for i, r in enumerate(results[:10], 1):
        sym   = r["symbol"]
        name  = r["name"]
        price = r["current_price"]
        score = r["total_score"]
        gap   = r["gap_pct"]
        rsi   = r.get("rsi", 0)
        days  = r["days_since_cross"]
        fr    = r.get("funding_rate", 0)

        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        lines.append(
            f"{medal} <b>{name}</b> ({sym})\n"
            f"   💰 ${price:,.4f}  |  점수 {score}점\n"
            f"   📊 200선 이격 +{gap:.1f}%  |  RSI {rsi:.0f}\n"
            f"   📅 돌파 후 {days}일  |  펀딩비 {fr:+.4f}%\n"
        )

    msg = header + "\n".join(lines)
    send_telegram(msg)

    # 상위 3개 차트 전송
    if send_charts:
        for r in results[:3]:
            try:
                levels = calc_price_levels(r["symbol"], r["current_price"])
                img = make_chart_image(r["symbol"], r["name"], levels)
                if img:
                    caption = (
                        f"📈 {r['name']} ({r['symbol']})\n"
                        f"매수 ${levels.get('entry',0):,.4f} | "
                        f"목표 ${levels.get('target',0):,.4f} | "
                        f"손절 ${levels.get('stop',0):,.4f} | "
                        f"손익비 {levels.get('rr',0):.1f}:1"
                    )
                    send_photo(img, caption)
            except Exception as e:
                print(f"[차트 전송 오류] {r['symbol']}: {e}")
