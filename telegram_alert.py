"""
텔레그램 알림 모듈 v2.0
- 급등 예고 종목 자동 알림
- 매수가/목표가/손절가/손익비 포함
- 캔들차트 이미지 첨부
- 재무 데이터 (PER/PBR)
"""
import requests
import pandas as pd
import numpy as np
import io
from datetime import date

TELEGRAM_TOKEN   = "8686257393:AAGWPuisi_qy995cKC7pIWnCGqpQMljQxgc"
TELEGRAM_CHAT_ID = "-1003815975342"  # 주식 급등 알림 채널

def send_telegram(message: str) -> bool:
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


def send_photo(image_bytes: bytes, caption: str = "") -> bool:
    """이미지 전송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        resp = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML"
        }, files={"photo": ("chart.png", image_bytes, "image/png")}, timeout=30)
        return resp.ok
    except:
        return False


def make_chart_image(symbol: str, name: str, price_levels: dict = None) -> bytes | None:
    """캔들차트 + 240일선 + 목표가/손절가 수평선 이미지 생성"""
    try:
        import yfinance as yf
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        df = yf.Ticker(symbol).history(period="6mo")
        df = df.dropna(subset=["Open","High","Low","Close"])
        if len(df) < 20:
            return None

        df2y = yf.Ticker(symbol).history(period="2y").dropna(subset=["Close"])
        ma240_full = df2y["Close"].rolling(240).mean()
        ma240 = ma240_full.reindex(df.index)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7),
                                        gridspec_kw={"height_ratios": [3, 1]},
                                        facecolor="#0e1117")
        ax1.set_facecolor("#0e1117")
        ax2.set_facecolor("#0e1117")

        # 캔들차트
        for i, (idx, row) in enumerate(df.iterrows()):
            color = "#ff3355" if row["Close"] >= row["Open"] else "#4f8ef7"
            ax1.plot([i, i], [row["Low"], row["High"]], color=color, linewidth=0.8)
            ax1.bar(i, abs(row["Close"] - row["Open"]),
                    bottom=min(row["Open"], row["Close"]),
                    color=color, width=0.6, alpha=0.9)

        close = df["Close"]
        x = range(len(df))
        ax1.plot(x, close.rolling(20).mean().values, color="#ffd700", linewidth=1.2, label="MA20")
        ax1.plot(x, close.rolling(60).mean().values, color="#ff8c42", linewidth=1.2, label="MA60")
        if ma240.notna().any():
            ax1.plot(x, ma240.values, color="#ff4b6e", linewidth=2.0, label="MA240")

        current = float(close.iloc[-1])

        # ── 목표가 / 현재가 / 손절가 수평선 ──
        if price_levels:
            target  = price_levels.get("target")
            stop    = price_levels.get("stop")
            entry   = price_levels.get("entry", current)
            entry_label = price_levels.get("entry_label", "매수")
            upside  = price_levels.get("upside", 0)
            downside = price_levels.get("downside", 0)

            if target:
                ax1.axhline(y=target, color="#00ff88", linewidth=1.5, linestyle="--", alpha=0.9)
                ax1.text(len(df)-1, target, f" 목표 ₩{target:,.0f} (+{upside:.1f}%)",
                         color="#00ff88", fontsize=7, va="bottom", ha="right",
                         fontproperties=_get_korean_font())
                ax1.axhspan(entry, target, alpha=0.05, color="#00ff88")

            # 매수가 (240선 근거)
            if entry < current:
                ax1.axhline(y=entry, color="#ffd700", linewidth=1.5, linestyle="-.", alpha=0.9)
                ax1.text(len(df)-1, entry, f" 매수({entry_label}) ₩{entry:,.0f}",
                         color="#ffd700", fontsize=7, va="bottom", ha="right",
                         fontproperties=_get_korean_font())

            ax1.axhline(y=current, color="#ffffff", linewidth=1.0, linestyle="--", alpha=0.6)
            ax1.text(len(df)-1, current, f" 현재 ₩{current:,.0f}",
                     color="#ffffff", fontsize=7, va="bottom", ha="right",
                     fontproperties=_get_korean_font())

            if stop:
                ax1.axhline(y=stop, color="#ff3355", linewidth=1.5, linestyle="--", alpha=0.9)
                ax1.text(len(df)-1, stop, f" 손절 ₩{stop:,.0f} ({downside:.1f}%)",
                         color="#ff3355", fontsize=7, va="top", ha="right",
                         fontproperties=_get_korean_font())
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

        # 거래량
        vol = df["Volume"]
        vol_colors = ["#ff3355" if df["Close"].iloc[i] >= df["Open"].iloc[i]
                      else "#4f8ef7" for i in range(len(df))]
        ax2.bar(x, vol.values, color=vol_colors, alpha=0.7, width=0.6)
        ax2.plot(x, vol.rolling(20).mean().values, color="#ffd700", linewidth=1.0)
        ax2.tick_params(colors="#8b92a5", labelsize=7)
        ax2.spines[:].set_color("#2d3555")
        ax2.yaxis.set_label_position("right")
        ax2.yaxis.tick_right()
        ax2.set_ylabel("Volume", color="#8b92a5", fontsize=7)

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
        print(f"차트 생성 실패 {symbol}: {e}")
        return None


def _get_korean_font():
    """한글 폰트 반환 (없으면 None)"""
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


def get_financial_data(symbol: str) -> dict:
    """재무 데이터 (PER, PBR) 조회"""
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


def calc_price_levels(symbol: str) -> dict:
    """목표가/손절가/손익비 + 근거 있는 매수가 계산"""
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

        # ── 매수가: 240선 근처 근거 있는 진입가 ──────────────────
        ma240 = close.rolling(240).mean()
        ma20  = float(close.rolling(20).mean().iloc[-1])
        ma240_v = float(ma240.iloc[-1]) if not pd.isna(ma240.iloc[-1]) else None
        swing_low_20 = float(low.tail(20).min())

        # 후보 매수가 목록 (현재가 이하 + 240선 위)
        entry_candidates = []
        if ma240_v:
            entry_candidates.append(("240선+버퍼", ma240_v * 1.005))  # 240선 0.5% 위
        entry_candidates.append(("MA20", ma20))
        entry_candidates.append(("스윙저점", swing_low_20))

        # 현재가 이하이면서 240선 위인 후보 중 가장 높은 값 선택
        valid = [
            (label, price) for label, price in entry_candidates
            if price < current and (ma240_v is None or price >= ma240_v * 0.995)
        ]
        if valid:
            entry_label, entry = max(valid, key=lambda x: x[1])
        else:
            # 후보가 없으면 현재가 그대로
            entry_label, entry = "현재가", current

        # 손절가
        stop = max(
            swing_low_20 - atr * 1.5,
            ma20 - atr * 1.0
        )
        stop = max(stop, current * 0.88)
        stop = min(stop, current * 0.96)
        risk = max(entry - stop, entry * 0.01)

        # 목표가
        recent_high = float(high.tail(120).max())
        recent_low  = float(low.tail(120).min())
        swing_range = max(recent_high - recent_low, entry * 0.01)

        candidates = sorted([
            x for x in [
                recent_low + swing_range * 1.272,
                recent_low + swing_range * 1.618,
                recent_low + swing_range * 2.0,
                recent_high * 1.05,
                entry + atr * 3.0,
                entry + atr * 5.0,
            ] if x > entry * 1.03
        ])

        min_rr3 = entry + risk * 3.0
        valid_t = [x for x in candidates if x >= min_rr3]
        if valid_t:
            weights = [1 / (x - entry) for x in valid_t]
            target = sum(x * w for x, w in zip(valid_t, weights)) / sum(weights)
        elif candidates:
            target = candidates[-1]
        else:
            target = entry + risk * 3.0

        target = min(target, entry * 2.0)
        rr = (target - entry) / (entry - stop + 1e-9)

        return {
            "current":     current,
            "entry":       entry,
            "entry_label": entry_label,
            "target":      target,
            "stop":        stop,
            "rr":          rr,
            "upside":      (target / entry - 1) * 100,
            "downside":    (stop / entry - 1) * 100,
        }
    except:
        return {}


def format_signals(signals: dict) -> str:
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


def send_scan_alert(results: list, send_charts: bool = True):
    """스캔 결과 텔레그램 전송 (차트 이미지 포함)"""
    if not results:
        return

    today = date.today().strftime("%Y-%m-%d")

    # 요약 메시지 먼저 전송
    summary_lines = [f"🚀 <b>급등 예고 종목</b> ({today} 장마감) — {len(results[:10])}개\n{'━'*20}"]

    for i, r in enumerate(results[:10], 1):
        lv = calc_price_levels(r["symbol"])
        fin = get_financial_data(r["symbol"])
        s   = r.get("signals", {})
        sig_str = format_signals(s)

        entry      = f"₩{lv['entry']:,.0f} ({lv['entry_label']})" if lv else f"₩{r['current_price']:,.0f}"
        target_str = f"₩{lv['target']:,.0f}  (+{lv['upside']:.1f}%)" if lv else "-"
        stop_str   = f"₩{lv['stop']:,.0f}  ({lv['downside']:.1f}%)" if lv else "-"
        rr_str     = f"{lv['rr']:.1f} : 1" if lv else "-"

        per_str = f"PER {fin['per']}" if fin.get("per") else ""
        pbr_str = f"PBR {fin['pbr']}" if fin.get("pbr") else ""
        fin_str = "  ".join(filter(None, [per_str, pbr_str]))

        block = (
            f"\n<b>{i}. {r['name']} ({r['symbol']})</b> ⭐ {r['total_score']}점\n"
            f"📍 매수가:  {entry}\n"
            f"🎯 목표가:  {target_str}\n"
            f"🛑 손절가:  {stop_str}\n"
            f"⚖️ 손익비:  {rr_str}\n"
        )
        if fin_str:
            block += f"📊 {fin_str}\n"
        if sig_str:
            block += f"{sig_str}\n"
        block += "━" * 20
        summary_lines.append(block)

    summary_lines.append("\n⚠️ 투자 참고용 정보이며 투자 권유가 아닙니다.")
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

    # 차트 이미지 전송 (종목별)
    if send_charts:
        for r in results[:5]:
            lv = calc_price_levels(r["symbol"])
            img = make_chart_image(r["symbol"], r["name"], price_levels=lv)
            if img:
                if lv:
                    caption = (
                        f"<b>{r['name']}</b> ⭐{r['total_score']}점\n"
                        f"매수({lv['entry_label']}) ₩{lv['entry']:,.0f}  "
                        f"목표 ₩{lv['target']:,.0f}(+{lv['upside']:.1f}%)  "
                        f"손절 ₩{lv['stop']:,.0f}({lv['downside']:.1f}%)"
                    )
                else:
                    caption = f"<b>{r['name']}</b>"
                send_photo(img, caption)


def send_test_alert():
    return send_telegram(
        "✅ <b>HotStock 알림 봇 연결 완료!</b>\n"
        "매일 장 마감 후 급등 예고 종목을 자동으로 알려드립니다. 🚀"
    )
