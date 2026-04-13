"""
코인 급등 예측 - Streamlit 앱 v2.0
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timezone

try:
    from crypto_surge_detector import CryptoSurgeDetector, fetch_ohlcv
    from cache_db import (save_scan, load_scan, list_scan_dates,
                          save_alert_history, update_alert_status,
                          get_performance_summary)
    from symbols import COIN_NAMES, CRYPTO_SYMBOLS
except Exception as e:
    st.error(f"Import error: {e}")
    st.stop()

# ── 페이지 설정 (최상단) ─────────────────────────────────────────
st.set_page_config(
    page_title="코인 급등 예측",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── 인증 ─────────────────────────────────────────────────────────
try:
    PASSWORDS = list(st.secrets.get("PASSWORDS", ["comfreec", "vip1234"]))
except:
    PASSWORDS = ["comfreec", "vip1234"]

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.markdown("""
    <style>
    @keyframes fadein { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }
    @keyframes coin_spin {
        0%   { transform: rotateY(0deg) translateY(0px); }
        25%  { transform: rotateY(90deg) translateY(-20px); }
        50%  { transform: rotateY(180deg) translateY(0px); }
        75%  { transform: rotateY(270deg) translateY(-20px); }
        100% { transform: rotateY(360deg) translateY(0px); }
    }
    .login-box { animation: fadein 0.6s ease; }
    .coin-wrap {
        display: inline-block;
        animation: coin_spin 2s linear infinite;
        perspective: 200px;
        margin-bottom: 8px;
    }
    .coin-face {
        width: 72px; height: 72px;
        border-radius: 50%;
        background: radial-gradient(circle at 35% 35%, #ffe066, #f7a44f 60%, #c47a00);
        border: 4px solid #ffd700;
        box-shadow: 0 0 24px rgba(247,164,79,0.7), inset 0 2px 6px rgba(255,255,255,0.4);
        display: flex; align-items: center; justify-content: center;
        font-size: 32px; font-weight: 900;
        color: #7a4800;
        text-shadow: 1px 1px 2px rgba(255,255,255,0.4);
        font-family: Arial, sans-serif;
    }
    </style>
    <div class='login-box' style='max-width:420px;margin:80px auto;'>
      <div style='background:linear-gradient(135deg,#1a1f35,#0e1117);
           padding:48px 40px;border-radius:20px;border:1px solid #2d3555;
           box-shadow:0 20px 60px rgba(0,0,0,0.5);text-align:center;'>
        <div class='coin-wrap'><div class='coin-face'>₿</div></div>
        <h2 style='color:#fff;margin:16px 0 6px;font-size:26px;font-weight:800;letter-spacing:-0.5px;'>코인 급등 예측</h2>
        <p style='color:#f7a44f;font-size:13px;margin:0 0 32px;font-weight:500;letter-spacing:2px;'>CRYPTO SURGE PREDICTOR</p>
        <div style='width:40px;height:2px;background:linear-gradient(90deg,#f7a44f,#ffd700);margin:0 auto 32px;border-radius:2px;'></div>
        <p style='color:#8b92a5;font-size:13px;margin:0 0 24px;'>허가된 사용자만 접근 가능합니다</p>
      </div>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pw = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력", label_visibility="collapsed")
        if st.button("로그인", type="primary", use_container_width=True):
            if pw in PASSWORDS:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다")
    st.stop()

# ── CSS ──────────────────────────────────────────────────────────
st.markdown("""<style>
@viewport { width: device-width; }
.main .block-container { padding: 0.5rem 0.8rem !important; max-width: 100% !important; }
section[data-testid="stSidebar"] {
    min-width: 240px !important; max-width: 260px !important;
    background: linear-gradient(180deg, #0d1117 0%, #0e1117 100%) !important;
    border-right: 1px solid #1e2540 !important;
}
section[data-testid="stSidebar"] .block-container { padding: 1rem 0.8rem !important; }
.stApp { background: #080c14 !important; }
.main  { background: #080c14 !important; }
.top-header {
    background: linear-gradient(135deg, #0d1528 0%, #111827 50%, #0d1528 100%);
    padding: 28px 36px; border-radius: 20px; margin-bottom: 20px;
    border: 1px solid rgba(247,164,79,0.25);
    box-shadow: 0 0 40px rgba(247,164,79,0.08);
}
.market-card {
    background: linear-gradient(135deg, #111827, #1a2035);
    border: 1px solid rgba(61,68,102,0.6); border-radius: 12px;
    padding: 14px 12px; text-align: center; margin: 4px;
}
.metric-card {
    background: linear-gradient(135deg, #111827, #1a2035);
    border: 1px solid rgba(61,68,102,0.6); border-radius: 14px;
    padding: 18px 14px; text-align: center; margin: 4px;
}
.metric-card .lbl { color: #6b7280; font-size: 11px; font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase; }
.metric-card .val { color: #f0f4ff; font-size: 24px; font-weight: 800; margin-top: 4px; }
.rank-card {
    background: linear-gradient(135deg, #0f1623, #131d2e);
    border-left: 3px solid #f7a44f;
    border-top: 1px solid rgba(255,255,255,0.05);
    border-right: 1px solid rgba(255,255,255,0.03);
    border-bottom: 1px solid rgba(255,255,255,0.03);
    border-radius: 14px; padding: 18px 20px; margin: 10px 0;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
.rank-card.gold   { border-left-color: #ffd700; background: linear-gradient(135deg, #141208, #1a1a0f); }
.rank-card.silver { border-left-color: #c0c0c0; background: linear-gradient(135deg, #111318, #181b22); }
.rank-card.bronze { border-left-color: #cd7f32; background: linear-gradient(135deg, #130f0a, #1a1510); }
.bar-bg   { background: rgba(30,33,48,0.8); border-radius: 10px; height: 6px; width: 100%; overflow: hidden; }
.bar-fill { background: linear-gradient(90deg, #f7a44f, #ffd700); border-radius: 10px; height: 6px; }
.sec-title { font-size: clamp(15px,3vw,19px); font-weight: 700; color: #e8edf8; margin: 24px 0 12px; padding-bottom: 8px; border-bottom: 1px solid rgba(45,53,85,0.8); }
.cond-box { background: linear-gradient(135deg,#0d1528,#111827); border: 1px solid rgba(247,164,79,0.2); border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; font-size: 13px; color: #8b92a5; }
/* 사이드바 텍스트 */
section[data-testid="stSidebar"] label { color: #e8edf8 !important; }
section[data-testid="stSidebar"] p { color: #c9d1e0 !important; }
section[data-testid="stSidebar"] th, section[data-testid="stSidebar"] td { color: #c9d1e0 !important; }
/* 최적셋팅 버튼 */
section[data-testid="stSidebar"] div[data-testid="stButton"] button {
    background: linear-gradient(135deg, #f7a44f, #ffd700) !important;
    color: #000000 !important; font-weight: 800 !important; border: none !important;
}
section[data-testid="stSidebar"] div[data-testid="stButton"] button p,
section[data-testid="stSidebar"] div[data-testid="stButton"] button span {
    color: #000000 !important;
}
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #2d3555; border-radius: 3px; }
@media (max-width: 768px) {
    .main .block-container { padding: 0.3rem 0.3rem !important; }
    .metric-card { padding: 10px 6px !important; }
    .metric-card .val { font-size: 16px !important; }
    .rank-card { padding: 10px 12px !important; }
    .top-header { padding: 16px 18px !important; }
}
</style>""", unsafe_allow_html=True)

# ── 헬퍼 함수 ────────────────────────────────────────────────────
def metric_card(col, label, value):
    col.markdown(f"""<div class="metric-card">
        <div class="lbl">{label}</div><div class="val">{value}</div>
    </div>""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def get_usd_krw() -> float:
    """USD/KRW 환율 조회 - 여러 소스 순차 시도"""
    import urllib.request, json
    try:
        with urllib.request.urlopen("https://open.er-api.com/v6/latest/USD", timeout=5) as r:
            return float(json.loads(r.read())["rates"]["KRW"])
    except:
        pass
    try:
        with urllib.request.urlopen("https://api.frankfurter.app/latest?from=USD&to=KRW", timeout=5) as r:
            return float(json.loads(r.read())["rates"]["KRW"])
    except:
        pass
    try:
        import ccxt
        upbit   = ccxt.upbit({"enableRateLimit": True})
        binance = ccxt.binance({"enableRateLimit": True})
        return float(upbit.fetch_ticker("BTC/KRW")["last"]) / float(binance.fetch_ticker("BTC/USDT")["last"])
    except:
        pass
    return 1450.0

def _krw(usd_val, rate=None):
    """USD 값을 원화 문자열로 변환"""
    if usd_val is None:
        return "-"
    if rate is None:
        rate = get_usd_krw()
    return f"₩{int(usd_val * rate):,}"

def calc_rsi(close, period=14):
    d = close.diff()
    gain = d.where(d > 0, 0.0)
    loss = -d.where(d < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))

# ── 시장 현황 ─────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_market_overview():
    """업비트 원화 기준 시장 현황"""
    try:
        import ccxt
        upbit = ccxt.upbit({"enableRateLimit": True})
        symbols = ["BTC/KRW", "ETH/KRW", "BNB/KRW", "SOL/KRW"]
        result = {}
        for sym in symbols:
            try:
                t = upbit.fetch_ticker(sym)
                result[sym] = {"price": float(t.get("last", 0)), "change": float(t.get("percentage", 0))}
            except:
                pass
        return result
    except:
        return {}

@st.cache_data(ttl=3600)
def get_fear_greed():
    try:
        import ccxt
        ex = ccxt.binance({"enableRateLimit": True})
        raw = ex.fetch_ohlcv("BTC/USDT", "1d", limit=30)
        closes = [r[4] for r in raw]
        rets = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
        vol = float(pd.Series(rets).std() * 100)
        mom = float((closes[-1] - closes[-7]) / closes[-7] * 100)
        rsi_val = float(calc_rsi(pd.Series(closes), 14).dropna().iloc[-1])
        score = max(0, min(100, 50 + mom * 2 - vol * 3 + (rsi_val - 50) * 0.5))
        if score >= 75:   label, color = "극도의 탐욕", "#ff3355"
        elif score >= 55: label, color = "탐욕", "#ff8c42"
        elif score >= 45: label, color = "중립", "#ffd700"
        elif score >= 25: label, color = "공포", "#4f8ef7"
        else:             label, color = "극도의 공포", "#00d4aa"
        return int(score), label, color
    except:
        return None, None, None

@st.cache_data(ttl=300)
def get_chart_data(symbol, limit=200):
    return fetch_ohlcv(symbol, limit=limit)

def make_candle(data, title, show_levels=True):
    fig = go.Figure()
    fig.add_trace(go.Ohlc(
        x=data.index, open=data["Open"], high=data["High"],
        low=data["Low"], close=data["Close"], name="가격",
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350"
    ))
    for w, c, nm in [(20, "#a78bfa", "MA20"), (50, "#4f8ef7", "MA50"), (240, "#ff9800", "MA200")]:
        ma = data["Close"].rolling(w).mean()
        fig.add_trace(go.Scatter(x=data.index, y=ma, name=nm,
            line=dict(color=c, width=2.5 if w == 240 else 1.2)))

    price_levels = None
    if show_levels and len(data) >= 20:
        close   = data["Close"].dropna()
        high    = data["High"].dropna()
        low     = data["Low"].dropna()
        current = float(close.iloc[-1])

        tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().dropna().iloc[-1])

        ma200_v = float(close.rolling(240).mean().dropna().iloc[-1]) if len(close) >= 240 else None
        ma20_v  = float(close.rolling(20).mean().dropna().iloc[-1])
        swing_low = float(low.tail(20).min())

        entry_cands = []
        if ma200_v and ma200_v * 1.005 < current:
            entry_cands.append(("MA200", ma200_v * 1.005))
        if ma20_v < current:
            entry_cands.append(("MA20", ma20_v))
        if swing_low < current:
            entry_cands.append(("스윙저점", swing_low))

        if entry_cands:
            entry_label = "+".join(l for l, _ in entry_cands)
            entry = sum(p for _, p in entry_cands) / len(entry_cands)
        else:
            entry_label, entry = "현재가", current

        stop = entry * 0.95
        risk = max(entry - stop, entry * 0.01)

        recent_high = float(high.tail(120).max())
        recent_low  = float(low.tail(120).min())
        swing_range = max(recent_high - recent_low, entry * 0.01)

        cands = sorted([x for x in [
            recent_low + swing_range * 1.272,
            recent_low + swing_range * 1.618,
            recent_low + swing_range * 2.0,
            entry + atr * 3.0, entry + atr * 5.0,
        ] if x > entry * 1.03])

        valid3 = [x for x in cands if x >= entry + risk * 3.0]
        target = valid3[0] if valid3 else (cands[-1] if cands else entry + risk * 3.0)
        target = min(target, current * 2.5)

        rr_ratio = (target - entry) / (risk + 1e-9)
        upside   = (target / entry - 1) * 100
        downside = (stop / entry - 1) * 100

        fig.add_hline(y=target, line=dict(color="#00ff88", width=2, dash="dash"))
        fig.add_hrect(y0=entry, y1=target, fillcolor="rgba(0,255,136,0.06)", line_width=0)
        if entry < current:
            fig.add_hline(y=entry, line=dict(color="#ffd700", width=2, dash="dashdot"))
            fig.add_hrect(y0=stop, y1=entry, fillcolor="rgba(255,51,85,0.06)", line_width=0)
        fig.add_hline(y=current, line=dict(color="#ffffff", width=1.5, dash="dot"))
        fig.add_hline(y=stop, line=dict(color="#ff3355", width=2, dash="dash"))

        price_levels = dict(target=target, current=current, entry=entry,
                            entry_label=entry_label, stop=stop,
                            upside=upside, downside=downside, rr_ratio=rr_ratio)

    fig.update_layout(
        title=dict(text=title, font=dict(color="#e0e6f0", size=13)),
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font=dict(color="#8b92a5"),
        yaxis=dict(gridcolor="#1e2540", fixedrange=True, side="right"),
        xaxis=dict(gridcolor="#1e2540", rangeslider_visible=False, fixedrange=True),
        legend=dict(bgcolor="#1e2130", bordercolor="#2d3555", visible=True,
                    orientation="h", y=1.02, font=dict(size=10)),
        dragmode=False, height=500, margin=dict(l=0, r=50, t=30, b=0)
    )
    fig._price_levels = price_levels
    return fig

def show_price_levels(fig):
    lv = getattr(fig, "_price_levels", None)
    if not lv:
        return
    rr = lv["rr_ratio"]
    rr_color = "#00ff88" if rr >= 3 else "#ffd700" if rr >= 2 else "#ff8c42"
    rr_label  = "우수" if rr >= 3 else "양호" if rr >= 2 else "주의"
    st.markdown(f"""
    <div style='display:flex;gap:8px;margin:-8px 0 4px;'>
      <div style='flex:1.2;background:rgba(0,255,136,0.08);border:1px solid #00ff88;border-radius:10px;padding:12px;text-align:center;'>
        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>🎯 목표가</div>
        <div style='color:#00ff88;font-size:18px;font-weight:700;margin:4px 0;'>{int(lv["target"] * get_usd_krw()):,}원</div>
        <div style='color:#00ff88;font-size:12px;'>+{lv["upside"]:.1f}%</div>
      </div>
      <div style='flex:1;background:rgba(255,215,0,0.08);border:1px solid #ffd700;border-radius:10px;padding:12px;text-align:center;'>
        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>📍 매수가</div>
        <div style='color:#ffd700;font-size:18px;font-weight:700;margin:4px 0;'>{int(lv["entry"] * get_usd_krw()):,}원</div>
        <div style='color:#ffd700;font-size:12px;'>{lv.get("entry_label","근거가")} 기준</div>
      </div>
      <div style='flex:1;background:rgba(255,51,85,0.08);border:1px solid #ff3355;border-radius:10px;padding:12px;text-align:center;'>
        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>🛑 손절가</div>
        <div style='color:#ff3355;font-size:18px;font-weight:700;margin:4px 0;'>{int(lv["stop"] * get_usd_krw()):,}원</div>
        <div style='color:#ff3355;font-size:12px;'>{lv["downside"]:.1f}%</div>
      </div>
      <div style='flex:0.8;background:rgba(255,215,0,0.08);border:1px solid {rr_color};border-radius:10px;padding:12px;text-align:center;'>
        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>⚖️ 손익비</div>
        <div style='color:{rr_color};font-size:22px;font-weight:700;margin:4px 0;'>{rr:.1f}:1</div>
        <div style='color:{rr_color};font-size:11px;'>{rr_label}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── 헤더 ─────────────────────────────────────────────────────────
market = get_market_overview()
fear_score, fear_label, fear_color = get_fear_greed()
now_str = datetime.now(timezone.utc).strftime("%Y.%m.%d %H:%M UTC")

st.markdown("""
<style>
@keyframes header_coin_spin {
    0%   { transform: rotateY(0deg) translateY(0px); }
    25%  { transform: rotateY(90deg) translateY(-8px); }
    50%  { transform: rotateY(180deg) translateY(0px); }
    75%  { transform: rotateY(270deg) translateY(-8px); }
    100% { transform: rotateY(360deg) translateY(0px); }
}
.header-coin-wrap {
    display: inline-block;
    animation: header_coin_spin 2.5s linear infinite;
    vertical-align: middle;
}
.header-coin {
    width: 52px; height: 52px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 35%, #ffe066, #f7a44f 60%, #c47a00);
    border: 3px solid #ffd700;
    box-shadow: 0 0 20px rgba(247,164,79,0.7), inset 0 2px 5px rgba(255,255,255,0.4);
    display: flex; align-items: center; justify-content: center;
    font-size: 24px; font-weight: 900; color: #7a4800;
    font-family: Arial, sans-serif;
}
</style>
<div class="top-header">
  <div style="display:flex;align-items:center;gap:12px;">
    <div class='header-coin-wrap'><div class='header-coin'>₿</div></div>
    <div>
      <h1 style="color:#f0f4ff;margin:0;font-size:clamp(18px,4vw,28px);font-weight:800;">코인 급등 예측 시스템</h1>
      <p style="color:#f7a44f;margin:4px 0 0;font-size:12px;font-weight:600;letter-spacing:2px;text-transform:uppercase;">Crypto Surge Predictor v2.0</p>
    </div>
  </div>
  <p style="color:#6b7280;margin:12px 0 0;font-size:13px;line-height:1.6;">
    200일선 아래 충분한 조정 → 최근 돌파 → 현재 근처 → 급등 신호 복합 확인 | 24/7 자동 스캔
  </p>
</div>""", unsafe_allow_html=True)

cols_m = st.columns([1, 1, 1, 1, 2])
market_items = [("BTC/KRW", "비트코인"), ("ETH/KRW", "이더리움"), ("BNB/KRW", "바이낸스"), ("SOL/KRW", "솔라나")]
for col, (sym, name) in zip(cols_m[:4], market_items):
    d = market.get(sym, {})
    price = d.get("price", 0)
    chg   = d.get("change", 0)
    color = "#26a69a" if chg >= 0 else "#ef5350"
    arrow = "▲" if chg >= 0 else "▼"
    col.markdown(f"""<div class='market-card'>
      <div style='color:#6b7280;font-size:10px;font-weight:600;letter-spacing:1px;text-transform:uppercase;'>{name}</div>
      <div style='color:#f0f4ff;font-size:18px;font-weight:800;margin:4px 0;'>₩{int(price):,}</div>
      <div style='color:{color};font-size:13px;font-weight:600;'>{arrow} {abs(chg):.2f}%</div>
    </div>""", unsafe_allow_html=True)

if fear_score is not None:
    bar_color = "#ff3355" if fear_score >= 75 else "#ff8c42" if fear_score >= 55 else "#ffd700" if fear_score >= 45 else "#4f8ef7"
    cols_m[4].markdown(f"""<div class='market-card' style='display:flex;justify-content:space-between;align-items:center;'>
      <div>
        <div style='color:#6b7280;font-size:10px;font-weight:600;letter-spacing:1px;text-transform:uppercase;'>공포/탐욕</div>
        <div style='color:{fear_color};font-size:20px;font-weight:800;margin:4px 0;'>{fear_score}</div>
        <div style='color:{fear_color};font-size:12px;font-weight:600;'>{fear_label}</div>
        <div style='background:rgba(255,255,255,0.06);border-radius:4px;height:3px;margin-top:6px;'>
          <div style='background:{bar_color};width:{fear_score}%;height:3px;border-radius:4px;'></div>
        </div>
      </div>
      <div style='text-align:right;'>
        <div style='color:#6b7280;font-size:10px;'>기준시각</div>
        <div style='color:#e8edf8;font-size:13px;font-weight:700;margin-top:4px;'>{now_str}</div>
      </div>
    </div>""", unsafe_allow_html=True)

# ── 탭 메뉴 ──────────────────────────────────────────────────────
if "mode" not in st.session_state:
    st.session_state["mode"] = "🔍 급등 예고 코인 탐지"

tab_labels = ["🔍 급등 예고 코인 탐지", "🎯 최적 급등 타이밍", "📈 개별 코인 분석", "⭐ 즐겨찾기", "📊 히스토리", "📈 성과 추적"]
tab_cols = st.columns(6)
for i, (col, label) in enumerate(zip(tab_cols, tab_labels)):
    active = st.session_state["mode"] == label
    if col.button(label, key=f"tab_{i}", use_container_width=True,
                  type="primary" if active else "secondary"):
        st.session_state["mode"] = label
        st.rerun()

mode = st.session_state["mode"]
st.markdown("---")

# ── 사이드바 ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <style>
    @keyframes sidebar_coin_spin {
        0%   { transform: rotateY(0deg); }
        100% { transform: rotateY(360deg); }
    }
    .sidebar-coin-wrap {
        display: inline-block;
        animation: sidebar_coin_spin 3s linear infinite;
    }
    .sidebar-coin {
        width: 44px; height: 44px;
        border-radius: 50%;
        background: radial-gradient(circle at 35% 35%, #ffe066, #f7a44f 60%, #c47a00);
        border: 3px solid #ffd700;
        box-shadow: 0 0 14px rgba(247,164,79,0.6), inset 0 2px 4px rgba(255,255,255,0.4);
        display: flex; align-items: center; justify-content: center;
        font-size: 20px; font-weight: 900; color: #7a4800;
        font-family: Arial, sans-serif;
    }
    </style>
    <div style='text-align:center;padding:8px 0 4px;'>
      <div class='sidebar-coin-wrap'><div class='sidebar-coin'>₿</div></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<h3 style='color:#f0f4ff;text-align:center;margin:6px 0 2px;'>코인 급등 예측</h3>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("<h3 style='color:#f0f4ff;'>⚙️ 핵심 조건 설정</h3>", unsafe_allow_html=True)

    DEFAULTS = {"max_gap": 10, "min_below": 120, "max_cross": 60, "min_score": 15}
    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if st.button("⚡ 최적 셋팅", use_container_width=True):
        st.session_state["max_gap"]   = 10
        st.session_state["min_below"] = 120
        st.session_state["max_cross"] = 60
        st.session_state["min_score"] = 15
        st.rerun()

    max_gap   = st.slider("📍 200선 근처 범위 (%)", 1, 20, key="max_gap",
        help="현재가가 200일선 위 몇 % 이내인지")
    min_below = st.slider("📉 최소 조정 기간 (일)", 60, 300, key="min_below",
        help="200일선 아래 최소 체류 일수 (120=6개월)")
    max_cross = st.slider("📈 돌파 후 최대 경과 (일)", 10, 180, key="max_cross",
        help="200일선 돌파 후 최대 경과 일수")
    min_score = st.slider("🎯 최소 종합점수", 0, 40, key="min_score",
        help="이 점수 이상인 코인만 표시")

    st.markdown("---")
    st.markdown("""**📊 추가 점수 신호**
| 신호 | 점수 |
|------|------|
| 🚀 돌파 시 거래량 폭발(3배+) | 4점 |
| 📦 돌파 시 거래량 급증(2배+) | 3점 |
| 📊 최근 거래량 증가 | 2점 |
| 📈 OBV 지속 상승 | 2점 |
| ⚡ 이평선 정배열 | 3점 |
| 🔄 눌림목 후 재상승 | 2점 |
| 💚 RSI 건강 구간 | 2점 |
| 🔥 BB수축→확장 | 3점 |
| 📊 MACD 크로스 | 2점 |
| 📉 펀딩비 음수 | 2점 |
| ⏱ 4H MA20 위 | 2점 |
| 🔀 복합 신호 승수 | x1.15~1.3 |""")
    st.markdown("---")
    if st.button("🚪 로그아웃", use_container_width=True, key="logout_btn"):
        st.session_state["authenticated"] = False
        st.rerun()
    st.caption("⚠️ 투자 손실에 책임지지 않습니다")

# ══════════════════════════════════════════════════════════════════
# 탭 1: 급등 예고 코인 탐지
# ══════════════════════════════════════════════════════════════════
if mode == "🔍 급등 예고 코인 탐지":

    st.markdown(f"""<div class="cond-box">
      <b style="color:#e0e6f0;">현재 탐지 조건</b><br>
      📉 200일선 아래 <b style="color:#ffd700;">{min_below}일({min_below//30}개월) 이상</b> 조정 →
      📈 최근 <b style="color:#00d4aa;">{max_cross}일 이내</b> 200일선 상향 돌파 →
      📍 현재가 200일선 위 <b style="color:#f7a44f;">0~{max_gap}%</b> 이내
    </div>""", unsafe_allow_html=True)

    if st.button("🚀 스캔 시작", type="primary", use_container_width=True):
        det = CryptoSurgeDetector(max_gap, min_below, max_cross)
        total = len(det.symbols)
        prog_bar  = st.progress(0)
        prog_text = st.empty()
        results   = []
        completed = [0]

        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(det.analyze_coin, sym): sym for sym in det.symbols}
            for future in as_completed(futures):
                completed[0] += 1
                sym = futures[future]
                prog_text.markdown(f"<span style='color:#8b92a5;font-size:13px;'>({completed[0]}/{total}) {sym} 분석 중...</span>", unsafe_allow_html=True)
                prog_bar.progress(completed[0] / total)
                try:
                    r = future.result()
                    if r:
                        results.append(r)
                except:
                    pass

        prog_bar.empty()
        prog_text.empty()
        results = sorted(results, key=lambda x: x["total_score"], reverse=True)
        results = [r for r in results if r["total_score"] >= min_score]
        st.session_state["scan_results"] = results
        try:
            save_scan(results)
        except:
            pass

    if "scan_results" not in st.session_state:
        try:
            from datetime import date
            cached = load_scan(str(date.today()))
            if cached:
                st.session_state["scan_results"] = cached
                st.info(f"📦 오늘 저장된 스캔 결과 {len(cached)}개 자동 로드됨")
        except:
            pass

    results = st.session_state.get("scan_results", [])
    results = [r for r in results if r.get("total_score", 0) >= min_score and r.get("gap_pct", 99) <= max_gap]

    if "scan_results" not in st.session_state:
        pass
    elif not results:
        st.warning("현재 조건을 만족하는 코인이 없습니다.")
        st.info("💡 사이드바에서 조건을 완화해보세요.")
    else:
        st.success(f"✅ {len(results)}개 코인이 모든 핵심 조건을 충족합니다!")

        c1, c2, c3, c4 = st.columns(4)
        metric_card(c1, "발견 코인", f"{len(results)}개")
        metric_card(c2, "평균 조정 기간", f"{int(sum(r['below_days'] for r in results)/len(results))}일")
        metric_card(c3, "평균 200선 이격", f"+{sum(r['gap_pct'] for r in results)/len(results):.1f}%")
        metric_card(c4, "최고 점수", f"{max(r['total_score'] for r in results)}점")

        st.markdown("<div class='sec-title'>🏆 급등 예고 코인 전체</div>", unsafe_allow_html=True)

        rows = []
        for r in results:
            s = r["signals"]
            rows.append({
                "코인명":    r["name"],
                "심볼":      r["symbol"],
                "현재가":    _krw(r['current_price']),
                "200일선":   _krw(r['ma200']),
                "200선이격": f"+{r['gap_pct']:.1f}%",
                "조정기간":  f"{r['below_days']}일",
                "돌파후":    f"{r['days_since_cross']}일",
                "RSI":       r["rsi"],
                "펀딩비":    f"{r.get('funding_rate', 0):+.4f}%",
                "종합점수":  r["total_score"],
                "거래량":    "✅" if s.get("vol_strong_cross") else ("🔶" if s.get("vol_at_cross") else "❌"),
                "OBV":       "✅" if s.get("obv_rising") else "❌",
                "정배열":    "✅" if s.get("ma_align") else "❌",
                "BB수축":    "✅" if s.get("bb_squeeze_expand") else "❌",
                "MACD":      "✅" if s.get("macd_cross") else "❌",
                "펀딩음수":  "✅" if s.get("funding_negative") else "❌",
                "4H추세":    "✅" if s.get("4h_above_ma20") else "❌",
            })
        st.dataframe(pd.DataFrame(rows),
            column_config={
                "종합점수": st.column_config.ProgressColumn("종합점수", min_value=0, max_value=30, format="%d점"),
                "RSI": st.column_config.ProgressColumn("RSI", min_value=0, max_value=100, format="%.1f"),
            },
            use_container_width=True, hide_index=True)

        if len(results) > 1:
            fig_bar = px.bar(pd.DataFrame(results), x="name", y="total_score",
                color="total_score", color_continuous_scale="Oranges",
                labels={"name": "코인명", "total_score": "점수"}, title="종합 점수")
            fig_bar.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                font=dict(color="#8b92a5"), xaxis_tickangle=30,
                coloraxis_showscale=False, height=240, margin=dict(l=5, r=5, t=30, b=50))
            st.plotly_chart(fig_bar, config={"scrollZoom": False, "displayModeBar": False, "staticPlot": True},
                            use_container_width=True, key="chart_score_bar")

        st.markdown("<div class='sec-title'>🎯 코인별 상세 분석</div>", unsafe_allow_html=True)
        medals = ["gold", "silver", "bronze"]
        icons  = ["🥇", "🥈", "🥉"]

        for i, r in enumerate(results):
            medal = medals[i] if i < 3 else ""
            icon  = icons[i]  if i < 3 else f"{i+1}."
            pct   = min(r["total_score"] / 30 * 100, 100)
            s     = r["signals"]
            fr    = r.get("funding_rate", 0)
            fr_color = "#26a69a" if fr <= 0 else "#ef5350"

            badges = []
            if s.get("vol_strong_cross"):  badges.append("🔥 거래량 3배")
            elif s.get("vol_at_cross"):    badges.append("📈 거래량 2배")
            if s.get("ma_align"):          badges.append("✅ 정배열")
            if s.get("bb_squeeze_expand"): badges.append("💥 BB수축→확장")
            if s.get("macd_cross"):        badges.append("⚡ MACD")
            if s.get("funding_negative"):  badges.append("📉 펀딩비 음수")
            if s.get("4h_above_ma20"):     badges.append("⏱ 4H 상승")
            if s.get("pullback_recovery"): badges.append("🔄 눌림목 반등")
            badge_html = " ".join(f"<span style='background:#1e2540;padding:2px 8px;border-radius:10px;font-size:11px;'>{b}</span>" for b in badges)

            st.markdown(f"""<div class="rank-card {medal}">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <span style="font-size:20px;">{icon}</span>
                  <span style="color:#fff;font-size:clamp(14px,3vw,18px);font-weight:700;margin-left:6px;">{r["name"]}</span>
                  <span style="color:#8b92a5;font-size:13px;margin-left:8px;">{r["symbol"]}</span>
                </div>
                <div style="text-align:right;">
                  <span style="color:#fff;font-size:clamp(14px,3vw,20px);font-weight:700;">{_krw(r["current_price"])}</span>
                  <span style="color:#f7a44f;font-size:16px;margin-left:8px;">{r["total_score"]}점</span>
                </div>
              </div>
              <div style="margin-top:6px;color:#8b92a5;font-size:12px;">
                200일선 {_krw(r["ma200"])} | 이격 +{r["gap_pct"]:.1f}% |
                조정 {r["below_days"]}일 | 돌파 {r["days_since_cross"]}일 전 |
                RSI {r["rsi"]:.1f} | <span style="color:{fr_color};">펀딩비 {fr:+.4f}%</span>
              </div>
              <div style="margin-top:8px;">
                <div style="color:#8b92a5;font-size:11px;margin-bottom:3px;">종합점수 {r["total_score"]}점</div>
                <div class="bar-bg"><div class="bar-fill" style="width:{pct:.0f}%;"></div></div>
              </div>
              <div style="margin-top:8px;">{badge_html}</div>
            </div>""", unsafe_allow_html=True)

            _favs = st.session_state.get("favorites", {})
            _is_fav = r["symbol"] in _favs
            fav_col, _ = st.columns([1, 5])
            if fav_col.button("⭐ 해제" if _is_fav else "☆ 즐겨찾기", key=f"fav_{r['symbol']}_{i}", use_container_width=True):
                if _is_fav: _favs.pop(r["symbol"], None)
                else: _favs[r["symbol"]] = r["name"]
                st.session_state["favorites"] = _favs
                st.toast("⭐ 즐겨찾기에 추가됐어요!" if not _is_fav else "즐겨찾기에서 제거됐어요")

            active_sigs = []
            if s.get("vol_strong_cross"):  active_sigs.append(f"🚀 돌파 시 거래량 폭발 ({s.get('cross_vol_ratio',0):.1f}배)")
            elif s.get("vol_at_cross"):    active_sigs.append(f"📦 돌파 시 거래량 급증 ({s.get('cross_vol_ratio',0):.1f}배)")
            if s.get("recent_vol"):        active_sigs.append(f"📊 최근 거래량 증가 ({s.get('recent_vol_ratio',0):.1f}배)")
            if s.get("obv_rising"):        active_sigs.append("📈 OBV 지속 상승")
            if s.get("ma_align"):          active_sigs.append("⚡ 이평선 정배열 (MA5>MA20>MA50)")
            if s.get("pullback_recovery"): active_sigs.append("🔄 눌림목 후 재상승")
            if s.get("rsi_healthy"):       active_sigs.append(f"💚 RSI 건강 구간 ({s.get('rsi',0):.1f})")
            if s.get("bb_squeeze_expand"): active_sigs.append("🔥 볼린저밴드 수축→확장")
            if s.get("macd_cross"):        active_sigs.append("📊 MACD 골든크로스")
            if s.get("funding_negative"):  active_sigs.append(f"📉 펀딩비 음수 ({s.get('funding_rate',0):+.4f}%)")
            if s.get("4h_above_ma20"):     active_sigs.append("⏱ 4시간봉 MA20 위")

            sig_cols = st.columns(2)
            for j, sig in enumerate(active_sigs):
                sig_cols[j % 2].success(sig)
            if not active_sigs:
                st.info("추가 신호 없음 (핵심 조건만 충족)")

            cd = get_chart_data(r["symbol"], 200)
            if cd is not None and len(cd) > 20:
                try:
                    _c = make_candle(cd, f"{r['name']} ({r['symbol']})")
                    st.plotly_chart(_c, config={"scrollZoom": False, "displayModeBar": False, "staticPlot": True},
                                    use_container_width=True, key=f"candle_{r['symbol']}_{i}")
                    show_price_levels(_c)
                except Exception as e:
                    st.caption(f"차트 오류: {e}")

# ══════════════════════════════════════════════════════════════════
# 탭 2: 최적 급등 타이밍
# ══════════════════════════════════════════════════════════════════
elif mode == "🎯 최적 급등 타이밍":

    st.markdown("""
    <div style='background:linear-gradient(135deg,#0d1528,#111827);padding:20px 24px;border-radius:14px;
         margin-bottom:16px;border:1px solid rgba(247,164,79,0.2);'>
      <h3 style='color:#f0f4ff;margin:0;font-size:18px;font-weight:800;'>🎯 최적 급등 타이밍 탐지</h3>
      <p style='color:#8b92a5;margin:8px 0 0;font-size:13px;'>
        7가지 핵심 조건이 동시에 겹치는 순간 포착 |
        <b style='color:#ffd700;'>에너지 축적 → 매집 → 변동성 수축 → 돌파 직전</b>
      </p>
    </div>""", unsafe_allow_html=True)

    def calc_timing_score(symbol):
        try:
            data = fetch_ohlcv(symbol, limit=300)
            if data is None or len(data) < 60:
                return None
            close = data["Close"].dropna()
            high  = data["High"].dropna()
            low   = data["Low"].dropna()
            vol   = data["Volume"].dropna()
            n     = len(close)
            if n < 60: return None
            current = float(close.iloc[-1])
            prev    = float(close.iloc[-2])
            chg     = (current - prev) / prev * 100
            ma5  = close.rolling(5).mean()
            ma20 = close.rolling(20).mean()
            ma50 = close.rolling(50).mean()
            ma200 = close.rolling(240).mean() if n >= 240 else None
            score = 0
            signals = {}
            if ma200 is None or pd.isna(ma200.iloc[-1]): return None
            ma200_v   = float(ma200.iloc[-1])
            ma200_gap = (current - ma200_v) / ma200_v * 100
            if not (0 <= ma200_gap <= 10): return None
            days_above = sum(1 for i in range(-3, 0) if float(close.iloc[i]) > float(ma200.iloc[i]))
            if days_above < 3: return None
            signals["ma200_gap"] = round(ma200_gap, 1)
            if pd.isna(ma50.iloc[-1]): return None
            if not (float(ma5.iloc[-1]) > float(ma20.iloc[-1]) > float(ma50.iloc[-1])): return None
            signals["ma_align"] = True
            vol_ma5  = float(vol.tail(5).mean())
            vol_ma20 = float(vol.rolling(20).mean().iloc[-1])
            vol_ratio = vol_ma5 / (vol_ma20 + 1e-9)
            if vol_ratio < 1.3: return None
            signals["vol_ratio"] = round(vol_ratio, 2)
            bb_std = close.rolling(20).std()
            bb_mid = close.rolling(20).mean()
            bb_w   = (4 * bb_std) / bb_mid.replace(0, np.nan)
            bb_w_min = float(bb_w.tail(60).min())
            bb_w_now = float(bb_w.iloc[-1])
            signals["bb_squeeze"]   = bb_w_now <= bb_w_min * 1.2
            signals["bb_expanding"] = bb_w_now > float(bb_w.iloc[-5]) * 1.03
            if signals["bb_squeeze"] and signals["bb_expanding"]: score += 3
            elif signals["bb_squeeze"]: score += 1
            rsi = calc_rsi(close, 14)
            cur_rsi = float(rsi.iloc[-1])
            signals["rsi"] = round(cur_rsi, 1)
            rsi_90 = rsi.tail(90).dropna()
            signals["rsi_cycle"]   = (rsi_90 < 30).any() and ((rsi_90.shift(1) <= 30) & (rsi_90 > 30)).any() and 40 <= cur_rsi <= 65
            signals["rsi_healthy"] = 40 <= cur_rsi <= 65
            if signals["rsi_cycle"]: score += 3
            elif signals["rsi_healthy"]: score += 1
            macd   = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
            macd_s = macd.ewm(span=9, adjust=False).mean()
            macd_h = macd - macd_s
            signals["macd_cross"]    = bool(macd_h.iloc[-1] > 0 and macd_h.iloc[-2] <= 0)
            signals["macd_positive"] = bool(macd_h.iloc[-1] > 0)
            if signals["macd_cross"]: score += 2
            elif signals["macd_positive"]: score += 1
            obv = [0]
            for i in range(1, n):
                obv.append(obv[-1] + (vol.iloc[i] if close.iloc[i] > close.iloc[i-1] else -vol.iloc[i] if close.iloc[i] < close.iloc[i-1] else 0))
            obv_s = pd.Series(obv, index=close.index)
            obv_chg   = (float(obv_s.iloc[-1]) - float(obv_s.iloc[-20])) / (abs(float(obv_s.iloc[-20])) + 1e-9)
            price_chg = abs((current - float(close.iloc[-20])) / float(close.iloc[-20]))
            signals["accumulation"] = obv_chg > 0.03 and price_chg < 0.08
            signals["obv_rising"]   = obv_chg > 0
            if signals["accumulation"]: score += 2
            elif signals["obv_rising"]: score += 1
            low_120  = float(close.tail(120).min())
            high_120 = float(close.tail(120).max())
            recovery = (current - low_120) / (high_120 - low_120 + 1e-9)
            signals["recovery_zone"] = 0.10 <= recovery <= 0.50
            signals["recovery_pct"]  = round(recovery * 100, 1)
            if 0.10 <= recovery <= 0.30: score += 2
            elif 0.30 < recovery <= 0.50: score += 1
            name = COIN_NAMES.get(symbol, symbol.replace("/USDT", ""))
            return {"symbol": symbol, "name": name, "current_price": current,
                    "price_change_1d": round(chg, 2), "total_score": score,
                    "signals": signals, "rsi": cur_rsi, "df": data}
        except:
            return None

    if st.button("🚀 최적 타이밍 스캔", type="primary", use_container_width=True):
        total = len(CRYPTO_SYMBOLS)
        results = []
        completed = [0]
        prog = st.progress(0)
        prog_text = st.empty()
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(calc_timing_score, sym): sym for sym in CRYPTO_SYMBOLS}
            for future in as_completed(futures):
                completed[0] += 1
                prog_text.markdown(f"<span style='color:#8b92a5;font-size:13px;'>({completed[0]}/{total}) {futures[future]} 분석 중...</span>", unsafe_allow_html=True)
                prog.progress(completed[0] / total)
                try:
                    r = future.result()
                    if r and r["total_score"] >= 3: results.append(r)
                except: pass
        prog.empty(); prog_text.empty()
        results.sort(key=lambda x: x["total_score"], reverse=True)
        st.session_state["timing_results"] = results

    results = st.session_state.get("timing_results", [])
    if not results:
        st.info("'최적 타이밍 스캔' 버튼을 눌러주세요.")
    else:
        st.success(f"✅ {len(results)}개 코인 발견!")
        c1, c2, c3, c4 = st.columns(4)
        metric_card(c1, "발견 코인", f"{len(results)}개")
        metric_card(c2, "최고 점수", f"{results[0]['total_score']}점")
        metric_card(c3, "평균 점수", f"{sum(r['total_score'] for r in results)/len(results):.1f}점")
        metric_card(c4, "만점", "14점")
        st.markdown("<div class='sec-title'>🏆 최적 급등 타이밍 TOP 코인</div>", unsafe_allow_html=True)
        medals = ["gold", "silver", "bronze"]
        icons  = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(results[:10]):
            medal = medals[i] if i < 3 else ""
            icon  = icons[i]  if i < 3 else f"{i+1}."
            s     = r["signals"]
            pct   = min(r["total_score"] / 14 * 100, 100)
            color = "#26a69a" if r["price_change_1d"] > 0 else "#ef5350"
            arrow = "▲" if r["price_change_1d"] > 0 else "▼"
            st.markdown(f"""<div class="rank-card {medal}">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <span style="font-size:20px;">{icon}</span>
                  <span style="color:#fff;font-size:18px;font-weight:700;margin-left:6px;">{r["name"]}</span>
                  <span style="color:#8b92a5;font-size:13px;margin-left:8px;">{r["symbol"]}</span>
                </div>
                <div style="text-align:right;">
                  <span style="color:#fff;font-size:20px;font-weight:700;">{_krw(r["current_price"])}</span>
                  <span style="color:{color};font-size:14px;margin-left:8px;">{arrow} {abs(r["price_change_1d"]):.2f}%</span>
                </div>
              </div>
              <div style="margin-top:8px;color:#8b92a5;font-size:12px;">
                RSI {s.get('rsi',0):.1f} | 거래량 {s.get('vol_ratio',0):.1f}배 |
                반등위치 {s.get('recovery_pct',0):.0f}% | 200선 +{s.get('ma200_gap',0):.1f}%
              </div>
              <div style="margin-top:8px;">
                <div style="color:#8b92a5;font-size:11px;margin-bottom:3px;">종합점수 {r["total_score"]}점 / 14점</div>
                <div class="bar-bg"><div class="bar-fill" style="width:{pct:.0f}%;"></div></div>
              </div>
            </div>""", unsafe_allow_html=True)
            with st.expander(f"📊 {r['name']} 상세 + 차트", expanded=(i == 0)):
                active, inactive = [], []
                checks = [
                    (s.get("recovery_zone"),   f"🏔 최적 반등 구간 ({s.get('recovery_pct',0):.0f}%)"),
                    (s.get("accumulation"),    "📦 매집 신호 (OBV↑ + 가격횡보)"),
                    (s.get("obv_rising"),      "📈 OBV 상승 중"),
                    (s.get("bb_squeeze"),      "🔥 볼린저밴드 수축"),
                    (s.get("bb_expanding"),    "💥 BB 확장 시작"),
                    (s.get("rsi_cycle"),       f"💚 RSI 바닥 사이클 완성 ({s.get('rsi',0):.1f})"),
                    (s.get("ma_align"),        "⚡ 이평선 완전 정배열"),
                    (s.get("macd_cross"),      "📊 MACD 골든크로스"),
                    (s.get("macd_positive"),   "📊 MACD 양전환"),
                ]
                for flag, label in checks:
                    (active if flag else inactive).append(label)
                ca, cb = st.columns(2)
                with ca:
                    st.write("**✅ 충족 신호**")
                    for sig in active: st.success(sig)
                with cb:
                    st.write("**❌ 미충족**")
                    for sig in inactive[:5]: st.error(sig)
                _c = make_candle(r["df"], f"{r['name']} ({r['symbol']})", show_levels=True)
                st.plotly_chart(_c, config={"scrollZoom": False, "displayModeBar": False, "staticPlot": True},
                                use_container_width=True, key=f"candle_timing_{r['symbol']}")
                show_price_levels(_c)

# ══════════════════════════════════════════════════════════════════
# 탭 3: 개별 코인 분석
# ══════════════════════════════════════════════════════════════════
elif mode == "📈 개별 코인 분석":
    st.markdown("<div class='sec-title'>📈 개별 코인 분석</div>", unsafe_allow_html=True)

    search_q = st.text_input("🔍 코인명 검색", placeholder="예: 비트코인, 솔라나, 이더리움...")
    symbol = None
    name   = None

    if search_q.strip():
        q = search_q.strip().lower()
        matches = [(sym, nm) for sym, nm in COIN_NAMES.items() if q in nm.lower() or q in sym.lower()]
        if matches:
            opts = [f"{nm} ({sym})" for sym, nm in matches]
            sel  = st.selectbox("검색 결과", opts, key="search_result")
            symbol = sel.split("(")[1].replace(")", "").strip()
            name   = sel.split("(")[0].strip()
        else:
            st.warning(f"'{search_q}' 검색 결과 없음")
    else:
        all_opts = [f"{nm} ({sym})" for sym, nm in COIN_NAMES.items()]
        sel = st.selectbox("코인 선택", all_opts)
        symbol = sel.split("(")[1].replace(")", "").strip()
        name   = sel.split("(")[0].strip()

    if symbol and st.button("분석", type="primary"):
        with st.spinner(f"{name} 분석 중..."):
            det    = CryptoSurgeDetector(max_gap, min_below, max_cross)
            result = det.analyze_coin(symbol)
            data   = get_chart_data(symbol, 200)
        st.session_state["indiv_result"] = result
        st.session_state["indiv_data"]   = data
        st.session_state["indiv_symbol"] = symbol
        st.session_state["indiv_name"]   = name

    result = st.session_state.get("indiv_result") if st.session_state.get("indiv_symbol") == symbol else None
    data   = st.session_state.get("indiv_data")   if st.session_state.get("indiv_symbol") == symbol else None

    if data is not None:
        current = float(data["Close"].iloc[-1])
        prev    = float(data["Close"].iloc[-2])
        chg     = (current - prev) / prev * 100
        color   = "#26a69a" if chg > 0 else "#ef5350"
        arrow   = "▲" if chg > 0 else "▼"

        if result:
            pct = min(result["total_score"] / 30 * 100, 100)
            st.markdown(f"""<div class="rank-card gold" style="margin-bottom:16px;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <span style="color:#fff;font-size:24px;font-weight:700;">✅ {name}</span>
                  <span style="color:#26a69a;font-size:13px;margin-left:10px;">핵심 조건 충족</span>
                </div>
                <div style="text-align:right;">
                  <span style="color:#fff;font-size:24px;font-weight:700;">{_krw(current)}</span>
                  <span style="color:{color};font-size:15px;margin-left:8px;">{arrow} {abs(chg):.2f}%</span>
                </div>
              </div>
              <div style="margin-top:10px;">
                <div style="color:#8b92a5;font-size:12px;margin-bottom:3px;">종합점수 {result["total_score"]}점</div>
                <div class="bar-bg"><div class="bar-fill" style="width:{pct:.0f}%;"></div></div>
              </div>
            </div>""", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            metric_card(c1, "RSI(14)", f"{result['rsi']:.1f}")
            metric_card(c2, "200선 이격", f"+{result['gap_pct']:.1f}%")
            metric_card(c3, "조정 기간", f"{result['below_days']}일")
            metric_card(c4, "돌파 후", f"{result['days_since_cross']}일")
            st.markdown("<div class='sec-title'>📊 신호 분석</div>", unsafe_allow_html=True)
            s = result["signals"]
            active, inactive = [], []
            checks = [
                (s.get("vol_at_cross"),      f"📦 돌파 시 거래량 급증 ({s.get('cross_vol_ratio',0):.1f}배)"),
                (s.get("recent_vol"),         f"📊 최근 거래량 증가 ({s.get('recent_vol_ratio',0):.1f}배)"),
                (s.get("obv_rising"),         "📈 OBV 지속 상승"),
                (s.get("ma_align"),           "⚡ 이평선 정배열 (MA5>MA20>MA50)"),
                (s.get("pullback_recovery"),  "🔄 눌림목 후 재상승"),
                (s.get("rsi_healthy"),        f"💚 RSI 건강 구간 ({s.get('rsi',0):.1f})"),
                (s.get("bb_squeeze_expand"),  "🔥 볼린저밴드 수축→확장"),
                (s.get("macd_cross"),         "📊 MACD 골든크로스"),
                (s.get("funding_negative"),   f"📉 펀딩비 음수 ({s.get('funding_rate',0):+.4f}%)"),
                (s.get("4h_above_ma20"),      "⏱ 4시간봉 MA20 위"),
            ]
            for flag, label in checks:
                (active if flag else inactive).append(label)
            ca, cb = st.columns(2)
            with ca:
                st.write("**✅ 충족 신호**")
                for sig in active: st.success(sig)
                if not active: st.info("추가 신호 없음")
            with cb:
                st.write("**❌ 미충족 신호**")
                for sig in inactive: st.error(sig)
        else:
            st.markdown(f"""<div class="rank-card" style="margin-bottom:16px;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <span style="color:#fff;font-size:24px;font-weight:700;">⚠️ {name}</span>
                  <span style="color:#ef5350;font-size:13px;margin-left:10px;">핵심 조건 미충족</span>
                </div>
                <div style="text-align:right;">
                  <span style="color:#fff;font-size:24px;font-weight:700;">{_krw(current)}</span>
                  <span style="color:{color};font-size:15px;margin-left:8px;">{arrow} {abs(chg):.2f}%</span>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)
            close_clean = data["Close"].dropna()
            if len(close_clean) >= 240:
                ma200_now = float(close_clean.rolling(240).mean().dropna().iloc[-1])
                gap = (current - ma200_now) / ma200_now * 100
                c1, c2 = st.columns(2)
                metric_card(c1, "현재 200선 이격", f"{gap:+.1f}%")
                metric_card(c2, "200일선", f"{_krw(ma200_now)}")
                if gap < 0:
                    st.warning(f"📉 현재가가 200일선 아래 ({gap:.1f}%) — 아직 조정 중")
                elif gap > max_gap:
                    st.warning(f"📈 200일선 위 {gap:.1f}% — 근처 범위({max_gap}%) 초과")
                else:
                    st.warning("📊 200일선 돌파 이력 또는 조정 기간 조건 미충족")

        _c = make_candle(data, f"{name} ({symbol})")
        st.plotly_chart(_c, config={"scrollZoom": False, "displayModeBar": False, "staticPlot": True},
                        use_container_width=True, key="chart_indiv")
        show_price_levels(_c)

        _favs = st.session_state.get("favorites", {})
        _is_fav = symbol in _favs
        if st.button("⭐ 즐겨찾기 해제" if _is_fav else "☆ 즐겨찾기 추가", key=f"fav_indiv_{symbol}"):
            if _is_fav: _favs.pop(symbol, None)
            else: _favs[symbol] = name
            st.session_state["favorites"] = _favs
            st.toast("⭐ 추가됐어요!" if not _is_fav else "즐겨찾기에서 제거됐어요")

# ══════════════════════════════════════════════════════════════════
# 탭 4: 즐겨찾기
# ══════════════════════════════════════════════════════════════════
elif mode == "⭐ 즐겨찾기":
    st.markdown("<div class='sec-title'>⭐ 즐겨찾기 코인</div>", unsafe_allow_html=True)
    favs_dict = st.session_state.get("favorites", {})
    if not favs_dict:
        st.info("즐겨찾기한 코인이 없습니다. 급등 탐지 탭에서 ☆ 버튼을 눌러 추가하세요.")
    else:
        st.success(f"총 {len(favs_dict)}개 코인")
        for sym, nm in list(favs_dict.items()):
            col1, col2 = st.columns([4, 1])
            with col1:
                df_f = get_chart_data(sym, 5)
                if df_f is not None and len(df_f) > 1:
                    cur_f  = float(df_f["Close"].iloc[-1])
                    prev_f = float(df_f["Close"].iloc[-2])
                    chg_f  = (cur_f - prev_f) / prev_f * 100
                    color_f = "#26a69a" if chg_f > 0 else "#ef5350"
                    st.markdown(f"""<div style='background:#1a1f35;border-radius:10px;padding:14px 16px;border:1px solid #2d3555;'>
                      <span style='color:#fff;font-weight:700;font-size:16px;'>{nm}</span>
                      <span style='color:#8b92a5;font-size:12px;margin-left:8px;'>{sym}</span><br>
                      <span style='color:#fff;font-size:18px;font-weight:700;'>{_krw(cur_f)}</span>
                      <span style='color:{color_f};font-size:13px;margin-left:8px;'>{"▲" if chg_f>0 else "▼"} {abs(chg_f):.2f}%</span>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"**{nm}** ({sym})")
            with col2:
                if st.button("🗑 삭제", key=f"del_fav_{sym}"):
                    favs_dict.pop(sym, None)
                    st.session_state["favorites"] = favs_dict
                    st.rerun()
            st.markdown("")
        if st.button("📊 즐겨찾기 전체 차트 보기", type="primary"):
            for sym, nm in favs_dict.items():
                cd = get_chart_data(sym, 200)
                if cd is not None:
                    fig_f = make_candle(cd, f"{nm} ({sym})")
                    st.plotly_chart(fig_f, config={"scrollZoom": False, "displayModeBar": False, "staticPlot": True},
                                    use_container_width=True, key=f"fav_chart_{sym}")
                    show_price_levels(fig_f)

# ══════════════════════════════════════════════════════════════════
# 탭 5: 히스토리
# ══════════════════════════════════════════════════════════════════
elif mode == "📊 히스토리":
    st.markdown("<div class='sec-title'>📅 과거 스캔 결과 히스토리</div>", unsafe_allow_html=True)
    try:
        scan_dates = list_scan_dates()
        if not scan_dates:
            st.info("저장된 스캔 결과가 없습니다. 급등 탐지 탭에서 스캔을 실행하면 자동 저장됩니다.")
        else:
            date_opts = [d["date"] for d in scan_dates]
            sel_date  = st.selectbox("날짜 선택", date_opts)
            cached    = load_scan(sel_date)
            if cached:
                st.success(f"{sel_date} — {len(cached)}개 코인")
                hist_df = pd.DataFrame([{
                    "코인명":    r.get("name", ""),
                    "심볼":      r.get("symbol", ""),
                    "현재가":    _krw(r.get('current_price', 0)),
                    "200선이격": f"+{r.get('gap_pct', 0):.1f}%",
                    "조정기간":  f"{r.get('below_days', 0)}일",
                    "돌파후":    f"{r.get('days_since_cross', 0)}일",
                    "RSI":       r.get("rsi", 0),
                    "종합점수":  r.get("total_score", 0),
                } for r in cached])
                st.dataframe(hist_df,
                    column_config={
                        "종합점수": st.column_config.ProgressColumn("종합점수", min_value=0, max_value=30, format="%d점"),
                        "RSI": st.column_config.ProgressColumn("RSI", min_value=0, max_value=100, format="%.1f"),
                    },
                    use_container_width=True, hide_index=True)
                if len(cached) > 1:
                    fig_h = px.bar(pd.DataFrame(cached), x="name", y="total_score",
                        color="total_score", color_continuous_scale="Oranges",
                        labels={"name": "코인명", "total_score": "점수"},
                        title=f"{sel_date} 스캔 결과")
                    fig_h.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                        font=dict(color="#8b92a5"), xaxis_tickangle=30,
                        coloraxis_showscale=False, height=280, margin=dict(l=5, r=5, t=40, b=50))
                    st.plotly_chart(fig_h, config={"scrollZoom": False, "displayModeBar": False, "staticPlot": True},
                                    use_container_width=True)
    except Exception as e:
        st.error(f"히스토리 로드 오류: {e}")

# ══════════════════════════════════════════════════════════════════
# 탭 6: 성과 추적
# ══════════════════════════════════════════════════════════════════
elif mode == "📈 성과 추적":
    st.markdown("<div class='sec-title'>📈 알림 코인 성과 추적</div>", unsafe_allow_html=True)
    col_refresh, _ = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 상태 업데이트", type="primary", use_container_width=True):
            with st.spinner("현재가 확인 중..."):
                update_alert_status()
            st.success("업데이트 완료!")
            st.rerun()
    try:
        summary = get_performance_summary()
        if not summary:
            st.info("아직 성과 데이터가 없습니다.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            metric_card(c1, "총 알림 종목", f"{summary.get('total', 0)}개")
            metric_card(c2, "승률", f"{summary.get('win_rate', 0):.1f}%")
            metric_card(c3, "평균 수익률", f"{summary.get('avg_return', 0):+.2f}%")
            win_rate = summary.get("win_rate", 0)
            grade = "🔥 강력" if win_rate >= 60 else "✅ 양호" if win_rate >= 50 else "⚠️ 보통"
            metric_card(c4, "전략 등급", grade)
            avg_ret = summary.get("avg_return", 0)
            ret_color = "#26a69a" if avg_ret >= 0 else "#ef5350"
            st.markdown(f"""
            <div style='background:#1a1f35;border-radius:12px;padding:20px;border:1px solid {ret_color};margin-top:12px;text-align:center;'>
              <div style='color:#8b92a5;font-size:13px;'>텔레그램 알림 발송 코인 기준 | 7일 후 평균 수익률</div>
              <div style='color:{ret_color};font-size:48px;font-weight:800;margin:12px 0;'>{avg_ret:+.2f}%</div>
            </div>""", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"성과 데이터 로드 오류: {e}")
    st.markdown("<div class='sec-title'>📋 알림 이력</div>", unsafe_allow_html=True)
    try:
        import sqlite3
        from cache_db import DB_PATH
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        rows = conn.execute(
            "SELECT alert_date,symbol,name,score,entry_price,target_price,stop_price,rr_ratio,status,exit_price,return_pct FROM alert_history ORDER BY alert_date DESC LIMIT 100"
        ).fetchall()
        conn.close()
        if rows:
            status_map = {"active": "🟡 보유중", "hit_target": "✅ 목표달성", "hit_stop": "❌ 손절", "expired": "⏰ 만료"}
            df_hist = pd.DataFrame([{
                "날짜": r[0], "코인": r[2], "심볼": r[1], "점수": r[3],
                "매수가": _krw(r[4]) if r[4] else "-",
                "목표가": _krw(r[5]) if r[5] else "-",
                "손절가": _krw(r[6]) if r[6] else "-",
                "손익비": f"{r[7]:.1f}:1" if r[7] else "-",
                "상태": status_map.get(r[8], r[8]),
                "청산가": _krw(r[9]) if r[9] else "-",
                "수익률": f"{r[10]:+.2f}%" if r[10] is not None else "-",
            } for r in rows])
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
        else:
            st.info("알림 이력이 없습니다.")
    except Exception as e:
        st.info(f"알림 이력 조회 오류: {e}")
