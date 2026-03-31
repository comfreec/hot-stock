import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from datetime import datetime

try:
    from stock_surge_detector import KoreanStockSurgeDetector
except Exception as e:
    st.error(f"Import error: {e}")
    st.stop()

try:
    from cache_db import (save_scan, load_scan, list_scan_dates,
                          add_favorite, remove_favorite, get_favorites,
                          is_favorite, start_scheduler)
    from backtest_ml import backtest_signal, SIGNAL_WEIGHTS
    from streamlit_javascript import st_javascript
    # ?��?줄러 ?�작 (??최초 로드 ??1??
    if "scheduler_started" not in st.session_state:
        start_scheduler()
        st.session_state["scheduler_started"] = True
except Exception as e:
    st.warning(f"캐시/백테?�트 모듈 로드 ?�패: {e}")

# ?�?� ?�근 ?�어 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
PASSWORDS = ["hotstock2026", "vip1234", "comfreec"]  # ?��???비�?번호 목록

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.markdown("""
    <style>
    @keyframes fadein { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }
    @keyframes rocket_up {
        0%   { transform: translateY(0px) rotate(-45deg); opacity:1; }
        70%  { transform: translateY(-120px) rotate(-45deg); opacity:1; }
        71%  { transform: translateY(-120px) rotate(-45deg); opacity:0; }
        72%  { transform: translateY(20px) rotate(-45deg); opacity:0; }
        100% { transform: translateY(0px) rotate(-45deg); opacity:1; }
    }
    .login-box { animation: fadein 0.6s ease; }
    .rocket-icon { display:inline-block; animation: rocket_up 2.5s ease-in-out infinite; font-size:52px; }
    </style>
    <div class='login-box' style='max-width:420px;margin:80px auto;'>
      <div style='background:linear-gradient(135deg,#1a1f35,#0e1117);
           padding:48px 40px;border-radius:20px;border:1px solid #2d3555;
           box-shadow:0 20px 60px rgba(0,0,0,0.5);text-align:center;'>
        <div class='rocket-icon'>??</div>
        <h2 style='color:#fff;margin:16px 0 6px;font-size:26px;font-weight:800;letter-spacing:-0.5px;'>주식 급등 ?�측</h2>
        <p style='color:#4f8ef7;font-size:13px;margin:0 0 32px;font-weight:500;letter-spacing:2px;'>STOCK SURGE PREDICTOR</p>
        <div style='width:40px;height:2px;background:linear-gradient(90deg,#4f8ef7,#00d4aa);margin:0 auto 32px;border-radius:2px;'></div>
        <p style='color:#8b92a5;font-size:13px;margin:0 0 24px;'>?��????�용?�만 ?�근 가?�합?�다</p>
      </div>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        pw = st.text_input("", type="password", placeholder="?��  비�?번호 ?�력", label_visibility="collapsed")
        if st.button("로그??, type="primary", width='stretch'):
            if pw in PASSWORDS:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("비�?번호가 ?�바르�? ?�습?�다")
    st.stop()

STOCK_NAMES = {
    "005930.KS":"?�성?�자","000660.KS":"SK?�이?�스","035420.KS":"NAVER",
    "051910.KS":"LG?�학","006400.KS":"?�성SDI","035720.KS":"카카??,
    "207940.KS":"?�성바이??,"068270.KS":"?�?�리??,"323410.KS":"카카?�뱅??,
    "373220.KS":"LG?�너지?�루??,"005380.KS":"?��?�?,"000270.KS":"기아",
    "105560.KS":"KB금융","055550.KS":"?�한지�?,"012330.KS":"?��?모비??,
    "028260.KS":"?�성물산","066570.KS":"LG?�자","003550.KS":"LG",
    "017670.KS":"SK?�레�?,"030200.KS":"KT","196170.KQ":"?�테?�젠",
    "263750.KQ":"?�어비스","293490.KQ":"카카?�게?�즈","112040.KQ":"?�메?�드",
    "357780.KQ":"?�브?�인","086900.KQ":"메디?�스","214150.KQ":"?�래?�스",
    "950140.KQ":"?��??�드??,"145020.KQ":"?�젤","041510.KQ":"?�스??,
    "247540.KQ":"?�코?�로비엠",
    "000100.KS":"?�한?�행",
    "001040.KS":"CJ",
    "002380.KS":"KCC",
    "003490.KS":"?�?�항�?,
    "004020.KS":"?��??�철",
    "005490.KS":"POSCO?�?�스",
    "007070.KS":"GS리테??,
    "010130.KS":"고려?�연",
    "010950.KS":"S-Oil",
    "011070.KS":"LG?�노??,
    "011200.KS":"HMM",
    "016360.KS":"?�성증권",
    "018260.KS":"?�성?�스?�에??,
    "021240.KS":"코웨??,
    "023530.KS":"�?��?�핑",
    "024110.KS":"기업?�??,
    "029780.KS":"?�성카드",
    "032640.KS":"LG?�플?�스",
    "033780.KS":"KT&G",
    "034020.KS":"?�산?�너빌리??,
    "034220.KS":"LG?�스?�레??,
    "036460.KS":"?�국가?�공??,
    "036570.KS":"?�씨?�프??,
    "042660.KS":"?�화?�션",
    "047050.KS":"?�스코인?�내?�널",
    "051600.KS":"?�전KPS",
    "060980.KS":"?�세?�업",
    "064350.KS":"?��?로템",
    "071050.KS":"?�국금융지�?,
    "078930.KS":"GS",
    "086280.KS":"?��?글로비??,
    "090430.KS":"?�모?�퍼?�픽",
    "096770.KS":"SK?�노베이??,
    "097950.KS":"CJ?�일?�당",
    "100840.KS":"SNT모티�?,
    "161390.KS":"?�국?�?�어?�테?��?로�?",
    "175330.KS":"JB금융지�?,
    "180640.KS":"?�진�?,
    "192400.KS":"쿠쿠?�?�스",
    "204320.KS":"HL만도",
    "267250.KS":"HD?��?",
    "316140.KS":"?�리금융지�?,
    "326030.KS":"SK바이?�팜",
    "329180.KS":"HD?��?중공??,
    "336260.KS":"?�산밥캣",
    "035900.KQ":"JYP?�터",
    "036030.KQ":"YG?�터?�인먼트",
    "039030.KQ":"?�오?�크?�스",
    "041960.KQ":"블루�?,
    "045390.KQ":"?�?�티?�이",
    "048260.KQ":"?�스?�임?��???,
    "053800.KQ":"?�랩",
    "058470.KQ":"리노공업",
    "060310.KQ":"3S",
    "064760.KQ":"?�씨케??,
    "066970.KQ":"?�앤?�프",
    "067160.KQ":"?�프리카TV",
    "068760.KQ":"?�?�리?�제??,
    "078600.KQ":"?�주전?�재�?,
    "086520.KQ":"?�코?�로",
    "091580.KQ":"?�아?�론?�크",
    "095340.KQ":"ISC",
    "096530.KQ":"?�젠",
    "101490.KQ":"?�스?�에?�텍",
    "108320.KQ":"LX?��?�?,
    "122870.KQ":"?�?��?-??,
    "131970.KQ":"?�산?�스??,
    "137310.KQ":"?�스?�바?�오?�서",
    "141080.KQ":"?�고켐바?�오",
    "155900.KQ":"바텍",
    "166090.KQ":"?�나머티리얼�?,
    "183300.KQ":"코�?�?,
    "200130.KQ":"콜마비앤?�이�?,
    "206650.KQ":"?�바?�오로직??,
    "214370.KQ":"케?�젠",
    "236200.KQ":"?�프리마",
    "237690.KQ":"?�스?�팜",
    "251270.KQ":"?�마�?,
    "253450.KQ":"?�튜?�오?�래�?,
    "256840.KQ":"?�국비엔??,
    "270210.KQ":"?�스?�바?�오??,
    "277810.KQ":"?�인보우로보?�스",
    "290650.KQ":"?�씨?�프??,
    "298380.KQ":"?�이비엘바이??,
    "302440.KQ":"SK바이?�사?�언??,
}

st.set_page_config(page_title="?�국 주식 급등 ?�측", page_icon="??", layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
/* ?�?� 뷰포??& 기본 ?�?� */
@viewport { width: device-width; }

.main .block-container {
    padding: 0.5rem 0.8rem !important;
    max-width: 100% !important;
}
section[data-testid="stSidebar"] {
    min-width: 240px !important;
    max-width: 260px !important;
    background: linear-gradient(180deg, #0d1117 0%, #0e1117 100%) !important;
    border-right: 1px solid #1e2540 !important;
}
section[data-testid="stSidebar"] .block-container {
    padding: 1rem 0.8rem !important;
}

/* ?�?� 배경 ?�?� */
.stApp { background: #080c14 !important; }
.main { background: #080c14 !important; }

/* ?�?� ?�더 ?�?� */
.top-header {
    background: linear-gradient(135deg, #0d1528 0%, #111827 50%, #0d1528 100%);
    padding: 28px 36px;
    border-radius: 20px;
    margin-bottom: 20px;
    border: 1px solid rgba(79,142,247,0.25);
    box-shadow: 0 0 40px rgba(79,142,247,0.08), inset 0 1px 0 rgba(255,255,255,0.05);
    position: relative;
    overflow: hidden;
}
.top-header::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at 30% 50%, rgba(79,142,247,0.06) 0%, transparent 60%);
    pointer-events: none;
}

/* ?�?� 메트�?카드 ?�?� */
.metric-card {
    background: linear-gradient(135deg, #111827 0%, #1a2035 100%);
    border: 1px solid rgba(61,68,102,0.6);
    border-radius: 14px;
    padding: 18px 14px;
    text-align: center;
    margin: 4px;
    transition: all 0.25s ease;
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    position: relative;
    overflow: hidden;
}
.metric-card::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(79,142,247,0.4), transparent);
}
.metric-card .lbl { color: #6b7280; font-size: 11px; font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase; }
.metric-card .val { color: #f0f4ff; font-size: 24px; font-weight: 800; margin-top: 4px; letter-spacing: -0.5px; }

/* ?�?� 종목 카드 ?�?� */
.rank-card {
    background: linear-gradient(135deg, #0f1623 0%, #131d2e 100%);
    border-left: 3px solid #4f8ef7;
    border-top: 1px solid rgba(255,255,255,0.05);
    border-right: 1px solid rgba(255,255,255,0.03);
    border-bottom: 1px solid rgba(255,255,255,0.03);
    border-radius: 14px;
    padding: 18px 20px;
    margin: 10px 0;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 0 0 rgba(79,142,247,0);
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}
.rank-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: linear-gradient(135deg, rgba(79,142,247,0.03) 0%, transparent 60%);
    pointer-events: none;
}
.rank-card.gold {
    border-left-color: #ffd700;
    background: linear-gradient(135deg, #141208 0%, #1a1a0f 100%);
    box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 20px rgba(255,215,0,0.06);
}
.rank-card.gold::before {
    background: linear-gradient(135deg, rgba(255,215,0,0.04) 0%, transparent 60%);
}
.rank-card.silver {
    border-left-color: #c0c0c0;
    background: linear-gradient(135deg, #111318 0%, #181b22 100%);
}
.rank-card.bronze {
    border-left-color: #cd7f32;
    background: linear-gradient(135deg, #130f0a 0%, #1a1510 100%);
}

/* ?�?� 진행 �??�?� */
.bar-bg {
    background: rgba(30,33,48,0.8);
    border-radius: 10px;
    height: 6px;
    width: 100%;
    overflow: hidden;
}
.bar-fill {
    background: linear-gradient(90deg, #4f8ef7 0%, #00d4aa 100%);
    border-radius: 10px;
    height: 6px;
    box-shadow: 0 0 8px rgba(79,142,247,0.5);
    transition: width 0.6s ease;
}

/* ?�?� ?�션 ?�?��? ?�?� */
.sec-title {
    font-size: clamp(15px,3vw,19px);
    font-weight: 700;
    color: #e8edf8;
    margin: 24px 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(45,53,85,0.8);
    letter-spacing: -0.3px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* ?�?� 조건 박스 ?�?� */
.cond-box {
    background: linear-gradient(135deg, #0d1528, #111827);
    border: 1px solid rgba(45,53,85,0.7);
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 14px;
    font-size: 13px;
    color: #8b92a5;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}

/* ?�?� 버튼 ?�?� */
.stButton > button {
    background: linear-gradient(135deg, #1e3a5f 0%, #1a3050 100%) !important;
    border: 1px solid rgba(79,142,247,0.3) !important;
    color: #7eb8f7 !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #254a7a 0%, #1e3d66 100%) !important;
    border-color: rgba(79,142,247,0.6) !important;
    box-shadow: 0 4px 16px rgba(79,142,247,0.2) !important;
    transform: translateY(-1px) !important;
}
button[kind="primary"] {
    background: linear-gradient(135deg, #1a56db 0%, #1e40af 100%) !important;
    border: 1px solid rgba(79,142,247,0.5) !important;
    color: #fff !important;
    box-shadow: 0 4px 16px rgba(26,86,219,0.3) !important;
}
button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1d63f5 0%, #2348c4 100%) !important;
    box-shadow: 0 6px 24px rgba(26,86,219,0.45) !important;
    transform: translateY(-1px) !important;
}

/* ?�?� ?�라?�더 ?�?� */
.stSlider > div > div > div > div {
    background: linear-gradient(90deg, #4f8ef7, #00d4aa) !important;
}

/* ?�?� ?�이?�프?�임 ?�?� */
.stDataFrame {
    border-radius: 12px !important;
    overflow: hidden !important;
    border: 1px solid rgba(45,53,85,0.5) !important;
}
.stDataFrame thead tr th {
    background: #111827 !important;
    color: #8b92a5 !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: 0.5px !important;
    text-transform: uppercase !important;
    border-bottom: 1px solid #1e2540 !important;
}
.stDataFrame tbody tr:nth-child(even) { background: rgba(17,24,39,0.5) !important; }
.stDataFrame tbody tr:hover { background: rgba(79,142,247,0.06) !important; }

/* ?�?� ?�공/?�러/?�포 박스 ?�?� */
.stSuccess { background: rgba(0,212,170,0.08) !important; border: 1px solid rgba(0,212,170,0.25) !important; border-radius: 10px !important; }
.stWarning { background: rgba(255,193,7,0.08) !important; border: 1px solid rgba(255,193,7,0.25) !important; border-radius: 10px !important; }
.stInfo    { background: rgba(79,142,247,0.08) !important; border: 1px solid rgba(79,142,247,0.25) !important; border-radius: 10px !important; }
.stError   { background: rgba(255,51,85,0.08)  !important; border: 1px solid rgba(255,51,85,0.25)  !important; border-radius: 10px !important; }

/* ?�?� 차트 ?�치 ?�?� */
.js-plotly-plot, .plotly, .plot-container { touch-action: pan-y !important; }
.stPlotlyChart { touch-action: pan-y !important; }

/* ?�?� ?�장 ?�황 카드 ?�?� */
.market-card {
    background: linear-gradient(135deg, #111827 0%, #1a2035 100%);
    border: 1px solid rgba(45,53,85,0.6);
    border-radius: 14px;
    padding: 12px 16px;
    text-align: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    position: relative;
    overflow: hidden;
}
.market-card::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent);
}

/* ?�?� ?�크롤바 ?�?� */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #2d3555; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #4f8ef7; }

/* ?�?� 모바???�?� */
@media (max-width: 768px) {
    .main .block-container { padding: 0.3rem 0.3rem !important; }
    h1 { font-size: 18px !important; }
    .metric-card { padding: 10px 6px !important; margin: 2px !important; }
    .metric-card .val { font-size: 16px !important; }
    .rank-card { padding: 10px 12px !important; }
    .stButton > button { font-size: 12px !important; padding: 6px 4px !important; }
    .stDataFrame { overflow-x: auto !important; }
    .stDataFrame table { min-width: 600px !important; }
    .top-header { padding: 16px 18px !important; }
}

/* ?�?� ?�블�??�?� */
@media (max-width: 1024px) and (min-width: 769px) {
    .metric-card .val { font-size: 18px !important; }
    .main .block-container { padding: 0.4rem 0.6rem !important; }
}
</style>""", unsafe_allow_html=True)



st.markdown("""<div class="top-header">
  <div style="display:flex;align-items:center;gap:12px;">
    <span style="font-size:36px;">??</span>
    <div>
      <h1 style="color:#f0f4ff;margin:0;font-size:clamp(18px,4vw,28px);font-weight:800;letter-spacing:-0.5px;">?�국 주식 급등 ?�측 ?�스??/h1>
      <p style="color:#4f8ef7;margin:4px 0 0;font-size:12px;font-weight:600;letter-spacing:2px;text-transform:uppercase;">Stock Surge Predictor v3.0</p>
    </div>
  </div>
  <p style="color:#6b7280;margin:12px 0 0;font-size:13px;line-height:1.6;">
    240?�선 ?�래 충분??조정 ??최근 ?�파 ???�재 근처 ??급등 ?�호 복합 ?�인
  </p>
</div>""", unsafe_allow_html=True)

# ?�?� ?�단 ?�장 ?�황 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
@st.cache_data(ttl=300)
def get_market_index():
    try:
        kospi = yf.Ticker("^KS11").history(period="5d").dropna(subset=["Close"])
        kosdaq = yf.Ticker("^KQ11").history(period="5d").dropna(subset=["Close"])
        results = {}
        for name, df in [("KOSPI", kospi), ("KOSDAQ", kosdaq)]:
            if len(df) >= 2:
                cur = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2])
                chg = (cur - prev) / prev * 100
                results[name] = (cur, chg)
        return results
    except:
        return {}

@st.cache_data(ttl=3600)
def get_fear_greed():
    """공포/?�욕 지??- KOSPI 20??변?�성 기반 ?�체 계산"""
    try:
        df = yf.Ticker("^KS11").history(period="3mo")
        close = df["Close"]
        ret = close.pct_change().dropna()
        vol = float(ret.tail(20).std() * 100)
        rsi_val = float(calc_rsi_wilder(close, 14).iloc[-1])
        ma20 = float(close.rolling(20).mean().iloc[-1])
        cur = float(close.iloc[-1])
        momentum = (cur - ma20) / ma20 * 100
        # ?�수 계산 (0~100)
        score = 50
        score -= (vol - 1.0) * 10   # 변?�성 ?�으�?공포
        score += momentum * 2        # 모멘?� 좋으�??�욕
        score += (rsi_val - 50) * 0.5
        score = max(0, min(100, score))
        if score >= 75:   label, color = "극도???�욕", "#ff3355"
        elif score >= 55: label, color = "?�욕", "#ff8c42"
        elif score >= 45: label, color = "중립", "#ffd700"
        elif score >= 25: label, color = "공포", "#4f8ef7"
        else:             label, color = "극도??공포", "#00d4aa"
        return int(score), label, color
    except:
        return None, None, None

@st.cache_data(ttl=300)
def get_sparkline(symbol):
    """최근 20???�파?�라???�이??""
    try:
        df = yf.Ticker(symbol).history(period="1mo")
        return df["Close"].tail(20).tolist()
    except:
        return []

def make_sparkline(prices, color):
    """미니 ?�파?�라??SVG"""
    if len(prices) < 2:
        return ""
    mn, mx = min(prices), max(prices)
    rng = mx - mn or 1
    w, h = 80, 30
    pts = []
    for i, p in enumerate(prices):
        x = i / (len(prices)-1) * w
        y = h - (p - mn) / rng * h
        pts.append(f"{x:.1f},{y:.1f}")
    pts_str = " ".join(pts)
    return f'<svg width="{w}" height="{h}" style="display:inline-block;vertical-align:middle;"><polyline points="{pts_str}" fill="none" stroke="{color}" stroke-width="1.5"/></svg>'

@st.cache_data(ttl=60)
def get_realtime_price(symbol):
    """?�이�?금융?�서 ?�시�?1~2�?지?? ?�재가 가?�오�?""
    try:
        code = symbol.replace(".KS","").replace(".KQ","")
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=3)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.text, "html.parser")
        price_tag = soup.select_one(".no_today .blind")
        if price_tag:
            return int(price_tag.get_text().replace(",",""))
    except:
        pass
    return None

@st.cache_data(ttl=600)
def get_news_headline(symbol):
    """종목 최신 ?�스 1�?""
    try:
        code = symbol.replace(".KS","").replace(".KQ","")
        url = f"https://finance.naver.com/item/news_news.naver?code={code}&page=1"
        res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=3)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.text, "html.parser")
        titles = [a.get_text().strip() for a in soup.select(".title") if a.get_text().strip()]
        return titles[0] if titles else ""
    except:
        return ""


    """종목 최신 ?�스 1�?""
    try:
        code = symbol.replace(".KS","").replace(".KQ","")
        url = f"https://finance.naver.com/item/news_news.naver?code={code}&page=1"
        res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=3)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.text, "html.parser")
        titles = [a.get_text().strip() for a in soup.select(".title") if a.get_text().strip()]
        return titles[0] if titles else ""
    except:
        return ""

market = get_market_index()
fear_score, fear_label, fear_color = get_fear_greed()
from datetime import datetime, timezone, timedelta
KST = timezone(timedelta(hours=9))
now = datetime.now(KST).strftime("%Y.%m.%d %H:%M")

cols_m = st.columns([1,1,1,2])
for i, (name, (val, chg)) in enumerate(market.items()):
    color = "#ff3355" if chg > 0 else "#4f8ef7"
    arrow = "?? if chg > 0 else "??
    cols_m[i].markdown(f"""
    <div class='market-card'>
      <div style='color:#6b7280;font-size:10px;font-weight:600;letter-spacing:1px;text-transform:uppercase;'>{name}</div>
      <div style='color:#f0f4ff;font-size:20px;font-weight:800;margin:4px 0;letter-spacing:-0.5px;'>{val:,.2f}</div>
      <div style='color:{color};font-size:13px;font-weight:600;'>{arrow} {abs(chg):.2f}%</div>
    </div>""", unsafe_allow_html=True)

if fear_score is not None:
    bar_w = fear_score
    if fear_score >= 75:   bar_color = "#ff3355"
    elif fear_score >= 55: bar_color = "#ff8c42"
    elif fear_score >= 45: bar_color = "#ffd700"
    elif fear_score >= 25: bar_color = "#4f8ef7"
    else:                  bar_color = "#00d4aa"
    cols_m[2].markdown(f"""
    <div class='market-card'>
      <div style='color:#6b7280;font-size:10px;font-weight:600;letter-spacing:1px;text-transform:uppercase;'>공포/?�욕</div>
      <div style='color:{fear_color};font-size:20px;font-weight:800;margin:4px 0;'>{fear_score}</div>
      <div style='color:{fear_color};font-size:12px;font-weight:600;'>{fear_label}</div>
      <div style='background:rgba(255,255,255,0.06);border-radius:4px;height:3px;margin-top:6px;'>
        <div style='background:{bar_color};width:{bar_w}%;height:3px;border-radius:4px;box-shadow:0 0 6px {bar_color};'></div>
      </div>
    </div>""", unsafe_allow_html=True)

cols_m[3].markdown(f"""
    <div class='market-card' style='text-align:right;'>
      <div style='color:#6b7280;font-size:10px;font-weight:600;letter-spacing:1px;text-transform:uppercase;'>기�??�각 (1~2�?지??</div>
      <div style='color:#e8edf8;font-size:17px;font-weight:700;margin-top:6px;letter-spacing:-0.3px;'>{now}</div>
      <div style='color:#3d4466;font-size:11px;margin-top:4px;'>KST</div>
    </div>""", unsafe_allow_html=True)

# ?�?� ?�단 메뉴 ???�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
if "mode" not in st.session_state:
    st.session_state["mode"] = "?�� 급등 ?�고 종목 ?��?"

tab_labels = ["?�� 급등 ?�고 종목 ?��?", "?�� 최적 급등 ?�?�밍", "?�� 개별 종목 분석", "�?즐겨찾기", "?�� 백테?�트", "?�� ?�과 추적"]
tab_cols = st.columns(6)
for i, (col, label) in enumerate(zip(tab_cols, tab_labels)):
    active = st.session_state["mode"] == label
    if col.button(label, key=f"tab_{i}", width='stretch',
                  type="primary" if active else "secondary"):
        st.session_state["mode"] = label
        if label == "�?즐겨찾기":
            st.session_state.pop("fav_loaded", None)  # ??진입 ???�로??
        st.rerun()

mode = st.session_state["mode"]
st.markdown("---")

# ?�?� ?�이?�바: 조건 ?�정 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
with st.sidebar:
    st.markdown("---")
    st.markdown("### ?�️ ?�심 조건 ?�정")

    if "max_gap"   not in st.session_state: st.session_state["max_gap"]   = 10
    if "min_below" not in st.session_state: st.session_state["min_below"] = 120
    if "max_cross" not in st.session_state: st.session_state["max_cross"] = 60
    if "min_score" not in st.session_state: st.session_state["min_score"] = 15

    if st.button("??최적 ?�팅", width='stretch'):
        st.session_state["max_gap"]   = 10
        st.session_state["min_below"] = 120
        st.session_state["max_cross"] = 60
        st.session_state["min_score"] = 15
        st.session_state.pop("scan_results", None)  # 조건 바뀌면 결과 초기??
        st.rerun()

    max_gap   = st.slider("?�� 240??근처 범위 (%)", 1, 20, key="max_gap",
        help="?�재가가 240?�선 ??�?% ?�내?��? (?�을?�록 ?�격)")
    min_below = st.slider("?�� 최소 조정 기간 (??", 60, 300, key="min_below",
        help="240?�선 ?�래 최소 체류 ?�수 (120=6개월, 240=1??")
    max_cross = st.slider("?�� ?�파 ??최�? 경과 (??", 10, 180, key="max_cross",
        help="240?�선 ?�파 ??최�? 경과 ?�수")
    min_score = st.slider("?�� 최소 종합?�수", 0, 40, key="min_score",
        help="???�수 ?�상??종목�??�시 (0=?�체, ?�을?�록 ?�격)")

    # 조건??바뀌면 기존 ?�캔 결과 초기??
    _cur_cond = (st.session_state["max_gap"], st.session_state["min_below"],
                 st.session_state["max_cross"], st.session_state["min_score"])
    if st.session_state.get("_last_cond") != _cur_cond:
        st.session_state["_last_cond"] = _cur_cond
        st.session_state.pop("scan_results", None)
    st.markdown("---")
    st.markdown("""**?�� 추�? ?�수 ?�호**
| ?�호 | ?�수 |
|------|------|
| ?? ?�파 ??거래????��(3�?) | 4??|
| ?�� ?�파 ??거래??급증(2�?) | 3??|
| ?�� ?�파 ?�후 거래??지??| 2??|
| ?�� 최근 거래??증�? | 2??|
| ?�� 기�?+?�국???�시 ?�매??| 4??|
| ??기�? ?�는 ?�국???�매??| 2??|
| ?�� OBV 지???�승 | 2??|
| ???�평???�배??| 3??|
| ?�� ?�림�????�상??| 2??|
| ?�� RSI 건강 구간 | 2??|
| ?�� BB?�축?�확??| 3??|
| ?�� MACD ?�로??| 2??|
| ?�� 240???�승 ?�환 | 3??|
| ?�� MFI 과매??반등 | 2??|
| ?�� ?�토캐스???�로??| 2??|
| ?�� ADX 강한 추세 | 2??|
| ?�� VWAP ??| 2??|
| ?�️ ?�목균형???�파 | 3??|
| ?�� 52�??�고가 근처 | 2??|
| ?�� ?�승??가??| 2??|
| ?�� ?�터 강세 | 최�? 3??|
| ?�� ?�종 ?�터 ?�반 ?�승 | 최�? 3??|
| ?�� 3???�속 거래??가�?| 3??|
| ?�� ?��? ?�림�?3~15%) | 3??|
| ?���??�력 매집 감�? | 3??|
| ?�� ?�림�?반등 | 3??|
| ?�� 캔들 ?�턴 | 1~2??|
| ??조정 기간 가??| 1~3??|
| ?�� 긍정 ?�스 | 1~2??|
| ?�� ?�재 공시 | 2??|
| ?? 복합 ?�호 ?�수 | ×1.2~1.3 |""")
    st.markdown("---")
    st.caption("?�️ ?�자 ?�실??책임지지 ?�습?�다")

# ?�?� localStorage 즐겨찾기 ?�퍼 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
def ls_get_favorites() -> dict:
    """session_state?�서 즐겨찾기 로드"""
    if "favorites" not in st.session_state:
        st.session_state["favorites"] = {}
    return st.session_state["favorites"]

def ls_save_favorites(favs: dict):
    """즐겨찾기 ?�??- session_state"""
    st.session_state["favorites"] = favs

def ls_load_from_browser():
    """브라?��? localStorage?�서 즐겨찾기 로드 - st_javascript 미사??""
    pass  # localStorage ?�기??비활?�화 (?�더�??�이�?방�?)

def ls_persist_to_browser():
    """즐겨찾기�?localStorage???�기??- st_javascript 미사??""
    pass  # localStorage ?�기??비활?�화 (?�더�??�이�?방�?)

# ?�?� 캐시 ?�수 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
@st.cache_data(ttl=86400)
def get_all_krx_stocks() -> dict:
    """KRX ?�체 ?�장 종목 로드 (JSON ?�일 ?�선, ?�으�?KRX?�서 ?�운로드)"""
    import json, os
    json_path = os.path.join(os.path.dirname(__file__), "krx_stocks.json")
    try:
        if os.path.exists(json_path):
            with open(json_path, encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    # JSON ?�으�?KRX?�서 ?�운로드
    try:
        import io
        result = {}
        for market, suffix in [("stockMkt","KS"), ("kosdaqMkt","KQ")]:
            url = f"https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType={market}"
            r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
            df = pd.read_html(io.StringIO(r.content.decode("euc-kr")), header=0)[0]
            for _, row in df.iterrows():
                name = str(row["?�사�?]).strip()
                code = str(row["종목코드"]).strip().zfill(6)
                result[f"{code}.{suffix}"] = name
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
        return result
    except:
        return {}

@st.cache_data(ttl=300)
def search_stock_by_name(query: str) -> list:
    """종목명으�?검??(KRX ?�체 2600+ 종목)"""
    from stock_surge_detector import STOCK_NAMES as DET_NAMES
    all_names = {**STOCK_NAMES, **DET_NAMES}
    all_names.update(get_all_krx_stocks())

    q = query.strip()
    matches = [(k, v) for k, v in all_names.items() if q in v]
    matches.sort(key=lambda x: (not x[1].startswith(q), x[1]))
    return matches[:20]
@st.cache_data(ttl=300)
def get_chart_data(symbol, period="2y"):
    try:
        df = yf.Ticker(symbol).history(period=period)
        if df is None or len(df) == 0:
            return None
        df = df.dropna(subset=["Open","High","Low","Close"])
        return df if len(df) > 0 else None
    except:
        return None

def metric_card(col, label, value):
    col.markdown(f"""<div class="metric-card">
        <div class="lbl">{label}</div><div class="val">{value}</div>
    </div>""", unsafe_allow_html=True)


def calc_rsi_wilder(close, period=20):
    """Wilder's Smoothing RSI (EWM 방식 - stock_surge_detector._rsi?� ?�일)"""
    d = close.diff()
    gain = d.where(d > 0, 0.0)
    loss = -d.where(d < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    return 100 - (100 / (1 + rs))

def show_price_levels(fig, split_buy=False):
    """차트 ?�래??목표가/매수가/?�절가 박스 ?�시"""
    if not hasattr(fig, '_price_levels') or fig._price_levels is None:
        return
    lv = fig._price_levels
    import math
    if any(math.isnan(v) for v in [lv["target"], lv["current"], lv["stop"]] if isinstance(v, float)):
        return

    rr = lv["rr_ratio"]
    rr_color = "#00ff88" if rr >= 3 else "#ffd700" if rr >= 2 else "#ff8c42"
    rr_label = "?�수" if rr >= 3 else "?�호" if rr >= 2 else "주의"

    st.markdown(f"""
    <div style='display:flex;gap:8px;margin:-8px 0 4px;'>
      <div style='flex:1.2;background:rgba(0,255,136,0.08);border:1px solid #00ff88;
           border-radius:10px;padding:12px;text-align:center;'>
        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>?�� 목표가</div>
        <div style='color:#00ff88;font-size:18px;font-weight:700;margin:4px 0;'>??lv["target"]:,.0f}</div>
        <div style='color:#00ff88;font-size:12px;'>+{lv["upside"]:.1f}%</div>
        <div style='color:#4a5568;font-size:10px;margin-top:4px;'>Fib×ATR 가중평�?/div>
      </div>
      <div style='flex:1;background:rgba(255,215,0,0.08);border:1px solid #ffd700;
           border-radius:10px;padding:12px;text-align:center;'>
        {'<div style="color:#8b92a5;font-size:10px;letter-spacing:1px;">?�� 분할매수</div><div style="color:#ffd700;font-size:18px;font-weight:700;margin:4px 0;">?? + f'{lv.get("ma240", lv["entry"]):,.0f}' + ' ~ ?? + f'{lv["entry"]:,.0f}' + '</div><div style="color:#4a5568;font-size:10px;margin-top:4px;">240??근처 분할매수</div>' if split_buy else '<div style="color:#8b92a5;font-size:10px;letter-spacing:1px;">?�� 매수가</div><div style="color:#ffd700;font-size:18px;font-weight:700;margin:4px 0;">?? + f'{lv["entry"]:,.0f}' + '</div><div style="color:#ffd700;font-size:12px;">' + lv.get("entry_label","근거가") + ' 기�?</div><div style="color:#4a5568;font-size:10px;margin-top:4px;">240??근거 진입가</div>'}
      </div>
      <div style='flex:1;background:rgba(255,51,85,0.08);border:1px solid #ff3355;
           border-radius:10px;padding:12px;text-align:center;'>
        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>?�� ?�절가</div>
        <div style='color:#ff3355;font-size:18px;font-weight:700;margin:4px 0;'>??lv["stop"]:,.0f}</div>
        <div style='color:#ff3355;font-size:12px;'>{lv["downside"]:.1f}%</div>
        <div style='color:#4a5568;font-size:10px;margin-top:4px;'>?�윙?�??ATR×1.5</div>
      </div>
      <div style='flex:0.8;background:rgba(255,215,0,0.08);border:1px solid {rr_color};
           border-radius:10px;padding:12px;text-align:center;'>
        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>?�️ ?�익�?/div>
        <div style='color:{rr_color};font-size:22px;font-weight:700;margin:4px 0;'>{rr:.1f}:1</div>
        <div style='color:{rr_color};font-size:11px;'>{rr_label}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

def make_rsi_chart(rsi_s, chart_data=None):
    """RSI 차트 - ?�베?�트증권 ?��??? ?��?/축소 비활?�화"""
    if chart_data is not None:
        try:
            rsi_idx   = rsi_s.index.tz_localize(None) if rsi_s.index.tz is not None else rsi_s.index
            chart_idx = chart_data.index.tz_localize(None) if chart_data.index.tz is not None else chart_data.index
            start = chart_idx[0]
            end   = chart_idx[-1]
            mask  = (rsi_idx >= start) & (rsi_idx <= end)
            rsi_s = pd.Series(rsi_s.values[mask], index=rsi_idx[mask])
        except Exception:
            pass

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=rsi_s.index, y=rsi_s.values,
        name="RSI(20)", line=dict(color="#4f8ef7", width=1.5),
        fill="tozeroy", fillcolor="rgba(79,142,247,0.05)"
    ))
    fig.add_hline(y=30, line=dict(color="#00d4aa", dash="dash", width=1),
                  annotation_text="30", annotation_font_color="#00d4aa",
                  annotation_position="right")
    fig.add_hline(y=70, line=dict(color="#ff4b6e", dash="dash", width=1),
                  annotation_text="70", annotation_font_color="#ff4b6e",
                  annotation_position="right")
    fig.add_hline(y=50, line=dict(color="#555", dash="dot", width=1))
    fig.add_hrect(y0=0,  y1=30,  fillcolor="rgba(0,212,170,0.06)",  line_width=0)
    fig.add_hrect(y0=70, y1=100, fillcolor="rgba(255,75,110,0.06)", line_width=0)

    # 30 ?�향?�파 (?�전 <= 30, ?�재 > 30) ??초록 ???�살??
    cross_up = (rsi_s.shift(1) <= 30) & (rsi_s > 30)
    for dt, val in rsi_s[cross_up].items():
        fig.add_annotation(
            x=dt, y=val,
            text="??, showarrow=False,
            font=dict(color="#00d4aa", size=14),
            yshift=8
        )

    # 70 ?�향?�탈 (?�전 >= 70, ?�재 < 70) ??빨간 ?�래 ?�살??
    cross_down = (rsi_s.shift(1) >= 70) & (rsi_s < 70)
    for dt, val in rsi_s[cross_down].items():
        fig.add_annotation(
            x=dt, y=val,
            text="??, showarrow=False,
            font=dict(color="#ff4b6e", size=14),
            yshift=-8
        )

    fig.update_layout(
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font=dict(color="#8b92a5"),
        yaxis=dict(range=[0,100], gridcolor="#1e2540", title="RSI",
                   tickvals=[0,20,30,50,70,80,100], fixedrange=True),
        xaxis=dict(gridcolor="#1e2540", rangeslider_visible=False, fixedrange=True),
        height=120, margin=dict(l=40,r=40,t=20,b=5),
        title=dict(text="RSI(20)", font=dict(color="#e0e6f0", size=13)),
        showlegend=False,
        dragmode=False,
    )
    return fig

def _calc_price_levels_from_data(data):
    """symbol ?�이 data DataFrame?�로 가�??�벨 계산 (telegram_alert.calc_price_levels?� ?�일 로직)"""
    def _tick(p):
        if p < 2000:      t = 1
        elif p < 5000:    t = 5
        elif p < 20000:   t = 10
        elif p < 50000:   t = 50
        elif p < 200000:  t = 100
        elif p < 500000:  t = 500
        else:             t = 1000
        return int(round(p / t) * t)
    try:
        import numpy as np
        df = data.dropna(subset=["Close","High","Low"])
        if len(df) < 30:
            return {}
        close = df["Close"]; high = df["High"]; low = df["Low"]
        current = float(close.iloc[-1])
        tr = pd.concat([high-low,(high-close.shift(1)).abs(),(low-close.shift(1)).abs()],axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().dropna().iloc[-1])
        ma240 = close.rolling(240).mean()
        ma240_v = float(ma240.iloc[-1]) if not pd.isna(ma240.iloc[-1]) else None
        ma20 = float(close.rolling(20).mean().iloc[-1])
        swing_low_20 = float(low.tail(20).min())
        entry_candidates = []
        if ma240_v:
            entry_candidates.append(("240??버퍼", ma240_v * 1.005))
        entry_candidates.append(("?�윙?�??, swing_low_20))
        entry_candidates.append(("MA20", ma20))
        valid = [(l,p) for l,p in entry_candidates if p < current * 0.98 and (ma240_v is None or p >= ma240_v * 0.99)]
        if valid:
            entry_label, entry = max(valid, key=lambda x: x[1])  # 가???��? �?= ?�재가??가??가까운 지지??
        else:
            entry_label, entry = "?�재가", current
        stop_cands = []
        if ma240_v: stop_cands.append(ma240_v * 0.995)
        stop_cands.append(swing_low_20 - atr * 1.0)
        stop = max(stop_cands) if stop_cands else entry * 0.93
        stop = max(stop, entry * 0.85)
        risk = max(entry - stop, entry * 0.01)
        recent_high = float(high.tail(120).max()); recent_low = float(low.tail(120).min())
        swing_range = max(recent_high - recent_low, entry * 0.01)
        candidates = sorted([x for x in [
            recent_low+swing_range*1.272, recent_low+swing_range*1.618,
            recent_low+swing_range*2.0, recent_high*1.05,
            entry+atr*3.0, entry+atr*5.0] if x > entry*1.03])
        min_rr3 = entry + risk * 3.0
        valid_t = [x for x in candidates if x >= min_rr3]
        if valid_t:
            weights = [1/(x-entry) for x in valid_t]
            target = sum(x*w for x,w in zip(valid_t,weights))/sum(weights)
        elif candidates: target = candidates[-1]
        else: target = entry + risk * 3.0
        target = min(target, entry * 2.0)
        rr = (target - entry) / (entry - stop + 1e-9)
        entry  = _tick(entry)
        target = _tick(target)
        stop   = _tick(stop)
        rr     = (target - entry) / (entry - stop + 1e-9)
        ma240_tick = _tick(ma240_v) if ma240_v else entry
        return {"current":current,"entry":entry,"entry_label":entry_label,"target":target,
                "ma240":ma240_tick,
                "stop":stop,"rr":rr,"upside":(target/entry-1)*100,"downside":(stop/entry-1)*100}
    except:
        return {}


def make_candle(data, title, ma240_series=None, cross_date=None, show_levels=True, symbol=None):
    fig = go.Figure()

    # ?�?� Heikin-Ashi 계산 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
    ha_close = (data["Open"] + data["High"] + data["Low"] + data["Close"]) / 4
    ha_open = ha_close.copy()
    for i in range(1, len(ha_open)):
        ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
    ha_high = pd.concat([data["High"], ha_open, ha_close], axis=1).max(axis=1)
    ha_low  = pd.concat([data["Low"],  ha_open, ha_close], axis=1).min(axis=1)

    fig.add_trace(go.Candlestick(
        x=data.index,
        open=ha_open, high=ha_high, low=ha_low, close=ha_close,
        name="Heikin-Ashi",
        increasing=dict(line=dict(color="#ff3355", width=1), fillcolor="#ff3355"),
        decreasing=dict(line=dict(color="#4f8ef7", width=1), fillcolor="#4f8ef7"),
    ))
    for w,c,nm in [(20,"#ffd700","MA20"),(60,"#ff8c42","MA60"),(240,"#ff4b6e","MA240")]:
        ma = data["Close"].rolling(w).mean()
        fig.add_trace(go.Scatter(x=data.index, y=ma, name=nm,
            line=dict(color=c, width=3 if w==240 else 1.2)))
    if cross_date is not None:
        pass  # ?�파 ?�시 ?�거

    fig._price_levels = None
    if show_levels:
        try:
            # data 기반?�로 직접 계산 (yfinance ?�호�??�음)
            lv = _calc_price_levels_from_data(data)
            if lv and lv.get("target"):
                target   = lv["target"]
                entry    = lv["entry"]
                entry_label = lv.get("entry_label", "매수")
                stop     = lv["stop"]
                current  = lv["current"]
                upside   = lv["upside"]
                downside = lv["downside"]
                rr_ratio = lv["rr"]
                fig.add_hline(y=target, line=dict(color="#00ff88", width=2, dash="dash"))
                fig.add_hrect(y0=entry, y1=target, fillcolor="rgba(0,255,136,0.08)", line_width=0)
                if entry < current:
                    fig.add_hline(y=entry, line=dict(color="#ffd700", width=2, dash="dashdot"))
                    fig.add_hrect(y0=stop, y1=entry, fillcolor="rgba(255,51,85,0.08)", line_width=0)
                fig.add_hline(y=current, line=dict(color="#ffffff", width=1.5, dash="dot"))
                fig.add_hline(y=stop, line=dict(color="#ff3355", width=2, dash="dash"))
                fig._price_levels = dict(target=target, current=current, entry=entry,
                                         entry_label=entry_label, stop=stop,
                                         ma240=lv.get("ma240", entry),
                                         upside=upside, downside=downside, rr_ratio=rr_ratio)
        except Exception:
            pass

    fig.update_layout(
        title=dict(text=title, font=dict(color="#e0e6f0", size=13)),
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font=dict(color="#8b92a5"),
        yaxis=dict(gridcolor="#1e2540", fixedrange=True, side="right", showticklabels=True),
        xaxis=dict(gridcolor="#1e2540", rangeslider_visible=False, fixedrange=True),
        legend=dict(bgcolor="#1e2130", bordercolor="#2d3555", visible=False),
        dragmode=False,
        height=500, margin=dict(l=0,r=50,t=30,b=0))
    return fig

# ?�?� 급등 ?�고 종목 ?��? ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
if mode == "?�� 급등 ?�고 종목 ?��?":

    # ?�?� ?�늘 캐시 ?�동 로드 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
    if "scan_results" not in st.session_state:
        try:
            cached_today = load_scan()  # ?�늘 ?�짜 기본�?
            if cached_today:
                # 리스?�로 ?�?�된 ?�리�??�이?��? pandas Series�?복원
                import pandas as _pd
                series_keys = ["close_series","open_series","high_series","low_series",
                               "volume_series","ma240_series","ma60_series","ma20_series",
                               "rsi_series","vol_ma_series"]
                for r in cached_today:
                    for k in series_keys:
                        if k in r and isinstance(r[k], list):
                            r[k] = _pd.Series(r[k])
                st.session_state["scan_results"] = cached_today
                st.info(f"?�� ?�늘 캐시???�캔 결과 {len(cached_today)}�?로드??(?�스캔하?�면 '?�캔 ?�작' ?�릭)")
        except:
            pass

    # ?�재 조건 ?�시
    st.markdown(f"""<div class="cond-box">
      <b style="color:#e0e6f0;">?�재 ?��? 조건</b><br>
      ?�� 240?�선 ?�래 <b style="color:#ffd700;">{min_below}??{min_below//20}개월) ?�상</b> 조정 ??
      ?�� 최근 <b style="color:#00d4aa;">{max_cross}???�내</b> 240?�선 ?�향 ?�파 ??
      ?�� ?�재 주�? 240?�선 ??<b style="color:#4f8ef7;">0~{max_gap}%</b> ?�내
    </div>""", unsafe_allow_html=True)

    if st.button("?? ?�캔 ?�작", type="primary", width='stretch'):
        st.session_state.pop("scan_results", None)  # 기존 결과 초기??
        det = KoreanStockSurgeDetector(max_gap, min_below, max_cross)
        symbols = list(dict.fromkeys(det.all_symbols))  # 중복 ?�거
        total = len(symbols)

        st.markdown("<div class='sec-title'>?�� ?�캔 진행 �?..</div>", unsafe_allow_html=True)
        prog_bar  = st.progress(0)
        prog_text = st.empty()

        results = []
        completed = [0]

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _scan(symbol):
            return det.analyze_stock(symbol)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(_scan, sym): sym for sym in symbols}
            for future in as_completed(futures):
                completed[0] += 1
                sym = futures[future]
                prog_text.markdown(
                    f"<span style='color:#8b92a5;font-size:13px;'>"
                    f"({completed[0]}/{total}) {sym} 분석 �?..</span>",
                    unsafe_allow_html=True
                )
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

        # DB 캐싱 (?�리�??�이???�함 ?�??
        try:
            import pandas as _pd
            def _serialize(r):
                out = {}
                for k, v in r.items():
                    if isinstance(v, _pd.Series):
                        out[k] = v.tolist()
                    elif hasattr(v, 'tolist'):  # numpy array
                        out[k] = v.tolist()
                    else:
                        out[k] = v
                return out
            save_scan([_serialize(r) for r in results])
        except:
            pass

    # session_state ?�으�??�무것도 ?�시 ????(?�동 로드 ?�음)
    results = st.session_state.get("scan_results", [])

    if "scan_results" not in st.session_state:
        pass  # ?�캔 ??- �??�면
    elif not results:
        st.warning("?�재 조건??만족?�는 종목???�습?�다.")
        st.info("?�� ?�이?�바?�서 조건???�화?�보?�요:\n- '240??근처 범위'�??�리거나\n- '최소 조정 기간'??줄이거나\n- '?�파 ??최�? 경과'�??�려보세??)
    else:
            st.success(f"??{len(results)}�?종목??모든 ?�심 조건??충족?�니??")

            # ?�약 카드
            c1,c2,c3,c4 = st.columns(4)
            metric_card(c1, "발견 종목", f"{len(results)}�?)
            metric_card(c2, "?�균 조정 기간", f"{int(sum(r['below_days'] for r in results)/len(results))}??)
            metric_card(c3, "?�균 240???�격", f"+{sum(r['ma240_gap'] for r in results)/len(results):.1f}%")
            metric_card(c4, "최고 ?�수", f"{max(r['total_score'] for r in results)}??)

            st.markdown("<div class='sec-title'>?�� 급등 ?�고 종목 ?�체</div>", unsafe_allow_html=True)

            # ?�이�?
            rows = []
            for r in results:
                s = r["signals"]
                rows.append({
                    "종목�?:     r["name"],
                    "종목코드":   r["symbol"],
                    "?�재가":     f"??r['current_price']:,.0f}",
                    "?�락�?:     f"{'?��' if r['price_change_1d']>0 else '?��'}{r['price_change_1d']:.2f}%",
                    "240?�선":    f"??r['ma240']:,.0f}",
                    "240?�이�?:  f"+{r['ma240_gap']:.1f}%",
                    "조정기간":   f"{r['below_days']}??{r['below_days']//20}개월)",
                    "?�파??:     f"{r['days_since_cross']}??,
                    "?�파강도":   f"{r.get('cross_gap_pct', 0):.1f}%",
                    "RSI":        r["rsi"],
                    "종합?�수":   r["total_score"],
                    "?�점??:     r.get("raw_score", r["total_score"]),
                    "?�심?�호":   f"{r.get('core_signal_count', 0)}�?,
                    "거래??:     "?? if s.get("vol_strong_cross") else ("?��" if s.get("vol_at_cross") else "??),
                    "?�급":       "?��" if r.get("both_buying") else ("?? if r.get("smart_money_in") else "??),
                    "OBV":        "?? if s.get("obv_rising") else "??,
                    "?�배??:     "?? if s.get("ma_align") else "??,
                    "BB?�축":     "?? if s.get("bb_squeeze_expand") else "??,
                    "MACD":       "?? if s.get("macd_cross") else "??,
                    "240?�환":    "?? if s.get("ma240_turning_up") else "??,
                    "MFI":        "?? if s.get("mfi_oversold_recovery") else "??,
                    "?�토캐스??: "?? if s.get("stoch_cross") else "??,
                    "ADX":        "?? if s.get("adx_strong") else "??,
                    "VWAP":       "?? if s.get("above_vwap") else "??,
                    "?�목":       "?? if s.get("ichimoku_bull") else "??,
                    "52주고??:   "?? if s.get("near_52w_high") else "??,
                })
            df = pd.DataFrame(rows)
            st.dataframe(df,
                column_config={
                    "종합?�수": st.column_config.ProgressColumn(
                        "종합?�수(ML보정)", min_value=0, max_value=50, format="%d??),
                    "?�점??: st.column_config.ProgressColumn(
                        "?�점??, min_value=0, max_value=39, format="%d??),
                    "RSI": st.column_config.ProgressColumn(
                        "RSI", min_value=0, max_value=100, format="%.1f"),
                    "?�급": st.column_config.TextColumn("기�?/?�국??, help="?��=?�시매수 ???�쪽매수 ???�음"),
                    "거래??: st.column_config.TextColumn("거래??, help="??3배이???��=2배이????미달"),
                },
                width='stretch', hide_index=True)

            # 차트
            if len(results) > 1:
                fig = px.bar(pd.DataFrame(results), x="name", y="total_score",
                    color="total_score", color_continuous_scale="Greens",
                    labels={"name":"종목�?,"total_score":"?�수"}, title="종합 ?�수")
                fig.update_layout(paper_bgcolor="#0e1117",plot_bgcolor="#0e1117",
                    font=dict(color="#8b92a5"),xaxis_tickangle=30,
                    coloraxis_showscale=False,height=240,margin=dict(l=5,r=5,t=30,b=50))
                st.plotly_chart(fig, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":False}, width='stretch', key="chart_score_bar")

            # ?�세 카드
            st.markdown("<div class='sec-title'>?�� 종목�??�세 분석</div>", unsafe_allow_html=True)
            medals = ["gold","silver","bronze"]
            icons  = ["?��","?��","?��"]

            for i, r in enumerate(results):
                medal = medals[i] if i < 3 else "rank-card"
                icon  = icons[i]  if i < 3 else f"{i+1}."
                pct   = r["total_score"] / 28 * 100
                color = "#ff3355" if r["price_change_1d"] > 0 else "#4f8ef7"
                arrow = "?? if r["price_change_1d"] > 0 else "??

                # ?�파?�라???�거 (?�더�?충돌 방�?)
                spark_svg = ""
                news = get_news_headline(r["symbol"])
                import html as _html
                news_safe = _html.escape(news) if news else ""
                below_months = r["below_days"] // 20
                # ?�시�?가�?
                rt_price = get_realtime_price(r["symbol"])
                display_price = rt_price if rt_price else r["current_price"]
                # ?�급 문자???�전 계산 (f-string 충돌 방�?)
                if r.get("both_buying"):
                    supply_str = "?��기�?+?�국??
                elif r.get("smart_money_in"):
                    supply_str = "?�수급있??
                else:
                    supply_str = "?�수급없??

                st.markdown(f"""<div class="rank-card {medal}">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                      <span style="font-size:20px;">{icon}</span>
                      <span style="color:#fff;font-size:clamp(14px,3vw,18px);font-weight:700;margin-left:6px;">{r["name"]}</span>
                      <span style="color:#8b92a5;font-size:13px;margin-left:8px;">{r["symbol"]}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:12px;">
                      <div style="text-align:right;">
                        <span style="color:#fff;font-size:clamp(14px,3vw,20px);font-weight:700;">??display_price:,.0f}</span>
                        <span style="color:{color};font-size:14px;margin-left:8px;">{arrow} {abs(r["price_change_1d"]):.2f}%</span>
                      </div>
                    </div>
                  </div>
                  <div style="margin-top:6px;color:#8b92a5;font-size:12px;">
                    240?�선 ??r["ma240"]:,.0f} | ?�격 +{r["ma240_gap"]:.1f}% |
                    조정 {r["below_days"]}??{below_months}개월) | ?�파 {r["days_since_cross"]}????| ?�파강도 {r.get("cross_gap_pct",0):.1f}% |
                    ?�급 {supply_str} | ?�심?�호 {r.get("core_signal_count",0)}�?
                  </div>
                </div>""", unsafe_allow_html=True)
                # 즐겨찾기 버튼 (localStorage 기반 - 기기�??�구 ?�??
                _fav_col, _news_col = st.columns([1, 5])
                _favs = ls_get_favorites()
                _is_fav = r["symbol"] in _favs
                _fav_label = "�?즐겨찾기 ?�제" if _is_fav else "??즐겨찾기"
                if _fav_col.button(_fav_label, key=f"fav_{r['symbol']}_{i}", width='stretch'):
                    if _is_fav:
                        _favs.pop(r["symbol"], None)
                    else:
                        _favs[r["symbol"]] = r["name"]
                    ls_save_favorites(_favs)
                    st.toast("�?즐겨찾기??추�??�어??" if not _is_fav else "즐겨찾기?�서 ?�거?�어??)
                if news_safe:
                    st.markdown(f'<div style="color:#6b7280;font-size:11px;padding:2px 8px 4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">?�� {news_safe}</div>', unsafe_allow_html=True)
                pct_str = f"{pct:.2f}"
                st.markdown(f"""<div style="padding:4px 8px 8px;">
                  <div style="color:#8b92a5;font-size:11px;margin-bottom:3px;">종합?�수 {r["total_score"]}??/div>
                  <div class="bar-bg"><div class="bar-fill" style="width:{pct_str}%;"></div></div>
                </div>""", unsafe_allow_html=True)

                if True:  # 바로 ?�시
                    m1,m2,m3,m4,m5 = st.columns(5)
                    m1.metric("RSI(20)", f"{r['rsi']:.1f}")
                    m2.metric("240???�격", f"+{r['ma240_gap']:.1f}%")
                    m3.metric("조정 기간", f"{r['below_days']}??)
                    m4.metric("?�파 ??, f"{r['days_since_cross']}??)
                    m5.metric("?�파강도", f"{r.get('cross_gap_pct',0):.1f}%")
                    # ?�급 ?�보
                    supply_label = "?�� 기�?+?�국?? if r.get("both_buying") else ("???�급?�음" if r.get("smart_money_in") else "???�급?�음")
                    st.caption(f"?�급: {supply_label}  |  ?�심?�호: {r.get('core_signal_count',0)}�? |  거래?�배?? {r.get('vol_ratio',0):.1f}�?)

                    s = r["signals"]
                    active = []
                    if s.get("vol_strong_cross"):       active.append(f"?? ?�파 ??거래????�� ({s['cross_vol_ratio']:.1f}�?- 강한 ?�파)")
                    elif s.get("vol_at_cross"):         active.append(f"?�� ?�파 ??거래??급증 ({s['cross_vol_ratio']:.1f}�?")
                    if s.get("vol_surge_sustained"):    active.append("?�� ?�파 ?�후 거래??지??증�?")
                    if s.get("recent_vol"):             active.append(f"?�� 최근 거래??증�? ({s['recent_vol_ratio']:.1f}�?")
                    if r.get("both_buying"):            active.append("?�� 기�?+?�국???�시 ?�매??(강한 ?�급)")
                    elif r.get("smart_money_in"):       active.append("??기�? ?�는 ?�국???�매??)
                    if s.get("obv_rising"):             active.append("?�� OBV 지???�승 (매집 진행 �?")
                    if s.get("ma_align"):               active.append("???�평???�배??(MA5>MA20>MA60)")
                    if s.get("pullback_recovery"):      active.append("?�� ?�림�????�상??)
                    if s.get("rsi_healthy"):            active.append(f"?�� RSI 건강 구간 ({s.get('rsi',0):.1f})")
                    if s.get("bb_squeeze_expand"):      active.append("?�� 볼린?�밴드 ?�축?�확??(??�� 직전)")
                    if s.get("macd_cross"):             active.append("?�� MACD 골든?�로??)
                    if s.get("ma240_turning_up"):       active.append("?�� 240?�선 ?�락?�상???�환")
                    if s.get("stealth_accumulation"):   active.append("?���??�력 매집 감�? (조용??거래??증�?)")
                    if s.get("pullback_bounce"):        active.append("?�� ?�림�?반등 (최적 진입 ?�?�밍)")
                    if s.get("peer_momentum", 0) >= 2: active.append(f"?�� ?�종 ?�터 ?�반 ?�승 ({s.get('peer_momentum')}�?")
                    if s.get("mfi_oversold_recovery"):  active.append(f"?�� MFI 과매??반등 ({s.get('mfi',0):.0f})")
                    if s.get("stoch_cross"):            active.append(f"?�� ?�토캐스??골든?�로??({s.get('stoch_k',0):.0f})")
                    if s.get("adx_strong"):             active.append(f"?�� ADX 강한 추세 ({s.get('adx',0):.0f})")
                    if s.get("above_vwap"):             active.append("?�� VWAP ??(매수???�위)")
                    if s.get("ichimoku_bull"):          active.append("?�️ ?�목균형??구름?� ?�파")
                    if s.get("near_52w_high"):          active.append(f"?�� 52�??�고가 근처 ({s.get('high_ratio',0):.1f}%)")
                    if s.get("market_bull"):            active.append(f"?�� ?�승??({s.get('market_slope',0):+.1f}%)")
                    if s.get("sector_momentum",0) > 2:  active.append(f"?�� ?�터 강세 ({s.get('sector_momentum',0):+.1f}%)")
                    if s.get("vol_price_rising3"):      active.append("?�� 3???�속 거래??가�??�승")
                    pd_val = s.get("pullback_depth", 0)
                    if 3 <= pd_val <= 15:               active.append(f"?�� ?��? ?�림�?({pd_val:.1f}%)")
                    if s.get("hammer"):                 active.append("?�� 망치??캔들")
                    if s.get("bullish_engulf"):         active.append("?�� ?�악??캔들")
                    if r["below_days"] >= 240:          active.append(f"??1?? 충분??조정 ({r['below_days']}??")
                    if s.get("news_sentiment",0) > 0:   active.append(f"?�� 긍정 ?�스 {s.get('pos_news',0)}�?)
                    if s.get("has_disclosure"):         active.append(f"?�� ?�재 공시: {', '.join(s.get('disclosure_types',[]))}")

                    cols = st.columns(2)
                    for j, sig in enumerate(active):
                        cols[j%2].success(sig)
                    if not active:
                        st.info("추�? ?�호 ?�음 (?�심 조건�?충족)")

                    # ?�캔 ?�이??직접 ?�용 (yfinance ?�호�??�음 - Rate Limit 방�?)
                    cd = None
                    close_s = r.get("close_series")
                    if close_s is not None and len(close_s) > 20:
                        open_s  = r.get("open_series",  close_s)
                        high_s  = r.get("high_series",  close_s)
                        low_s   = r.get("low_series",   close_s)
                        vol_s   = r.get("volume_series", pd.Series(0, index=close_s.index))
                        cd = pd.DataFrame({"Open":open_s,"High":high_s,"Low":low_s,"Close":close_s,"Volume":vol_s})
                        # ?�일 종�?가 ?�캔 ?�이?�에 ?�으�?current_price�?추�?
                        from datetime import date as _date
                        import pandas as _pd
                        today_str = _date.today().isoformat()
                        last_date = str(cd.index[-1])[:10]
                        if last_date < today_str:
                            cur_p = float(r.get("current_price", 0))
                            if cur_p > 0:
                                new_idx = _pd.Timestamp(today_str, tz=cd.index.tz)
                                new_row = _pd.DataFrame(
                                    {"Open":[cur_p],"High":[cur_p],"Low":[cur_p],"Close":[cur_p],"Volume":[0]},
                                    index=[new_idx]
                                )
                                cd = _pd.concat([cd, new_row])
                    # ?�패 ???�캔 ?�이?�로 ?�백
                    if cd is None or len(cd) == 0:
                        close_s = r.get("close_series")
                        if close_s is not None:
                            cd = pd.DataFrame({
                                "Open":   r.get("open_series", close_s),
                                "High":   r.get("high_series", close_s),
                                "Low":    r.get("low_series",  close_s),
                                "Close":  close_s,
                                "Volume": r.get("volume_series", pd.Series(0, index=close_s.index))
                            })
                    if cd is not None and len(cd) > 20:
                        try:
                            cross_date = None
                            close_s = r.get("close_series")
                            if close_s is not None and r["days_since_cross"] < len(close_s):
                                cross_date = close_s.index[-(r["days_since_cross"]+1)]
                            _c1 = make_candle(cd, f"{r['name']} ({r['symbol']})", cross_date=cross_date, symbol=r["symbol"])
                            st.plotly_chart(_c1, width='stretch', key=f"candle_{r['symbol']}_{i}")
                            show_price_levels(_c1, split_buy=True)
                        except Exception as chart_err:
                            st.caption(f"차트 ?�류: {chart_err}")

# ?�?� 개별 종목 분석 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
elif mode == "?�� 개별 종목 분석":
    st.markdown("<div class='sec-title'>?�� 개별 종목 분석</div>", unsafe_allow_html=True)

    from stock_surge_detector import STOCK_NAMES as DET_NAMES
    all_names = {**STOCK_NAMES, **DET_NAMES}
    opts = [f"{v} ({k})" for k,v in sorted(all_names.items(), key=lambda x:x[1])]

    # 종목�?검??
    search_col, period_col = st.columns([4, 1])
    with search_col:
        search_query = st.text_input("?�� 종목�?검??, placeholder="?? ?�리기술, ?�성?�자, ?�테?�젠...")
    with period_col:
        period = st.selectbox("기간", ["2y","1y","6mo"])

    symbol = None
    name   = None

    if search_query.strip():
        matches = search_stock_by_name(search_query.strip())
        if matches:
            search_opts = [f"{v} ({k})" for k, v in matches]
            sel_search = st.selectbox("검??결과", search_opts, key="search_result")
            symbol = sel_search.split("(")[1].replace(")","").strip()
            name   = sel_search.split("(")[0].strip()
        else:
            st.warning(f"'{search_query}' 검??결과 ?�음")
    else:
        sel = st.selectbox("종목 ?�택 (?�체 목록)", opts)
        symbol = sel.split("(")[1].replace(")","").strip()
        name   = sel.split("(")[0].strip()

    if symbol and st.button("분석", type="primary"):
        with st.spinner(f"{name} 분석 �?.."):
            det = KoreanStockSurgeDetector(max_gap, min_below, max_cross)
            result = det.analyze_stock(symbol)
            data = get_chart_data(symbol, period)
        # 결과�?session_state???�??(즐겨찾기 버튼 ?�릭 ?�에???��?)
        st.session_state["indiv_result"] = result
        st.session_state["indiv_data"]   = data
        st.session_state["indiv_symbol"] = symbol
        st.session_state["indiv_name"]   = name

    # session_state?�서 결과 로드
    result = st.session_state.get("indiv_result") if st.session_state.get("indiv_symbol") == symbol else None
    data   = st.session_state.get("indiv_data")   if st.session_state.get("indiv_symbol") == symbol else None

    if data is not None:
        current = float(data["Close"].iloc[-1])
        prev    = float(data["Close"].iloc[-2])
        chg     = (current - prev) / prev * 100
        color   = "#00d4aa" if chg > 0 else "#ff4b6e"
        arrow   = "?? if chg > 0 else "??

        if result:
            pct = result["total_score"] / 28 * 100
            st.markdown(f"""<div class="rank-card gold" style="margin-bottom:16px;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <span style="color:#fff;font-size:24px;font-weight:700;">??{name}</span>
                  <span style="color:#00d4aa;font-size:13px;margin-left:10px;">?�심 조건 충족</span>
                </div>
                <div style="text-align:right;">
                  <span style="color:#fff;font-size:24px;font-weight:700;">??current:,.0f}</span>
                  <span style="color:{color};font-size:15px;margin-left:8px;">{arrow} {abs(chg):.2f}%</span>
                </div>
              </div>
              <div style="margin-top:10px;">
                <div style="color:#8b92a5;font-size:12px;margin-bottom:3px;">종합?�수 {result["total_score"]}??/ 28??/div>
                <div class="bar-bg"><div class="bar-fill" style="width:{pct}%;"></div></div>
              </div>
            </div>""", unsafe_allow_html=True)

            c1,c2,c3,c4 = st.columns(4)
            metric_card(c1,"RSI(20)",f"{result['rsi']:.1f}")
            metric_card(c2,"240???�격",f"+{result['ma240_gap']:.1f}%")
            metric_card(c3,"조정 기간",f"{result['below_days']}??{result['below_days']//20}개월)")
            metric_card(c4,"?�파 ??,f"{result['days_since_cross']}??)

            st.markdown("<div class='sec-title'>?�� ?�호 분석</div>", unsafe_allow_html=True)
            s = result["signals"]
            active, inactive = [], []
            checks = [
                (s.get("vol_at_cross"),         f"?�� ?�파 ??거래??급증 ({s.get('cross_vol_ratio',0):.1f}�?"),
                (s.get("recent_vol"),            f"?�� 최근 거래??증�? ({s.get('recent_vol_ratio',0):.1f}�?"),
                (s.get("stealth_accumulation"),  "?���??�력 매집 감�? (조용??거래??증�?)"),
                (s.get("pullback_bounce"),       "?�� ?�림�?반등 (최적 진입 ?�?�밍)"),
                (s.get("obv_rising"),            "?�� OBV 지???�승 (매집 진행 �?"),
                (s.get("ma_align"),              "???�평???�배??(MA5>MA20>MA60)"),
                (s.get("pullback_recovery"),     "?�� ?�림�????�상??),
                (s.get("rsi_healthy"),           f"?�� RSI 건강 구간 ({s.get('rsi',0):.1f})"),
                (s.get("bb_squeeze_expand"),     "?�� 볼린?�밴드 ?�축?�확??(??�� 직전)"),
                (s.get("macd_cross"),            "?�� MACD 골든?�로??),
                (s.get("ma240_turning_up"),      "?�� 240?�선 ?�락?�상???�환"),
                (s.get("peer_momentum",0) >= 2,  f"?�� ?�종 ?�터 ?�반 ?�승 ({s.get('peer_momentum',0)}�?"),
                (s.get("hammer"),                "?�� 망치??캔들"),
                (s.get("bullish_engulf"),        "?�� ?�악??캔들"),
                (result["below_days"] >= 240,    f"??1?? 충분??조정 ({result['below_days']}??"),
                (s.get("news_sentiment",0) > 0,  f"?�� 긍정 ?�스 {s.get('pos_news',0)}�?),
                (s.get("has_disclosure"),        f"?�� ?�재 공시: {', '.join(s.get('disclosure_types',[]))}"),
            ]
            for flag, label in checks:
                (active if flag else inactive).append(label)

            ca, cb = st.columns(2)
            with ca:
                st.write("**??충족 ?�호**")
                for sig in active: st.success(sig)
                if not active: st.info("추�? ?�호 ?�음")
            with cb:
                st.write("**??미충�??�호**")
                for sig in inactive: st.error(sig)

            close_s2 = result.get("close_series")
            cross_date = close_s2.index[-(result["days_since_cross"]+1)] if close_s2 is not None else None
            _c2 = make_candle(data, f"{name} ({symbol})", cross_date=cross_date)
            st.plotly_chart(_c2, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":False}, width='stretch')
            show_price_levels(_c2)

            _favs2 = ls_get_favorites()
            _is_fav2 = symbol in _favs2
            if st.button("�?즐겨찾기 ?�제" if _is_fav2 else "??즐겨찾기 추�?", key=f"fav_indiv_{symbol}"):
                if _is_fav2: _favs2.pop(symbol, None)
                else: _favs2[symbol] = name
                ls_save_favorites(_favs2)
                st.toast("�?추�??�어??" if not _is_fav2 else "즐겨찾기?�서 ?�거?�어??)

            rsi_s = result["rsi_series"]

        else:
            st.markdown(f"""<div class="rank-card" style="margin-bottom:16px;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <span style="color:#fff;font-size:24px;font-weight:700;">?�️ {name}</span>
                  <span style="color:#ff4b6e;font-size:13px;margin-left:10px;">?�심 조건 미충�?/span>
                </div>
                <div style="text-align:right;">
                  <span style="color:#fff;font-size:24px;font-weight:700;">??current:,.0f}</span>
                  <span style="color:{color};font-size:15px;margin-left:8px;">{arrow} {abs(chg):.2f}%</span>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)

            close_clean = data["Close"].dropna()
            ma240_now = float(close_clean.rolling(240).mean().dropna().iloc[-1]) if len(close_clean) >= 240 else None
            current_clean = float(close_clean.iloc[-1])
            if ma240_now:
                gap = (current_clean - ma240_now) / ma240_now * 100
                c1,c2 = st.columns(2)
                metric_card(c1,"?�재 240???�격",f"{gap:+.1f}%")
                metric_card(c2,"240?�선",f"??ma240_now:,.0f}")
                if gap < 0:
                    st.warning(f"?�� ?�재 주�?가 240?�선 ?�래 ({gap:.1f}%) ???�직 조정 �?)
                elif gap > max_gap:
                    st.warning(f"?�� 240?�선 ??{gap:.1f}% ???��? 많이 ?�라 근처 범위({max_gap}%) 초과")
                else:
                    st.warning("?�� 240?�선 ?�파 ?�력 ?�는 조정 기간 조건 미충�?)

            _c3 = make_candle(data, f"{name} ({symbol})")
            st.plotly_chart(_c3, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":False}, width='stretch', key="chart_candle_no_cond")
            show_price_levels(_c3)

            _favs3 = ls_get_favorites()
            _is_fav3 = symbol in _favs3
            if st.button("�?즐겨찾기 ?�제" if _is_fav3 else "??즐겨찾기 추�?", key=f"fav_indiv_nc_{symbol}"):
                if _is_fav3: _favs3.pop(symbol, None)
                else: _favs3[symbol] = name
                ls_save_favorites(_favs3)
                st.toast("�?추�??�어??" if not _is_fav3 else "즐겨찾기?�서 ?�거?�어??)

            rsi_s = calc_rsi_wilder(data["Close"], period=20)


# ?�?� ?�량�?RSI 70 ?�탈 ?�캐???�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
elif mode == "?�� ?�량�?RSI 70 ?�탈":

    # ?�무 ?�량 + ?�장???��? 종목 (?�총 ?�위 + ?�적 ?�정)
    QUALITY_STOCKS = {
        # 반도�?IT
        "005930.KS": "?�성?�자",
        "000660.KS": "SK?�이?�스",
        "011070.KS": "LG?�노??,
        "035420.KS": "NAVER",
        "035720.KS": "카카??,
        # ?�동�?
        "005380.KS": "?��?�?,
        "000270.KS": "기아",
        "012330.KS": "?��?모비??,
        # 바이???�스
        "207940.KS": "?�성바이?�로직스",
        "068270.KS": "?�?�리??,
        "145020.KQ": "?�젤",
        "214150.KQ": "?�래?�스",
        "196170.KQ": "?�테?�젠",
        # 2차전지
        "006400.KS": "?�성SDI",
        "051910.KS": "LG?�학",
        "373220.KS": "LG?�너지?�루??,
        "247540.KQ": "?�코?�로비엠",
        # 금융
        "105560.KS": "KB금융",
        "055550.KS": "?�한지�?,
        "316140.KS": "?�리금융지�?,
        # 방산/중공??
        "042660.KS": "?�화?�션",
        "064350.KS": "?��?로템",
        "329180.KS": "HD?��?중공??,
        # ?�비/?�통
        "090430.KS": "?�모?�퍼?�픽",
        "097950.KS": "CJ?�일?�당",
        # ?�신
        "017670.KS": "SK?�레�?,
        "030200.KS": "KT",
        # ?�재
        "010130.KS": "고려?�연",
        "005490.KS": "POSCO?�?�스",
    }

    st.markdown("""
    <div style='background:linear-gradient(135deg,#1a1f35,#0e1117);
         padding:20px 24px;border-radius:12px;margin-bottom:16px;border:1px solid #2d3555;'>
      <h3 style='color:#fff;margin:0;'>?�� ?�무 ?�량�?RSI(20) ?�이???�성 ?�캐??/h3>
      <p style='color:#8b92a5;margin:8px 0 0;font-size:13px;'>
        ??RSI 30 ?�하 (과매?? ????RSI 30 ?�향?�파 ????RSI 70 ?�달 ????RSI 70 ?�탈<br>
        <b style='color:#ffd700;'>???�이???�성 ???�음 매수 ?�?�밍 준�?종목</b>
      </p>
    </div>
    """, unsafe_allow_html=True)

    days_ago = st.slider("?�� 최근 며칠 ?�내 70 ?�탈", 1, 60, 20, help="70???�탈??며칠 ?�내?��?")

    if st.button("?�� ?�캔 ?�작", type="primary", width='stretch'):
        results = []
        prog = st.progress(0)
        total = len(QUALITY_STOCKS)

        for idx, (symbol, name) in enumerate(QUALITY_STOCKS.items()):
            prog.progress((idx + 1) / total)
            try:
                df = yf.Ticker(symbol).history(period="2y")
                if df is None or len(df) < 60:
                    continue
                rsi = calc_rsi_wilder(df["Close"], 20).dropna()
                if len(rsi) < 40:
                    continue

                # ?�?� ?�이???��? ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
                # 1) RSI 30 ?�하 구간 존재
                below30 = rsi[rsi <= 30]
                if len(below30) == 0:
                    continue
                bottom_date = below30.index[0]
                bottom_rsi  = float(below30.min())

                # 2) 30 ?�향?�파 (bottom ?�후)
                after_bottom = rsi[rsi.index > bottom_date]
                cross30 = after_bottom[after_bottom > 30]
                if len(cross30) == 0:
                    continue
                cross30_date = cross30.index[0]

                # 3) 70 ?�달 (30?�파 ?�후)
                after_cross30 = rsi[rsi.index > cross30_date]
                above70 = after_cross30[after_cross30 >= 70]
                if len(above70) == 0:
                    continue
                peak_date = above70.index[0]
                peak_rsi  = float(above70.max())

                # 4) 70 ?�탈 (peak ?�후) ??최근 days_ago ?�내
                after_peak = rsi[rsi.index > peak_date]
                cross70_down = after_peak[(after_peak.shift(1) >= 70) & (after_peak < 70)]
                if len(cross70_down) == 0:
                    continue
                cross70_date = cross70_down.index[-1]
                days_since   = (rsi.index[-1] - cross70_date).days
                if days_since > days_ago:
                    continue

                current_price = float(df["Close"].iloc[-1])
                prev_price    = float(df["Close"].iloc[-2])
                chg           = (current_price - prev_price) / prev_price * 100
                current_rsi   = float(rsi.iloc[-1])

                results.append({
                    "symbol":        symbol,
                    "name":          name,
                    "current_price": current_price,
                    "price_change_1d": chg,
                    "current_rsi":   current_rsi,
                    "bottom_rsi":    bottom_rsi,
                    "peak_rsi":      peak_rsi,
                    "cross30_date":  str(cross30_date.date()),
                    "cross70_date":  str(cross70_date.date()),
                    "days_since":    days_since,
                    "rsi_series":    rsi,
                    "df":            df,
                })
            except Exception:
                continue

        prog.empty()

        if not results:
            st.warning(f"최근 {days_ago}???�내 RSI ?�이???�성 종목???�습?�다. 기간???�려보세??")
        else:
            results.sort(key=lambda x: x["days_since"])
            st.success(f"??{len(results)}�?종목 발견!")

            c1, c2, c3 = st.columns(3)
            metric_card(c1, "발견 종목", f"{len(results)}�?)
            metric_card(c2, "?�균 ?�재 RSI", f"{sum(r['current_rsi'] for r in results)/len(results):.1f}")
            metric_card(c3, "최근 ?�탈", f"{min(r['days_since'] for r in results)}????)

            st.markdown("<div class='sec-title'>?�� RSI ?�이???�성 종목</div>", unsafe_allow_html=True)

            df_out = pd.DataFrame([{
                "종목�?:    r["name"],
                "종목코드":  r["symbol"],
                "?�재가":    f"??r['current_price']:,.0f}",
                "?�락�?:    f"{'?��' if r['price_change_1d']>0 else '?��'}{r['price_change_1d']:.2f}%",
                "?�재RSI":   round(r["current_rsi"], 1),
                "바닥RSI":   round(r["bottom_rsi"], 1),
                "고점RSI":   round(r["peak_rsi"], 1),
                "30?�파??:  r["cross30_date"],
                "70?�탈??:  r["cross70_date"],
                "경과??:    f"{r['days_since']}??,
            } for r in results])

            st.dataframe(df_out,
                column_config={
                    "?�재RSI": st.column_config.ProgressColumn("?�재RSI", min_value=0, max_value=100, format="%.1f"),
                    "고점RSI": st.column_config.ProgressColumn("고점RSI", min_value=0, max_value=100, format="%.1f"),
                },
                width='stretch', hide_index=True)

            st.markdown("<div class='sec-title'>?�� 종목�?RSI 차트</div>", unsafe_allow_html=True)
            for r in results:
                with st.expander(f"?�� {r['name']} ({r['symbol']}) ???�재 RSI: {r['current_rsi']:.1f} | 70?�탈: {r['cross70_date']}", expanded=True):
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("바닥 RSI", f"{r['bottom_rsi']:.1f}")
                    m2.metric("고점 RSI", f"{r['peak_rsi']:.1f}")
                    m3.metric("?�재 RSI", f"{r['current_rsi']:.1f}")
                    m4.metric("70?�탈 ??, f"{r['days_since']}??)
                    st.plotly_chart(
                        make_rsi_chart(r["rsi_series"], r["df"]),
                        config={"scrollZoom": False, "displayModeBar": False},
                        width='stretch', key=f"rsi_quality_{r['symbol']}")
                    _c4 = make_candle(r["df"], f"{r['name']} ({r['symbol']})")
                    st.plotly_chart(_c4, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":False}, width='stretch', key=f"candle_quality_{r['symbol']}")
                    show_price_levels(_c4)


# ?�?� 최적 급등 ?�?�밍 ?��? ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
elif mode == "?�� 최적 급등 ?�?�밍":

    st.markdown("""
    <div style='background:linear-gradient(135deg,#0d1528,#111827);
         padding:20px 24px;border-radius:14px;margin-bottom:16px;border:1px solid rgba(79,142,247,0.2);'>
      <h3 style='color:#f0f4ff;margin:0;font-size:18px;font-weight:800;'>?�� 최적 급등 ?�?�밍 ?��? ?�스??/h3>
      <p style='color:#8b92a5;margin:8px 0 0;font-size:13px;line-height:1.6;'>
        9가지 ?�심 조건???�시??겹치???�간???�착?�니??<br>
        <b style='color:#ffd700;'>?�너지 축적 ???�력 매집 ??변?�성 ?�축 ???�파 직전</b> ?�턴
      </p>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("?�� 9가지 ?�심 조건 ?�명", expanded=False):
        st.markdown("""
| # | 조건 | ?�수 | ?�명 |
|---|------|------|------|
| 1 | ?�� 충분??조정 ??바닥 | 최�? 4??| 120?? ?�락 조정 ??바닥 ?��?�?(?�너지 축적) |
| 2 | ?�� ?�력 매집 ?�호 | 3??| OBV ?�승 + 가�??�보 (가�????�르?�데 거래??증�?) |
| 3 | ?�� 볼린?�밴드 ?�축 | 3??| BB Width 최�???근처 (??�� 직전 ?�너지 ?�축) |
| 4 | ?�� RSI 바닥 ?�이??| 3??| RSI 30 ?�하 ??30 ?�파 ??50 ?�상 (건강??반등) |
| 5 | ???�평???�배??| 3??| MA5 > MA20 > MA60 ?�서 ?�렬 |
| 6 | ?�� MACD 골든?�로??| 2??| MACD ?�스?�그??0???�향 ?�파 |
| 7 | ?�� ?��??�봉 + 거래??| 3??| ?�균 ?��?2�? 거래?�에 ?�봉 (?�력 진입 ?�인) |
| 8 | ?�� 52�??�고가 ?�파 직전 | 3??| 52�?고점 5% ?�내 (?�??�� ?�파 ?�박) |
| 9 | ?�� 240???�인 ?�파 | 최�? 4??| 가�??�파 ?�음 + 기울�??�상 + ?�이???�음 |
        """)

    def calc_surge_timing_score(symbol):
        """최적 급등 ?�?�밍 종합 ?�수 계산"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="2y")
            if df is None or len(df) < 60:
                return None

            # ?�?� ?�무 ?�터 (급등 ?��??� ?�일 기�?) ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
            try:
                info             = ticker.info
                market_cap       = info.get("marketCap", 0) or 0
                operating_income = info.get("operatingIncome") or 0
                per              = info.get("trailingPE") or info.get("forwardPE") or 0
                revenue_growth   = info.get("revenueGrowth") or None
                earnings_growth  = info.get("earningsGrowth") or None
                if market_cap > 0 and market_cap < 100_000_000_000:
                    return None
                if operating_income != 0 and operating_income < 0:
                    return None
                if per and (per < 0 or per > 200):
                    return None
                if revenue_growth is not None and revenue_growth < -0.05:
                    return None
                if earnings_growth is not None and earnings_growth < -0.30:
                    return None
            except:
                pass

            close = df["Close"]
            high  = df["High"]
            low   = df["Low"]
            vol   = df["Volume"]
            n     = len(close)

            score   = 0
            signals = {}

            # ?�?� ?�동?�균 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
            ma5   = close.rolling(5).mean()
            ma20  = close.rolling(20).mean()
            ma60  = close.rolling(60).mean()
            ma120 = close.rolling(120).mean()
            ma240 = close.rolling(240).mean() if n >= 240 else None

            current = float(close.iloc[-1])
            prev    = float(close.iloc[-2])
            chg     = (current - prev) / prev * 100

            # ?�?� [조건1] 충분??조정 ??바닥 ?��?�??�?�?�?�?�?�?�?�?�?�?�?�?�?�
            # 최근 120???�???��??�재 ?�치 + ?�?�에??반등 �?
            low_120  = float(close.tail(120).min())
            high_120 = float(close.tail(120).max())
            recovery = (current - low_120) / (high_120 - low_120 + 1e-9)
            # ?�?�에??반등 중인 구간 (0~80%)
            signals["recovery_zone"] = 0.10 <= recovery <= 0.50
            signals["recovery_pct"]  = round(recovery * 100, 1)
            if 0.10 <= recovery <= 0.30: score += 4  # 초기 반등 (최적)
            elif 0.30 < recovery <= 0.50: score += 2  # 중간 반등

            # ?�?� [조건2] ?�력 매집 ?�호 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
            # OBV ?�승 + 최근 20??가�?변??< 거래??변??(매집 ?�턴)
            obv = [0]
            for i in range(1, n):
                if close.iloc[i] > close.iloc[i-1]:
                    obv.append(obv[-1] + vol.iloc[i])
                elif close.iloc[i] < close.iloc[i-1]:
                    obv.append(obv[-1] - vol.iloc[i])
                else:
                    obv.append(obv[-1])
            obv_s = pd.Series(obv, index=close.index)

            obv_20_chg   = (float(obv_s.iloc[-1]) - float(obv_s.iloc[-20])) / (abs(float(obv_s.iloc[-20])) + 1e-9)
            price_20_chg = (current - float(close.iloc[-20])) / float(close.iloc[-20])
            # OBV???�르?�데 가격�? ?�보 = 매집
            signals["accumulation"] = obv_20_chg > 0.03 and abs(price_20_chg) < 0.08
            signals["obv_rising"]   = obv_20_chg > 0
            if signals["accumulation"]: score += 3
            elif signals["obv_rising"]: score += 1

            # ?�?� [조건3] 볼린?�밴드 ?�축 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
            bb_std = close.rolling(20).std()
            bb_mid = close.rolling(20).mean()
            bb_w   = (4 * bb_std) / bb_mid.replace(0, np.nan)
            bb_w_min_60 = float(bb_w.tail(60).min())
            bb_w_now    = float(bb_w.iloc[-1])
            bb_w_prev5  = float(bb_w.iloc[-5])
            # ?�재 BB??�� 60??최�???근처 (?�축 �?
            signals["bb_squeeze"]    = bb_w_now <= bb_w_min_60 * 1.2
            # ?�축 ???�장 ?�작
            signals["bb_expanding"]  = bb_w_now > bb_w_prev5 * 1.03
            signals["bb_width"]      = round(bb_w_now, 4)
            if signals["bb_squeeze"] and signals["bb_expanding"]: score += 3
            elif signals["bb_squeeze"]:                           score += 2

            # ?�?� [조건4] RSI 바닥 ?�이???�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
            rsi = calc_rsi_wilder(close, 20)
            cur_rsi = float(rsi.iloc[-1])
            signals["rsi"] = round(cur_rsi, 1)

            # RSI 30 ?�하 ??30 ?�파 ???�재 40~60 (건강???�승 초기)
            rsi_90 = rsi.tail(90).dropna()
            had_below30  = (rsi_90 < 30).any()
            crossed_30   = ((rsi_90.shift(1) <= 30) & (rsi_90 > 30)).any()
            rsi_healthy  = 40 <= cur_rsi <= 65
            signals["rsi_cycle"]   = had_below30 and crossed_30 and rsi_healthy
            signals["rsi_healthy"] = rsi_healthy
            if signals["rsi_cycle"]:   score += 3
            elif rsi_healthy:          score += 1

            # ?�?� [조건5] ?�평???�배???�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
            ma_align_full = (not pd.isna(ma60.iloc[-1]) and
                             float(ma5.iloc[-1]) > float(ma20.iloc[-1]) > float(ma60.iloc[-1]))
            ma_align_forming = (float(ma5.iloc[-1]) > float(ma20.iloc[-1]) and
                                float(ma20.iloc[-1]) > float(ma60.iloc[-1]) * 0.98)
            signals["ma_align"]         = ma_align_full
            signals["ma_align_forming"] = ma_align_forming
            if ma_align_full:    score += 3
            elif ma_align_forming: score += 1

            # ?�?� [조건6] MACD 골든?�로???�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
            macd   = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
            macd_s = macd.ewm(span=9, adjust=False).mean()
            macd_hist = macd - macd_s
            # ?�스?�그??0???�향 ?�파 or 직전 (?�→???�환)
            signals["macd_cross"]    = bool(macd_hist.iloc[-1] > 0 and macd_hist.iloc[-2] <= 0)
            signals["macd_positive"] = bool(macd_hist.iloc[-1] > 0)
            signals["macd_rising"]   = bool(macd_hist.iloc[-1] > macd_hist.iloc[-3])
            if signals["macd_cross"]:    score += 2
            elif signals["macd_rising"] and signals["macd_positive"]: score += 1

            # ?�?� [조건7] ?��??�봉 + 거래??급증 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
            vol_ma20 = vol.rolling(20).mean()
            vol_ratio = float(vol.iloc[-1] / vol_ma20.iloc[-1]) if vol_ma20.iloc[-1] > 0 else 0
            body_ratio = (float(close.iloc[-1]) - float(df["Open"].iloc[-1])) / (float(high.iloc[-1]) - float(low.iloc[-1]) + 1e-9)
            big_bull   = vol_ratio >= 2.0 and body_ratio >= 0.6 and chg > 0
            vol_surge  = vol_ratio >= 1.5
            signals["big_bull_candle"] = big_bull
            signals["vol_surge"]       = vol_surge
            signals["vol_ratio"]       = round(vol_ratio, 2)
            if big_bull:   score += 3
            elif vol_surge: score += 1

            # ?�?� [조건8] 52�??�고가 ?�파 직전 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
            high_52w = float(high.tail(252).max())
            high_ratio = current / high_52w
            near_high  = high_ratio >= 0.92  # 52�?고점 8% ?�내
            at_high    = high_ratio >= 0.98  # ?�파 직전
            signals["near_52w_high"] = near_high
            signals["high_ratio"]    = round(high_ratio * 100, 1)
            if at_high:   score += 3
            elif near_high: score += 2

            # ?�?� 보너?? 240?�선 ?�파 ??근처 + 강화??조건 ?�?�?�?�?�?�?�?�
            if ma240 is not None and not pd.isna(ma240.iloc[-1]):
                ma240_v = float(ma240.iloc[-1])
                ma240_gap = (current - ma240_v) / ma240_v * 100
                signals["ma240_gap"] = round(ma240_gap, 1)

                if 0 <= ma240_gap <= 10:
                    # 가�??�파 방�?: 최근 3???�속 240?????��? ?�인
                    days_above = sum(1 for i in range(-3, 0) if float(close.iloc[i]) > float(ma240.iloc[i]))
                    signals["ma240_confirmed"] = days_above >= 3

                    # 240??기울�? ?�평 ?�는 ?�승 ?�환 중이?�야 ??
                    ma240_slope = (float(ma240.iloc[-1]) - float(ma240.iloc[-20])) / float(ma240.iloc[-20]) * 100 if n >= 20 else 0
                    signals["ma240_slope"] = round(ma240_slope, 2)
                    signals["ma240_healthy_slope"] = ma240_slope >= -1.5

                    # ?�파 ??240???�이???�음 ?�인 (최근 60??기�?)
                    cross_found = False
                    broke_below = False
                    for i in range(n-2, max(n-61, 0), -1):
                        if float(close.iloc[i]) > float(ma240.iloc[i]) and float(close.iloc[i-1]) <= float(ma240.iloc[i-1]):
                            cross_found = True
                            # ?�파 ?�후 ?�이??체크
                            broke_below = any(float(close.iloc[j]) < float(ma240.iloc[j]) for j in range(i+1, n))
                            break
                    signals["ma240_no_rebreak"] = cross_found and not broke_below

                    if signals["ma240_confirmed"] and signals["ma240_healthy_slope"] and signals["ma240_no_rebreak"]:
                        score += 4  # 모든 조건 충족 = 강한 ?�호
                    elif signals["ma240_confirmed"] and signals["ma240_healthy_slope"]:
                        score += 2
                    elif 0 <= ma240_gap <= 10:
                        score += 1
            else:
                signals["ma240_gap"] = None
                signals["ma240_confirmed"] = False
                signals["ma240_no_rebreak"] = False

            return {
                "symbol":        symbol,
                "name":          STOCK_NAMES.get(symbol, symbol),
                "current_price": current,
                "price_change_1d": round(chg, 2),
                "total_score":   score,
                "max_score":     30,  # 만점 ?�데?�트 (240??보너??4??추�?)
                "signals":       signals,
                "rsi":           cur_rsi,
                "rsi_series":    rsi,
                "df":            df,
            }
        except Exception:
            return None

    if st.button("?? 최적 ?�?�밍 ?�캔", type="primary", width='stretch'):
        from stock_surge_detector import ALL_SYMBOLS as SCAN_SYMBOLS
        from concurrent.futures import ThreadPoolExecutor, as_completed

        symbols  = list(dict.fromkeys(SCAN_SYMBOLS))  # 중복 ?�거
        total    = len(symbols)
        results  = []
        completed = [0]

        prog      = st.progress(0)
        prog_text = st.empty()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(calc_surge_timing_score, sym): sym for sym in symbols}
            for future in as_completed(futures):
                completed[0] += 1
                sym = futures[future]
                prog_text.markdown(f"<span style='color:#8b92a5;font-size:13px;'>({completed[0]}/{total}) {sym} 분석 �?..</span>", unsafe_allow_html=True)
                prog.progress(completed[0] / total)
                try:
                    r = future.result()
                    if r and r["total_score"] >= 7:
                        results.append(r)
                except:
                    pass

        prog.empty()
        prog_text.empty()
        results.sort(key=lambda x: x["total_score"], reverse=True)

        if not results:
            st.warning("?�재 조건??충족?�는 종목???�습?�다.")
        else:
            st.success(f"??{len(results)}�?종목 발견!")

            c1, c2, c3, c4 = st.columns(4)
            metric_card(c1, "발견 종목", f"{len(results)}�?)
            metric_card(c2, "최고 ?�수", f"{results[0]['total_score']}??)
            metric_card(c3, "?�균 ?�수", f"{sum(r['total_score'] for r in results)/len(results):.1f}??)
            metric_card(c4, "만점", "30??)

            st.markdown("<div class='sec-title'>?�� 최적 급등 ?�?�밍 TOP 종목</div>", unsafe_allow_html=True)

            rows = []
            for r in results:
                s = r["signals"]
                rows.append({
                    "종목�?:   r["name"],
                    "?�재가":   f"??r['current_price']:,.0f}",
                    "?�락�?:   f"{'?��' if r['price_change_1d']>0 else '?��'}{r['price_change_1d']:.2f}%",
                    "종합?�수": r["total_score"],
                    "RSI":      round(r["rsi"], 1),
                    "거래?�비": f"{s.get('vol_ratio',0):.1f}�?,
                    "반등?�치": f"{s.get('recovery_pct',0):.0f}%",
                    "52주고??: f"{s.get('high_ratio',0):.1f}%",
                    "240??:    "?��" if s.get("ma240_confirmed") and s.get("ma240_no_rebreak") else ("?? if s.get("ma240_gap") is not None and 0 <= (s.get("ma240_gap") or -1) <= 10 else "??),
                    "매집":     "?? if s.get("accumulation") else "??,
                    "BB?�축":   "?? if s.get("bb_squeeze") else "??,
                    "RSI?�이??:"?? if s.get("rsi_cycle") else "??,
                    "?�배??:   "?? if s.get("ma_align") else "??,
                    "MACD":     "?? if s.get("macd_cross") or s.get("macd_positive") else "??,
                    "?��??�봉": "?? if s.get("big_bull_candle") else "??,
                })
            df_tbl = pd.DataFrame(rows)
            st.dataframe(df_tbl,
                column_config={
                    "종합?�수": st.column_config.ProgressColumn(
                        "종합?�수", min_value=0, max_value=30, format="%d??),
                    "240??: st.column_config.TextColumn("240???�인", help="?��=?�전?�인 ??근처 ???�당?�음"),
                },
                width='stretch', hide_index=True)

            # ?�위 종목 ?�세
            st.markdown("<div class='sec-title'>?�� ?�위 종목 ?�세 분석</div>", unsafe_allow_html=True)
            medals = ["gold","silver","bronze"]
            icons  = ["?��","?��","?��"]

            for i, r in enumerate(results[:10]):
                medal = medals[i] if i < 3 else ""
                icon  = icons[i]  if i < 3 else f"{i+1}."
                s     = r["signals"]
                pct   = r["total_score"] / 30 * 100
                color = "#00d4aa" if r["price_change_1d"] > 0 else "#ff4b6e"
                arrow = "?? if r["price_change_1d"] > 0 else "??

                st.markdown(f"""<div class="rank-card {medal}">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                      <span style="font-size:20px;">{icon}</span>
                      <span style="color:#fff;font-size:18px;font-weight:700;margin-left:6px;">{r["name"]}</span>
                      <span style="color:#8b92a5;font-size:13px;margin-left:8px;">{r["symbol"]}</span>
                    </div>
                    <div style="text-align:right;">
                      <span style="color:#fff;font-size:20px;font-weight:700;">??r["current_price"]:,.0f}</span>
                      <span style="color:{color};font-size:14px;margin-left:8px;">{arrow} {abs(r["price_change_1d"]):.2f}%</span>
                    </div>
                  </div>
                  <div style="margin-top:8px;color:#8b92a5;font-size:12px;">
                    RSI {s.get('rsi',0):.1f} | 거래??{s.get('vol_ratio',0):.1f}�?|
                    반등?�치 {s.get('recovery_pct',0):.0f}% | 52주고??{s.get('high_ratio',0):.1f}%
                    {f"| 240??+{s['ma240_gap']:.1f}%" if s.get('ma240_gap') is not None and s['ma240_gap'] >= 0 else ""}
                  </div>
                  <div style="margin-top:8px;">
                    <div style="color:#8b92a5;font-size:11px;margin-bottom:3px;">종합?�수 {r["total_score"]}??/ 30??/div>
                    <div class="bar-bg"><div class="bar-fill" style="width:{pct}%;"></div></div>
                  </div>
                </div>""", unsafe_allow_html=True)

                with st.expander(f"?�� {r['name']} ?�세 ?�호 + 차트", expanded=(i==0)):
                    active, inactive = [], []
                    checks = [
                        (s.get("recovery_zone"),      f"?�� 최적 반등 구간 ({s.get('recovery_pct',0):.0f}%)"),
                        (s.get("accumulation"),        "?�� ?�력 매집 ?�호 (OBV??+ 가격횡�?"),
                        (s.get("obv_rising"),          "?�� OBV ?�승 �?),
                        (s.get("bb_squeeze"),          f"?�� 볼린?�밴드 ?�축 ({s.get('bb_width',0):.4f})"),
                        (s.get("bb_expanding"),        "?�� BB ?�장 ?�작 (??�� 직전)"),
                        (s.get("rsi_cycle"),           f"?�� RSI 바닥 ?�이???�성 ({s.get('rsi',0):.1f})"),
                        (s.get("ma_align"),            "???�평???�전 ?�배??),
                        (s.get("ma_align_forming"),    "???�평???�배???�성 �?),
                        (s.get("macd_cross"),          "?�� MACD 골든?�로??),
                        (s.get("macd_positive"),       "?�� MACD ?�전??),
                        (s.get("big_bull_candle"),     f"?�� ?��??�봉 + 거래??급증 ({s.get('vol_ratio',0):.1f}�?"),
                        (s.get("vol_surge"),           f"?�� 거래??급증 ({s.get('vol_ratio',0):.1f}�?"),
                        (s.get("near_52w_high"),       f"?�� 52�??�고가 직전 ({s.get('high_ratio',0):.1f}%)"),
                        (s.get("ma240_confirmed") and s.get("ma240_no_rebreak"),
                                                       f"?�� 240???�전 ?�인 ?�파 (+{s.get('ma240_gap',0):.1f}%)"),
                        (s.get("ma240_gap") is not None and 0 <= s.get("ma240_gap",999) <= 10 and not s.get("ma240_confirmed"),
                                                       f"?�� 240?�선 근처 (+{s.get('ma240_gap',0):.1f}%)"),
                    ]
                    for flag, label in checks:
                        (active if flag else inactive).append(label)

                    ca, cb = st.columns(2)
                    with ca:
                        st.write("**??충족 ?�호**")
                        for sig in active: st.success(sig)
                    with cb:
                        st.write("**??미충�?*")
                        for sig in inactive[:6]: st.error(sig)

                    cd = r["df"]
                    _c5 = make_candle(cd, f"{r['name']} ({r['symbol']})", show_levels=True)
                    st.plotly_chart(_c5, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":False}, width='stretch', key=f"candle_timing_{r['symbol']}")
                    show_price_levels(_c5)
                    st.plotly_chart(
                        make_rsi_chart(r["rsi_series"], cd),
                        config={"scrollZoom":False,"displayModeBar":False,"staticPlot":False},
                        width='stretch', key=f"rsi_timing_{r['symbol']}")


# ?�?� 즐겨찾기 ???�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
elif mode == "�?즐겨찾기":
    st.markdown("<div class='sec-title'>�?즐겨찾기 종목</div>", unsafe_allow_html=True)

    # ??진입 ??1?�만 localStorage?�서 로드
    if "fav_loaded" not in st.session_state:
        ls_load_from_browser()
        st.session_state["fav_loaded"] = True

    # ?�재 즐겨찾기�?localStorage???�기??
    ls_persist_to_browser()

    favs_dict = ls_get_favorites()

    if not favs_dict:
        st.info("즐겨찾기??종목???�습?�다. 급등 ?��? ??��??종목 카드????버튼???�러 추�??�세??")
    else:
        st.success(f"�?{len(favs_dict)}�?종목 (??기기???�?�됨)")
        for sym, name in list(favs_dict.items()):
            col1, col2 = st.columns([4, 1])
            with col1:
                data_f = get_chart_data(sym, "3mo")
                if data_f is not None and len(data_f) > 1:
                    cur_f  = float(data_f["Close"].iloc[-1])
                    prev_f = float(data_f["Close"].iloc[-2])
                    chg_f  = (cur_f - prev_f) / prev_f * 100
                    color_f = "#00d4aa" if chg_f > 0 else "#ff4b6e"
                    st.markdown(f"""
                    <div style='background:#1a1f35;border-radius:10px;padding:14px 16px;border:1px solid #2d3555;'>
                      <span style='color:#fff;font-weight:700;font-size:16px;'>{name}</span>
                      <span style='color:#8b92a5;font-size:12px;margin-left:8px;'>{sym}</span><br>
                      <span style='color:#fff;font-size:18px;font-weight:700;'>??cur_f:,.0f}</span>
                      <span style='color:{color_f};font-size:13px;margin-left:8px;'>{"?? if chg_f>0 else "??} {abs(chg_f):.2f}%</span>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"**{name}** ({sym})")
            with col2:
                if st.button("?�� ??��", key=f"del_fav_{sym}"):
                    favs_dict.pop(sym, None)
                    ls_save_favorites(favs_dict)
                    st.rerun()
            st.markdown("")

        if st.button("?�� 즐겨찾기 ?�체 차트 보기", type="primary"):
            for sym, name in favs_dict.items():
                cd = get_chart_data(sym, "2y")
                if cd is not None:
                    fig_f = make_candle(cd, f"{name} ({sym})")
                    st.plotly_chart(fig_f, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":False},
                                    width='stretch', key=f"fav_chart_{sym}")
                    show_price_levels(fig_f)

# ?�?� 백테?�트 ???�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
elif mode == "?�� 백테?�트":
    st.markdown("<div class='sec-title'>?�� ?�략 백테?�트 결과</div>", unsafe_allow_html=True)

    st.markdown("""
    <div style='background:#1a1f35;border-radius:12px;padding:16px;border:1px solid #2d3555;margin-bottom:16px;'>
      <div style='color:#e0e6f0;font-size:14px;font-weight:600;margin-bottom:8px;'>?�� 백테?�트 방법�?/div>
      <div style='color:#8b92a5;font-size:13px;line-height:1.8;'>
        ??과거 2???�이?�에???�호 발생 ?�점 ?��?<br>
        ???�호 발생 ??<b style='color:#ffd700;'>20???�익�?/b> 측정<br>
        ??BB?�축+MACD+거래??3�??�트 ?�시 발생 ?�점 기�?<br>
        ???�리?��?/?�수�?미반??(참고??
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ?�호 가중치 ??
    st.markdown("#### ?�호�?가중치 (백테?�팅 기반)")
    try:
        weight_df = pd.DataFrame([
            {"?�호": k, "가중치": v,
             "?�명": {
                "bb_squeeze_expand": "볼린?�밴드 ?�축?�확??(??�� 직전)",
                "vol_price_rising3": "3???�속 거래??가�??�승",
                "ichimoku_bull": "?�목균형???�승 ?�호",
                "ma240_turning_up": "240?�선 ?�락?�상???�환",
                "vol_at_cross": "240???�파 ??거래??급증",
                "ma_align": "?�동?�균???�배??,
                "macd_cross": "MACD 골든?�로??,
                "pullback_recovery": "?�림�??�복",
                "mfi_oversold_recovery": "MFI 과매??반등",
                "near_52w_high": "52�??�고가 근처",
             }.get(k, k)}
            for k, v in sorted(SIGNAL_WEIGHTS.items(), key=lambda x: -x[1])
        ])
        st.dataframe(weight_df,
            column_config={
                "가중치": st.column_config.ProgressColumn("가중치", min_value=0, max_value=2.5, format="%.1f")
            },
            width='stretch', hide_index=True)
    except:
        st.warning("백테?�트 모듈??불러?????�습?�다.")

    st.markdown("---")
    st.markdown("#### 종목�?백테?�트 ?�행")
    st.caption("?�택 종목??과거 ?�호 발생 ?�점 ??20?????�균 ?�익�?계산")

    bt_col1, bt_col2 = st.columns([3, 2])
    with bt_col1:
        bt_query = st.text_input("?�� 종목�?검??(KRX ?�체)", placeholder="?? ?�리기술, ?�성?�자, ?�테?�젠...", key="bt_search")
    with bt_col2:
        bt_direct = st.text_input("직접 ?�력 (종목코드)", placeholder="?? 041190.KQ", key="bt_direct")

    bt_sym  = None
    bt_name = ""

    if bt_direct.strip():
        bt_sym  = bt_direct.strip()
        bt_name = bt_sym
        st.info(f"직접 ?�력: {bt_sym}")
    elif bt_query.strip():
        bt_matches = search_stock_by_name(bt_query.strip())
        if bt_matches:
            bt_opts2 = [f"{v} ({k})" for k, v in bt_matches]
            bt_sel2  = st.selectbox("검??결과", bt_opts2, key="bt_symbol2")
            bt_sym   = bt_sel2.split("(")[-1].replace(")", "").strip()
            bt_name  = bt_sel2.split("(")[0].strip()
        else:
            st.warning(f"'{bt_query}' 검??결과 ?�음. 종목코드�?직접 ?�력?�보?�요.")
    else:
        from stock_surge_detector import STOCK_NAMES as DET_NAMES
        all_bt = {**STOCK_NAMES, **DET_NAMES}
        bt_opts = [f"{v} ({k})" for k, v in sorted(all_bt.items(), key=lambda x: x[1])]
        bt_sel  = st.selectbox("종목 ?�택", bt_opts, key="bt_symbol")
        bt_sym  = bt_sel.split("(")[-1].replace(")", "").strip()
        bt_name = bt_sel.split("(")[0].strip()

    if bt_sym and st.button("?�� 백테?�트 ?�행", type="primary"):
        with st.spinner(f"{bt_name} 백테?�트 �?.. (1~2�??�요)"):
            try:
                bt_result = backtest_signal(bt_sym)
            except:
                bt_result = None

        if bt_result is None:
            st.warning("?�이??부�??�는 ?�호 발생 ?�력 ?�음")
        else:
            avg_ret  = bt_result["avg_ret"]
            win_rate = bt_result["win_rate"]
            trades   = bt_result["trades"]
            hold_d   = bt_result["hold_days"]
            color_bt = "#00d4aa" if avg_ret > 0 else "#ff4b6e"
            grade    = "?�� 강력" if avg_ret > 10 else "???�호" if avg_ret > 3 else "?�️ 보통" if avg_ret > 0 else "??주의"

            c1, c2, c3, c4 = st.columns(4)
            c1.metric(f"{hold_d}???�균 ?�익�?, f"{avg_ret:+.2f}%")
            c2.metric("?�률", f"{win_rate:.1f}%")
            c3.metric("?�호 발생 ?�수", f"{trades}??)
            c4.metric("?�략 ?�급", grade)

            st.markdown(f"""
            <div style='background:#1a1f35;border-radius:12px;padding:20px;border:1px solid {color_bt};margin-top:12px;text-align:center;'>
              <div style='color:#8b92a5;font-size:13px;'>???�체 ?�호(10�? 가중치 ?�산 기�? | {hold_d}?????�균 ?�익�?/div>
              <div style='color:{color_bt};font-size:48px;font-weight:800;margin:12px 0;'>{avg_ret:+.2f}%</div>
              <div style='color:#8b92a5;font-size:12px;'>과거 2???�이??기�? | ?�리?��? 미반??| 5??간격 ?�플�?/div>
            </div>
            """, unsafe_allow_html=True)

            # ?�호�?기여??
            if bt_result.get("sig_contrib"):
                st.markdown("#### ?�호�??�균 ?�익�?기여??)
                contrib_df = pd.DataFrame([
                    {"?�호": k, "?�균?�익�?: v,
                     "발생?�수": bt_result["sig_contrib"].get(k, 0)}
                    for k, v in sorted(bt_result["sig_contrib"].items(), key=lambda x: -x[1])
                ])
                st.dataframe(contrib_df,
                    column_config={
                        "?�균?�익�?: st.column_config.NumberColumn("?�균?�익�?%)", format="%.2f")
                    },
                    width='stretch', hide_index=True)

    # 과거 ?�캔 결과 ?�스?�리
    st.markdown("---")
    st.markdown("#### ?�� 과거 ?�캔 결과 ?�스?�리")
    try:
        scan_dates = list_scan_dates()
        if not scan_dates:
            st.info("?�?�된 ?�캔 결과가 ?�습?�다. 급등 ?��? ??��???�캔???�행?�면 ?�동 ?�?�됩?�다.")
        else:
            date_opts = [d["date"] for d in scan_dates]
            sel_date  = st.selectbox("?�짜 ?�택", date_opts)
            cached    = load_scan(sel_date)
            if cached:
                st.success(f"{sel_date} ??{len(cached)}�?종목")
                hist_df = pd.DataFrame([{
                    "종목�?: r.get("name",""),
                    "종목코드": r.get("symbol",""),
                    "?�재가": f"??r.get('current_price',0):,.0f}",
                    "240?�이�?: f"+{r.get('ma240_gap',0):.1f}%",
                    "조정기간": f"{r.get('below_days',0)}??,
                    "종합?�수": r.get("total_score", 0),
                } for r in cached])
                st.dataframe(hist_df, width='stretch', hide_index=True)
    except:
        st.info("?�스?�리 기능???�용?�려�?먼�? ?�캔???�행?�세??")

# ?�?� ?�과 추적 ???�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
elif mode == "?�� ?�과 추적":
    st.markdown("<div class='sec-title'>?�� ?�림 종목 ?�과 추적</div>", unsafe_allow_html=True)

    try:
        from cache_db import get_alert_history, get_performance_summary, update_alert_status

        col_refresh, col_empty = st.columns([1, 4])
        with col_refresh:
            if st.button("?�� ?�태 ?�데?�트", type="primary", width='stretch'):
                with st.spinner("?�재가 ?�인 �?.."):
                    update_alert_status()
                st.success("?�데?�트 ?�료!")
                st.rerun()

        # ?�?� ?�과 ?�약 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
        perf = get_performance_summary()
        if perf["total"] > 0:
            c1, c2, c3, c4, c5 = st.columns(5)
            metric_card(c1, "�?�� 종목", f"{perf['total']}�?)
            metric_card(c2, "목표가 ?�성", f"{perf['win']}�?)
            metric_card(c3, "?�절 발생", f"{perf['loss']}�?)
            win_color = "#00d4aa" if perf['win_rate'] >= 50 else "#ff3355"
            c4.markdown(f"""<div class='metric-card'>
              <div class='lbl'>?�률</div>
              <div class='val' style='color:{win_color};'>{perf['win_rate']}%</div>
            </div>""", unsafe_allow_html=True)
            ret_color = "#00d4aa" if perf['avg_return'] >= 0 else "#ff3355"
            c5.markdown(f"""<div class='metric-card'>
              <div class='lbl'>?�균 ?�익�?/div>
              <div class='val' style='color:{ret_color};'>{perf['avg_return']:+.1f}%</div>
            </div>""", unsafe_allow_html=True)

            if perf['win'] > 0 or perf['loss'] > 0:
                st.markdown(f"""<div class='cond-box' style='margin-top:8px;'>
                  ?�균 ?�익: <b style='color:#00d4aa;'>{perf['avg_win']:+.1f}%</b> &nbsp;|&nbsp;
                  ?�균 ?�실: <b style='color:#ff3355;'>{perf['avg_loss']:+.1f}%</b> &nbsp;|&nbsp;
                  진입 모니?�링: <b style='color:#4f8ef7;'>{perf.get('active',0)}�?/b> &nbsp;|&nbsp;
                  매수가 ?��? <b style='color:#8b92a5;'>{perf.get('pending',0)}�?/b> &nbsp;|&nbsp;
                  만료: <b style='color:#8b92a5;'>{perf['expired']}�?/b>
                </div>""", unsafe_allow_html=True)

            # ?�?� ?�익�?곡선 차트 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
            history_all = get_alert_history(200)
            closed = [h for h in history_all if h["status"] in ("hit_target","hit_stop") and h["return_pct"] is not None and h["exit_date"]]
            if len(closed) >= 2:
                closed_sorted = sorted(closed, key=lambda x: x["exit_date"])
                cumulative = 0
                dates, cum_rets, colors, names = [], [], [], []
                for h in closed_sorted:
                    cumulative += h["return_pct"]
                    dates.append(h["exit_date"])
                    cum_rets.append(round(cumulative, 2))
                    colors.append("#00d4aa" if h["return_pct"] > 0 else "#ff3355")
                    names.append(h["name"])

                fig_perf = go.Figure()
                fig_perf.add_trace(go.Scatter(
                    x=dates, y=cum_rets,
                    mode="lines+markers",
                    line=dict(color="#4f8ef7", width=2),
                    marker=dict(color=colors, size=8),
                    text=names,
                    hovertemplate="%{text}<br>?�적: %{y:+.1f}%<extra></extra>",
                    fill="tozeroy",
                    fillcolor="rgba(79,142,247,0.08)"
                ))
                fig_perf.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.2)")
                fig_perf.update_layout(
                    title="?�적 ?�익�?곡선",
                    paper_bgcolor="#0f1628", plot_bgcolor="#0f1628",
                    font=dict(color="#8b92a5"),
                    height=280, margin=dict(l=0,r=0,t=40,b=0),
                    xaxis=dict(gridcolor="#1e2540"),
                    yaxis=dict(gridcolor="#1e2540", ticksuffix="%"),
                )
                st.plotly_chart(fig_perf, width='stretch')
        else:
            st.info("?�직 ?�과 ?�이?��? ?�어?? ?�레그램 ?�림??발송?�면 ?�동?�로 기록?�니??")

        # ?�?� ?�세 ?�역 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
        history = get_alert_history(100)
        if history:
            st.markdown("<div class='sec-title'>?�� ?�림 ?�역</div>", unsafe_allow_html=True)

            status_filter = st.selectbox("?�태 ?�터", ["?�체", "매수?��?, "진입�?, "목표?�성", "?�절", "만료"], key="perf_filter")
            status_map = {"?�체": None, "매수?��?: "pending", "진입�?: "active", "목표?�성": "hit_target", "?�절": "hit_stop", "만료": "expired"}
            filtered = [h for h in history if status_map[status_filter] is None or h["status"] == status_map[status_filter]]

            rows = []
            for h in filtered:
                status_emoji = {"pending": "??매수?��?, "active": "?�� 진입�?, "hit_target": "??목표?�성", "hit_stop": "?�� ?�절", "expired": "??만료"}.get(h["status"], h["status"])
                ret_str = f"{h['return_pct']:+.1f}%" if h["return_pct"] is not None else "-"
                ret_color_str = "?��" if (h["return_pct"] or 0) > 0 else "?��" if (h["return_pct"] or 0) < 0 else "??
                rows.append({
                    "?�짜":    h["alert_date"],
                    "종목�?:  h["name"],
                    "?�수":    h["score"],
                    "매수가":  f"??h['entry_price']:,.0f}" if h["entry_price"] else "-",
                    "목표가":  f"??h['target_price']:,.0f}" if h["target_price"] else "-",
                    "?�절가":  f"??h['stop_price']:,.0f}" if h["stop_price"] else "-",
                    "?�익�?:  f"{h['rr_ratio']:.1f}:1" if h["rr_ratio"] else "-",
                    "?�태":    status_emoji,
                    "?�익�?:  f"{ret_color_str} {ret_str}",
                    "�?��??:  h["exit_date"] or "-",
                })
            st.dataframe(pd.DataFrame(rows),
                column_config={
                    "?�수": st.column_config.ProgressColumn("?�수", min_value=0, max_value=50, format="%d??),
                },
                width='stretch', hide_index=True)
        else:
            st.info("?�림 ?�역???�습?�다.")

    except Exception as e:
        st.error(f"?�과 추적 ?�류: {e}")

# ?�?� ?�단 면책조항 ?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�?�
st.markdown("---")

# ?�레그램 ?�림 ?�이?�바 버튼
with st.sidebar:
    st.markdown("---")
    st.markdown("### ?�� ?�레그램 ?�림")
    if st.button("?�� 지�??�림 ?�송", width='stretch'):
        try:
            from telegram_alert import send_scan_alert, send_test_alert
            scan_res = st.session_state.get("scan_results", [])
            if scan_res:
                send_scan_alert(scan_res)
                st.success("???�레그램 ?�송 ?�료!")
            else:
                st.warning("?�캔 결과가 ?�어?? 먼�? ?�캔???�행?�세??")
        except Exception as e:
            st.error(f"?�송 ?�패: {e}")
    if st.button("?�� ?�결 ?�스??, width='stretch'):
        try:
            from telegram_alert import send_test_alert
            ok = send_test_alert()
            st.success("???�결 ?�공!" if ok else "???�송 ?�패")
        except Exception as e:
            st.error(f"?�류: {e}")
st.markdown("""
<div style='text-align:center;color:#555;font-size:11px;padding:10px 0 20px;'>
?�️ �??�비?�는 ?�자 참고???�보 ?�공 목적?�며, ?�자 권유가 ?�닙?�다.<br>
주식 ?�자???�금 ?�실 ?�험???�으�? 모든 ?�자 결정�?책임?� ?�자??본인?�게 ?�습?�다.
</div>
""", unsafe_allow_html=True)
