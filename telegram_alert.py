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

import os

def _get_telegram_config():
    """환경변수 → Streamlit secrets 순으로 텔레그램 설정 로드"""
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
    """이미지 전송"""
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
    """캔들차트 + 240일선 + 목표가/손절가 수평선 이미지 생성"""
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
            # df가 짧으면 2y 데이터로 MA240 계산
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

        # Heikin-Ashi 계산
        ha_close = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4
        ha_open = ha_close.copy()
        for i in range(1, len(ha_open)):
            ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
        ha_high = pd.concat([df["High"], ha_open, ha_close], axis=1).max(axis=1)
        ha_low  = pd.concat([df["Low"],  ha_open, ha_close], axis=1).min(axis=1)

        # Heikin-Ashi 캔들차트
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
                ax1.text(len(df)-1, target, f" Target ₩{target:,.0f} (+{upside:.1f}%)",
                         color="#00ff88", fontsize=7, va="bottom", ha="right")
                ax1.axhspan(entry, target, alpha=0.05, color="#00ff88")

            # 매수가 (240선 근거)
            if entry < current:
                label_en = {"240선": "MA240", "240선+버퍼": "MA240", "MA20": "MA20", "스윙저점": "SwingLow", "현재가": "Close"}.get(entry_label, entry_label)
                ax1.axhline(y=entry, color="#ffd700", linewidth=1.5, linestyle="-.", alpha=0.9)
                ax1.text(len(df)-1, entry, f" Buy ₩{entry:,.0f}",
                         color="#ffd700", fontsize=7, va="bottom", ha="right")

            ax1.axhline(y=current, color="#ffffff", linewidth=1.0, linestyle="--", alpha=0.6)
            ax1.text(len(df)-1, current, f" Close ₩{current:,.0f}",
                     color="#ffffff", fontsize=7, va="bottom", ha="right")

            if stop:
                ax1.axhline(y=stop, color="#ff3355", linewidth=1.5, linestyle="--", alpha=0.9)
                ax1.text(len(df)-1, stop, f" Stop ₩{stop:,.0f} ({downside:.1f}%)",
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


def round_to_tick(price: float) -> int:
    """한국 주식 호가 단위로 반올림"""
    if price < 2000:      tick = 1
    elif price < 5000:    tick = 5
    elif price < 20000:   tick = 10
    elif price < 50000:   tick = 50
    elif price < 200000:  tick = 100
    elif price < 500000:  tick = 500
    else:                 tick = 1000
    return int(round(price / tick) * tick)


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
        df = yf.Ticker(symbol).history(period="5y", auto_adjust=False)
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

        # ── 매수가: 240일선 가격 고정 ────────────────────────────
        ma240  = close.rolling(240).mean()
        ma1000 = close.rolling(1000).mean()
        ma240_v  = float(ma240.iloc[-1])  if not pd.isna(ma240.iloc[-1])  else None
        ma1000_v = float(ma1000.iloc[-1]) if not pd.isna(ma1000.iloc[-1]) else None

        if ma240_v and ma240_v < current:
            entry_label = "장기선"
            entry = ma240_v
        else:
            entry_label, entry = "현재가", current

        # ── 손절가: 240일선 -5% 고정 ──────────────────────────────
        if ma240_v and ma240_v < entry:
            stop = ma240_v * 0.95
        else:
            stop = entry * 0.95
        risk = max(entry - stop, entry * 0.01)

        # 목표가: 피보나치 되돌림 기반
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

        # 호가 단위 적용
        entry  = round_to_tick(entry)
        target = round_to_tick(target)
        stop   = round_to_tick(stop)
        rr     = (target - entry) / (entry - stop + 1e-9)
        ma240_tick = round_to_tick(ma240_v) if ma240_v else entry

        return {
            "current":     current,
            "entry":       entry,
            "entry_label": entry_label,
            "ma240":       ma240_tick,
            "target":      target,
            "stop":        stop,
            "rr":          rr,
            "upside":      (target / entry - 1) * 100,
            "downside":    (stop / entry - 1) * 100,
        }
    except Exception as e:
        print(f"[calc_price_levels] {symbol} 오류: {e}")
        import traceback; traceback.print_exc()
        return {}


def _calc_levels_from_result(r: dict) -> dict:
    """스캔 결과에서 직접 가격 레벨 계산 - app.py make_candle과 동일한 로직"""
    try:
        current = float(r["current_price"])
        close_s = r.get("close_series")
        high_s  = r.get("high_series")
        low_s   = r.get("low_series")

        # list → Series 변환
        def to_s(v):
            if v is None: return None
            if hasattr(v, 'rolling'): return v
            return pd.Series(list(v))

        close_s = to_s(close_s)
        high_s  = to_s(high_s)
        low_s   = to_s(low_s)

        if close_s is None or len(close_s) < 20:
            return {}

        high_s  = high_s  if high_s  is not None else close_s
        low_s   = low_s   if low_s   is not None else close_s

        # ATR
        tr = pd.concat([high_s - low_s,
                        (high_s - close_s.shift(1)).abs(),
                        (low_s  - close_s.shift(1)).abs()], axis=1).max(axis=1)
        atr_s = tr.rolling(14).mean().dropna()
        atr = float(atr_s.iloc[-1]) if len(atr_s) > 0 else float((high_s - low_s).mean())

        # 매수가: 240일선 가격 고정
        ma240_s  = close_s.rolling(240).mean()
        ma1000_s = close_s.rolling(1000).mean()
        ma240_v  = float(ma240_s.iloc[-1]) if not pd.isna(ma240_s.iloc[-1]) else None
        ma1000_v = float(ma1000_s.iloc[-1]) if not pd.isna(ma1000_s.iloc[-1]) else None

        if ma240_v and ma240_v < current:
            entry_label = "장기선"
            entry = ma240_v
        else:
            entry_label, entry = "현재가", current

        # 손절가: 240일선 -5% 고정
        if ma240_v and ma240_v < entry:
            stop = ma240_v * 0.95
        else:
            stop = entry * 0.95
        risk = max(entry - stop, entry * 0.01)

        # 목표가: app.py와 동일한 다중 기법
        recent_high = float(high_s.tail(120).max()) if len(high_s) >= 120 else float(high_s.max())
        recent_low  = float(low_s.tail(120).min())  if len(low_s)  >= 120 else float(low_s.min())
        swing_range = max(recent_high - recent_low, current * 0.01)

        fib_1272 = recent_low + swing_range * 1.272
        fib_1618 = recent_low + swing_range * 1.618
        fib_2000 = recent_low + swing_range * 2.000
        prev_high_ext = recent_high * 1.05
        atr_x3 = current + atr * 3.0
        atr_x5 = current + atr * 5.0

        ma20_s = close_s.rolling(20).mean()
        std20  = close_s.rolling(20).std()
        bb_upper = float((ma20_s + std20 * 2.0).dropna().iloc[-1])

        min_rr3 = current + risk * 3.0
        min_rr2 = current + risk * 2.0
        all_cands = sorted([x for x in [fib_1272, fib_1618, fib_2000,
                                         recent_high, prev_high_ext,
                                         atr_x3, atr_x5, bb_upper]
                            if x > current * 1.03])
        valid_3 = [x for x in all_cands if x >= min_rr3]
        valid_2 = [x for x in all_cands if x >= min_rr2]

        if valid_3:
            weights = [1 / (x - current) for x in valid_3]
            target = sum(x * w for x, w in zip(valid_3, weights)) / sum(weights)
        elif valid_2:
            target = valid_2[-1]
        elif all_cands:
            target = all_cands[-1]
        else:
            target = current + risk * 3.0

        target = min(target, current * 2.0)

        # 호가 단위 적용
        entry  = round_to_tick(entry)
        stop   = round_to_tick(stop)
        target = round_to_tick(target)

        rr = (target - entry) / (max(entry - stop, 1) + 1e-9)

        return {
            "current":  current,
            "entry":    round(entry),
            "target":   round(target),
            "stop":     round(stop),
            "rr":       rr,
            "upside":   (target / entry - 1) * 100,
            "downside": (stop / entry - 1) * 100,
            "ma240":    round(ma240_v)  if ma240_v  else round(entry),
            "ma1000":   round(ma1000_v) if ma1000_v else None,
        }
    except Exception as e:
        print(f"[_calc_levels_from_result] {r.get('symbol')} 오류: {e}")
        import traceback; traceback.print_exc()
        return {}


def format_signals(signals: dict) -> str:
    sig_map = {
        "rsi_cycle_pullback":    "🔄 RSI사이클눌림목",
        "vol_at_cross":          "📦 돌파 거래량",
        "recent_vol":            "📊 거래량 급증",
        "bb_squeeze_expand":     "🔥 BB수축→확장",
        "macd_cross":            "📈 MACD골든크로스",
        "ma240_turning_up":      "🔼 장기선 상승전환",
        "ma_align":              "⚡ 이평선 정배열",
        "obv_rising":            "💹 OBV 상승",
        "ichimoku_bull":         "☁️ 일목균형표",
        "near_52w_high":         "🏆 52주 신고가",
        "stoch_cross":           "📉 스토캐스틱",
        "mfi_oversold_recovery": "💰 MFI 반등",
    }
    active = [sig_map[k] for k, v in signals.items() if v is True and k in sig_map]
    return "  ".join(active[:6]) if active else ""


def make_summary_chart(results: list) -> bytes | None:
    """급등 예고 종목 점수 요약 차트 - 다크 테마 고급 디자인"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib import font_manager
        import numpy as np

        # 한글 폰트 설정
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

        # ── 캔버스 설정 ──────────────────────────────────────────
        fig_h = max(5, n * 0.72 + 3.2)
        fig, ax = plt.subplots(figsize=(10, fig_h))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#0d1117")

        # ── 그라데이션 색상 (점수 높을수록 밝은 골드) ──────────
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

        # ── 배경 그리드 ──────────────────────────────────────────
        ax.set_xlim(0, max_s * 1.18)
        ax.set_ylim(-0.6, n - 0.4)
        for x in np.linspace(0, max_s * 1.15, 6):
            ax.axvline(x, color="#1e2433", linewidth=0.8, zorder=0)

        # ── 막대 그래프 ──────────────────────────────────────────
        bars = ax.barh(y_pos, scores, height=0.72, color=colors,
                       alpha=0.88, zorder=3, edgecolor="none")

        # ── 막대 안에 종목명 + 점수 텍스트 ──────────────────────
        for i, (name, s, c, bar) in enumerate(zip(names, scores, colors, bars)):
            bar_w = bar.get_width()
            ax.text(bar_w * 0.04, y_pos[i], name,
                    va="center", ha="left",
                    fontsize=28, fontweight="bold",
                    color="#0d1117", zorder=5)
            ax.text(bar_w + max_s * 0.012, y_pos[i], f"{s}점",
                    va="center", ha="left",
                    fontsize=26, fontweight="bold",
                    color=c, zorder=5)

        # ── 순위 뱃지 (막대 왼쪽) ────────────────────────────────
        medals = {0: "1", 1: "2", 2: "3"}
        medal_bg = {0: "#FFD700", 1: "#C0C0C0", 2: "#CD7F32"}
        for i in range(min(3, n)):
            circle = plt.Circle((-max_s * 0.055, y_pos[i]), 0.22,
                                 color=medal_bg[i], zorder=6)
            ax.add_patch(circle)
            ax.text(-max_s * 0.055, y_pos[i], medals[i],
                    va="center", ha="center", fontsize=9,
                    fontweight="bold", color="#0d1117", zorder=7)

        # ── Y축 숨김 ─────────────────────────────────────────────
        ax.set_yticks([])
        ax.set_yticklabels([])

        # ── X축 스타일 ───────────────────────────────────────────
        ax.set_xlabel("종합 점수", color="#6b7280", fontsize=10, labelpad=8)
        ax.tick_params(axis="x", colors="#4a5568", labelsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color("#1e2433")

        # ── 타이틀 ───────────────────────────────────────────────
        today_str = date.today().strftime("%Y.%m.%d")
        fig.text(0.5, 0.98, "J.A.R.V.I.S.  SWING RADAR",
                 ha="center", va="top",
                 fontsize=36, fontweight="bold", color="#f0f4ff")
        fig.text(0.5, 0.89, f"급등 예고 종목  TOP {n}   |   {today_str}",
                 ha="center", va="top",
                 fontsize=24, color="#a0b4d0", style="italic")

        # ── 하단 워터마크 ────────────────────────────────────────
        fig.text(0.98, 0.01, "SWING RADAR  |  매일 15:40 자동 분석",
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
        print(f"[요약차트] 생성 오류: {e}")
        return None


def send_scan_alert(results: list, send_charts: bool = True):
    """스캔 결과 텔레그램 전송 (차트 이미지 포함)"""
    if not results:
        return

    today = date.today().strftime("%Y-%m-%d")

    # ── 요약 차트 먼저 전송 ──────────────────────────────────────
    summary_img = make_summary_chart(results)
    if summary_img:
        send_photo(summary_img, caption=f"📡 {today} 급등 예고 종목 TOP {min(len(results),10)}")

    # 요약 메시지 먼저 전송
    # 신규 / 추적 중 분류
    new_items = []
    tracking_items = []

    for r in results[:10]:
        lv = _calc_levels_from_result(r)
        already_tracking = False
        try:
            from cache_db import _get_conn as _db_conn
            _conn = _db_conn()
            # 오늘 이전에 알림 보낸 적 있고 아직 진행 중인 종목 = 추적 중
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
        entry_str  = f"₩{lv['entry']:,.0f}" if lv else f"₩{r['current_price']:,.0f}"
        target_str = f"₩{lv['target']:,.0f} (+{lv['upside']:.1f}%)" if lv else "-"
        stop_str   = f"₩{lv['stop']:,.0f} ({lv['downside']:.1f}%)" if lv else "-"
        rr_str     = f"{lv['rr']:.1f} : 1" if lv else "-"
        per_str = f"PER {fin['per']}" if fin.get("per") else ""
        pbr_str = f"PBR {fin['pbr']}" if fin.get("pbr") else ""
        fin_str = "  ".join(filter(None, [per_str, pbr_str]))
        block = (
            f"\n<b>{idx}. {r['name']} ({r['symbol']})</b> ⭐ {r['total_score']}점\n"
            f"📍 매수가:  {entry_str}\n"
            f"🎯 목표가:  {target_str}\n"
            f"🛑 손절가:  {stop_str}\n"
            f"⚖️ 손익비:  {rr_str}\n"
        )
        if fin_str:
            block += f"📊 {fin_str}\n"
        if sig_str:
            block += f"{sig_str}\n"
        block += "━" * 20
        return block

    summary_lines = [f"📡 <b>스윙 레이더</b> ({today} 장마감) — {len(results[:10])}개\n{'━'*20}"]

    idx = 1
    if new_items:
        summary_lines.append(f"\n🆕 <b>신규 탐지</b>\n{'━'*20}")
        for r, lv in new_items:
            summary_lines.append(_make_block(r, lv, idx))
            idx += 1
    else:
        summary_lines.append(f"\n🆕 <b>신규 탐지</b>  없음\n{'━'*20}")

    if tracking_items:
        summary_lines.append(f"\n🔄 <b>재탐지 (추적 중)</b>\n{'━'*20}")
        for r, lv in tracking_items:
            summary_lines.append(_make_block(r, lv, idx))
            idx += 1

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
    # 차트 이미지 전송 + 성과 추적 저장
    price_levels_map = {}
    if send_charts:
        for r in results[:5]:
            lv = _calc_levels_from_result(r)
            # 이미 추적 중인 종목은 DB 기존 가격 사용
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
            except Exception:
                pass
            price_levels_map[r["symbol"]] = lv
            close_s = r.get("close_series")
            img = None
            try:
                if close_s is not None:
                    if not hasattr(close_s, 'rolling'):
                        close_s = pd.Series(list(close_s))
                    # datetime 인덱스가 있으면 스캔 데이터로 차트 생성
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
                print(f"스캔데이터 차트 오류 {r['symbol']}: {ce}")
            # 스캔 데이터로 실패하면 yfinance로 폴백
            if img is None:
                img = make_chart_image(r["symbol"], r["name"], price_levels=lv)
            if img:
                if lv:
                    caption = (
                        f"<b>{r['name']}</b> ⭐{r['total_score']}점\n"
                        f"📍 매수가: ₩{lv['entry']:,.0f}\n"
                        f"🎯 목표가: ₩{lv['target']:,.0f} (+{lv['upside']:.1f}%)\n"
                        f"🛑 손절가: ₩{lv['stop']:,.0f} ({lv['downside']:.1f}%)\n"
                        f"⚖️ 손익비: {lv['rr']:.1f}:1"
                    )
                else:
                    caption = f"<b>{r['name']}</b>"
                send_photo(img, caption)

    # ── 성과 추적 DB 저장 ──────────────────────────────────────
    try:
        from cache_db import save_alert_history
        # 차트 없는 종목도 포함해서 전체 저장
        for r in results:
            if r["symbol"] not in price_levels_map:
                price_levels_map[r["symbol"]] = calc_price_levels(r["symbol"])
        save_alert_history(results, price_levels_map)
        print(f"[성과추적] {len(results)}개 종목 저장 완료")
    except Exception as e:
        print(f"[성과추적] 저장 오류: {e}")


def send_test_alert():
    return send_telegram(
        "✅ <b>HotStock 알림 봇 연결 완료!</b>\n"
        "매일 장 마감 후 급등 예고 종목을 자동으로 알려드립니다. 🚀"
    )


def send_performance_update():
    """성과 업데이트 알림"""
    try:
        from cache_db import update_alert_status, get_alert_history, get_performance_summary
        import yfinance as yf

        update_alert_status()

        today = date.today().isoformat()
        today_fmt = date.today().strftime("%Y.%m.%d")
        history = get_alert_history(200)

        hit_target_today = [h for h in history if h["status"] == "hit_target" and h.get("exit_date") == today]
        hit_stop_today   = [h for h in history if h["status"] == "hit_stop"   and h.get("exit_date") == today]
        # symbol 기준 중복 제거
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
            print("[성과추적] 오늘 상태 변경 없음 - 알림 생략")
            return

        lines = [
            f"📊 <b>포트폴리오 현황</b>  {today_fmt}",
            "─" * 16,
        ]

        # ── 오늘 청산 ──────────────────────────────
        if hit_target_today or hit_stop_today:
            lines.append("\n🔔 <b>오늘 청산</b>")
            lines.append("─" * 16)
            for h in hit_target_today:
                ret  = h['return_pct'] if h.get('return_pct') is not None else 0
                exit_p = f"₩{h['exit_price']:,.0f}" if h.get('exit_price') else "?"
                lines.append(
                    f"✅ <b>{h['name']}</b>\n"
                    f"   체결가 {exit_p}  |  수익 <b>+{ret:.1f}%</b> 🎉"
                )
            for h in hit_stop_today:
                ret  = h['return_pct'] if h.get('return_pct') is not None else 0
                exit_p = f"₩{h['exit_price']:,.0f}" if h.get('exit_price') else "?"
                lines.append(
                    f"🛑 <b>{h['name']}</b>\n"
                    f"   체결가 {exit_p}  |  손실 {ret:.1f}%"
                )

        # ── 매수 중 ────────────────────────────────
        if active_list:
            lines.append(f"\n🟢 <b>매수 중</b>  ({len(active_list)}종목)")
            lines.append("─" * 16)
            for h in active_list:
                days       = (date.today() - date.fromisoformat(h["alert_date"])).days
                base_price = h.get("avg_price") or h.get("entry_price")
                avg_str    = f"₩{base_price:,.0f}" if base_price else "미정"
                target_str = f"₩{h['target_price']:,.0f}" if h.get("target_price") else "?"
                stop_str   = f"₩{h['stop_price']:,.0f}"   if h.get("stop_price")   else "?"
                # 분할매수 차수 표시
                split_step = h.get("split_step", 1) or 1
                split_tag  = f" <i>({split_step}차 평균)</i>" if split_step > 1 else ""

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
                                bar = "🟩" * bar_filled + "⬜" * (8 - bar_filled)
                            elif ret < 0 and stop < entry:
                                ratio = min((entry - cur) / (entry - stop), 1.0)
                                bar_filled = round(ratio * 8)
                                bar = "🟥" * bar_filled + "⬜" * (8 - bar_filled)
                            else:
                                bar = "⬜" * 8
                        else:
                            bar_filled = min(int(abs(ret) / 2), 8)
                            bar = ("🟩" if ret >= 0 else "🟥") * bar_filled + "⬜" * (8 - bar_filled)
                        cur_line = f"\n   {bar}  <b>₩{cur:,.0f}  ({ret:+.1f}%)</b>"
                except:
                    pass

                lines.append(
                    f"📌 <b>{h['name']}</b>  <i>{days}일째</i>\n"
                    f"   평균단가 {avg_str}{split_tag}  →  목표 {target_str}  /  손절 {stop_str}"
                    + cur_line
                )

        # ── 매수 대기 ──────────────────────────────
        if still_pending:
            lines.append(f"\n⏳ <b>매수 대기</b>  ({len(still_pending)}종목)")
            lines.append("─" * 16)
            for h in still_pending:
                days      = (date.today() - date.fromisoformat(h["alert_date"])).days
                entry_str = f"₩{h['entry_price']:,.0f}"  if h.get("entry_price")  else "미정"
                target_str= f"₩{h['target_price']:,.0f}" if h.get("target_price") else "?"
                lines.append(
                    f"🔵 <b>{h['name']}</b>  <i>{days}일째 대기</i>\n"
                    f"   진입가 {entry_str}  →  목표 {target_str}"
                )

        lines.append("\n─" * 8)
        lines.append("⚠️ <i>투자 참고용 정보입니다</i>")

        send_telegram("\n".join(lines))
        print("[성과추적] 업데이트 알림 전송 완료")

    except Exception as e:
        print(f"[성과추적] 알림 오류: {e}")
        import traceback; traceback.print_exc()



def send_weekly_summary(force: bool = False):
    """주간 성과 요약 - 매주 금요일 전송"""
    try:
        from cache_db import get_performance_summary, get_alert_history
        from datetime import datetime, timedelta
        import yfinance as yf

        if not force and datetime.now().weekday() != 4:
            return

        # 전체 누적 통계
        perf       = get_performance_summary()
        history    = get_alert_history(200)
        today      = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_start_str = week_start.isoformat()

        # 이번 주 신규 알림 종목
        this_week    = [h for h in history if h["alert_date"] >= week_start_str]
        # 현재 진행 중인 종목 (전체 기간, active/pending 모두 매수 중으로 표시)
        _seen = set()
        active_list = []
        for h in history:
            if h["status"] in ("active", "pending") and h["symbol"] not in _seen:
                active_list.append(h)
                _seen.add(h["symbol"])
        _seen2 = set()
        pending_list = []
        # pending은 active_list에 이미 포함됨 - 별도 표시 안 함
        # 이번 주 청산된 종목
        closed_this_week = [h for h in this_week if h["status"] in ("hit_target", "hit_stop", "expired")]

        if perf["total"] == 0 and not this_week and not active_list and not pending_list:
            print("[성과추적] 주간 요약 데이터 없음 - 생략")
            return

        win_rate = perf["win_rate"]
        avg_ret  = perf["avg_return"]
        period   = f"{week_start.strftime('%m/%d')} ~ {today.strftime('%m/%d')}"

        lines = [f"📅 <b>주간 리포트</b>  {period}", "─" * 16]

        # ── 1. 매수 중 (전체 기간 active) ──────────
        if active_list:
            lines.append(f"\n🟢 <b>매수 중</b>  ({len(active_list)}종목)")
            lines.append("─" * 16)
            for h in active_list:
                base_price = h.get("avg_price") or h.get("entry_price")
                avg_str    = f"₩{base_price:,.0f}" if base_price else "미정"
                target_str = f"₩{h['target_price']:,.0f}" if h.get("target_price") else "?"
                stop_str   = f"₩{h['stop_price']:,.0f}"   if h.get("stop_price")   else "?"
                split_step = h.get("split_step", 1) or 1
                split_tag  = f" <i>({split_step}차 평균)</i>" if split_step > 1 else ""
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
                                bar = "🟩" * filled + "⬜" * (8 - filled)
                            elif ret < 0 and stop < entry_p:
                                ratio = min((entry_p - cur) / (entry_p - stop), 1.0)
                                filled = round(ratio * 8)
                                bar = "🟥" * filled + "⬜" * (8 - filled)
                            else:
                                bar = "⬜" * 8
                        else:
                            filled = min(int(abs(ret) / 2), 8)
                            bar = ("🟩" if ret >= 0 else "🟥") * filled + "⬜" * (8 - filled)
                        cur_line = f"\n   {bar}  ₩{cur:,.0f}  <b>({ret:+.1f}%)</b>"
                except:
                    pass
                lines.append(
                    f"📌 <b>{h['name']}</b>\n"
                    f"   평균단가 {avg_str}{split_tag}  🎯{target_str}  🛑{stop_str}"
                    + cur_line
                )

        # ── 2. 누적 성과 통계 (전체 기간) ──────────
        lines.append("\n📊 <b>누적 성과</b>  <i>(전체 기간)</i>")
        lines.append("─" * 16)
        if perf["total"] > 0:
            filled = round(win_rate / 10)
            bar = "🟩" * filled + "⬜" * (10 - filled)
            wr_label = "우수" if win_rate >= 60 else "보통" if win_rate >= 40 else "부진"
            lines.append(f"  {bar}  {win_rate}%  <i>{wr_label}</i>")
            lines.append(f"  ✅ {perf['win']}건  🛑 {perf['loss']}건  ⌛ {perf.get('expired',0)}건")
            ret_arrow = "📈" if avg_ret >= 0 else "📉"
            lines.append(f"  {ret_arrow} 평균 수익률  <b>{avg_ret:+.1f}%</b>")
            if perf["win"] > 0:
                lines.append(f"     수익 평균  <b>+{perf['avg_win']:.1f}%</b>")
            if perf["loss"] > 0:
                lines.append(f"     손실 평균  <b>{perf['avg_loss']:.1f}%</b>")
        else:
            lines.append("  아직 청산 데이터 없음")

        # ── 최근 청산 내역 5건 ─────────────────────
        try:
            from cache_db import get_recent_closed
            recent = get_recent_closed(5)
            if recent:
                lines.append(f"\n📋 <b>최근 청산 내역</b>")
                lines.append("─" * 16)
                for r in recent:
                    icon = "💰" if r["status"] == "hit_target" else ("🛑" if r["status"] == "hit_stop" else "⌛")
                    ret_str = f"  <b>{r['return_pct']:+.1f}%</b>" if r["return_pct"] is not None else ""
                    date_str = r["exit_date"][5:] if r["exit_date"] else ""  # MM-DD
                    lines.append(f"  {icon} {r['name']}{ret_str}  <i>({date_str})</i>")
        except Exception:
            pass

        # ── 3. 매수 대기 ───────────────────────────
        if pending_list:
            lines.append(f"\n⏳ <b>매수 대기</b>  ({len(pending_list)}종목)")
            lines.append("─" * 16)
            for h in pending_list:
                # 거래일 기준 경과일 계산
                try:
                    from datetime import timedelta
                    alert_dt = date.fromisoformat(h["alert_date"])
                    trading_days = 0
                    cur_day = alert_dt
                    while cur_day < today:
                        cur_day += timedelta(days=1)
                        if cur_day.weekday() < 5:
                            trading_days += 1
                    days_str = f"{trading_days}거래일째"
                except:
                    days_str = f"{(today - date.fromisoformat(h['alert_date'])).days}일째"
                entry_str  = f"₩{h['entry_price']:,.0f}"  if h.get("entry_price")  else "미정"
                target_str = f"₩{h['target_price']:,.0f}" if h.get("target_price") else "?"
                lines.append(f"🔵 <b>{h['name']}</b>  <i>{days_str}</i>\n   진입가 {entry_str}  →  목표 {target_str}")

        # ── 푸터 ───────────────────────────────────
        lines.append(f"\n🟢 매수 중 {len(active_list)}종목  ·  ⏳ 대기 {len(pending_list)}종목")
        lines.append("─" * 16)
        lines.append("⚠️ <i>투자 참고용 정보입니다</i>")

        send_telegram("\n".join(lines))
        print("[성과추적] 주간 요약 전송 완료")

    except Exception as e:
        print(f"[성과추적] 주간 요약 오류: {e}")
        import traceback; traceback.print_exc()
