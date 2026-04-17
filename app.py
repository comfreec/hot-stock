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
                          is_favorite)
    from backtest_ml import backtest_signal, SIGNAL_WEIGHTS
    from streamlit_javascript import st_javascript
except Exception as e:
    st.warning(f"캐시/백테스트 모듈 로드 실패: {e}")

# ── 접근 제어 ────────────────────────────────────────────────────
try:
    PASSWORDS = list(st.secrets.get("PASSWORDS", ["hotstock2026", "vip1234", "comfreec"]))
except Exception:
    PASSWORDS = ["hotstock2026", "vip1234", "comfreec"]

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.markdown("""
    <style>
    @keyframes fadein { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }
    @keyframes radar_spin {
        0%   { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    @keyframes radar_pulse {
        0%,100% { box-shadow: 0 0 0 0 rgba(0,212,170,0.4), 0 0 20px rgba(79,142,247,0.3); }
        50%      { box-shadow: 0 0 0 16px rgba(0,212,170,0), 0 0 40px rgba(79,142,247,0.6); }
    }
    .login-box { animation: fadein 0.6s ease; }
    .radar-wrap {
        width:96px;height:96px;border-radius:50%;
        background:linear-gradient(135deg,#0d1528,#1a2540);
        border:2px solid #4f8ef7;
        display:flex;align-items:center;justify-content:center;
        margin:0 auto 16px;
        animation: radar_pulse 2s ease-in-out infinite;
        position:relative;overflow:hidden;
    }
    .radar-sweep {
        position:absolute;width:50%;height:50%;top:0;left:50%;
        transform-origin:bottom left;
        background:linear-gradient(135deg,rgba(0,212,170,0.6),transparent);
        animation:radar_spin 2s linear infinite;
        border-radius:100% 0 0 0;
    }
    .radar-icon { font-size:44px;z-index:1;position:relative; }
    </style>
    <div class='login-box' style='max-width:420px;margin:30px auto;'>
      <div style='background:linear-gradient(135deg,#1a1f35,#0e1117);
           padding:48px 40px;border-radius:20px;border:1px solid #2d3555;
           box-shadow:0 20px 60px rgba(0,0,0,0.5);text-align:center;'>
        <div class='radar-wrap'>
          <div class='radar-sweep'></div>
          <div class='radar-icon'>📡</div>
        </div>
        <div style='
            display:inline-block;
            padding:8px 20px;
            border-radius:10px;
            background:linear-gradient(135deg,rgba(79,142,247,0.12),rgba(0,212,170,0.12));
            border:none;
            box-shadow:0 0 24px rgba(0,212,170,0.25), 0 0 48px rgba(79,142,247,0.15);
            margin:8px auto 2px;
            text-align:center;
        '>
          <h2 style='
              margin:0;
              font-size:32px;
              font-weight:900;
              letter-spacing:8px;
              background:linear-gradient(90deg,#4f8ef7 0%,#00d4aa 50%,#4f8ef7 100%);
              -webkit-background-clip:text;
              -webkit-text-fill-color:transparent;
              background-clip:text;
          '>J.A.R.V.I.S.</h2>
        </div>
        <p style='color:#6b7280;font-size:11px;margin:4px 0 4px;font-weight:500;letter-spacing:5px;text-transform:uppercase;'>SWING RADAR</p>
        <p style='color:#4f8ef7;font-size:11px;margin:0 0 28px;font-weight:500;letter-spacing:2px;'>SWING RADAR SYSTEM</p>
        <div style='width:40px;height:2px;background:linear-gradient(90deg,#4f8ef7,#00d4aa);margin:0 auto 28px;border-radius:2px;'></div>
        <p style='color:#8b92a5;font-size:13px;margin:0 0 24px;'>허가된 사용자만 접근 가능합니다</p>
      </div>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        pw = st.text_input("", type="password", placeholder="🔑  비밀번호 입력", label_visibility="collapsed")
        if st.button("로그인", type="primary", width='stretch'):
            if pw in PASSWORDS:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다")
    st.stop()

STOCK_NAMES = {
    "005930.KS":"삼성전자","000660.KS":"SK하이닉스","035420.KS":"NAVER",
    "051910.KS":"LG화학","006400.KS":"삼성SDI","035720.KS":"카카오",
    "207940.KS":"삼성바이오","068270.KS":"셀트리온","323410.KS":"카카오뱅크",
    "373220.KS":"LG에너지솔루션","005380.KS":"현대차","000270.KS":"기아",
    "105560.KS":"KB금융","055550.KS":"신한지주","012330.KS":"현대모비스",
    "028260.KS":"삼성물산","066570.KS":"LG전자","003550.KS":"LG",
    "017670.KS":"SK텔레콤","030200.KS":"KT","196170.KQ":"알테오젠",
    "263750.KQ":"펄어비스","293490.KQ":"카카오게임즈","112040.KQ":"위메이드",
    "357780.KQ":"솔브레인","086900.KQ":"메디톡스","214150.KQ":"클래시스",
    "950140.KQ":"잉글우드랩","145020.KQ":"휴젤","041510.KQ":"에스엠",
    "247540.KQ":"에코프로비엠",
    "000100.KS":"유한양행",
    "001040.KS":"CJ",
    "002380.KS":"KCC",
    "003490.KS":"대한항공",
    "004020.KS":"현대제철",
    "005490.KS":"POSCO홀딩스",
    "007070.KS":"GS리테일",
    "010130.KS":"고려아연",
    "010950.KS":"S-Oil",
    "011070.KS":"LG이노텍",
    "011200.KS":"HMM",
    "016360.KS":"삼성증권",
    "018260.KS":"삼성에스디에스",
    "021240.KS":"코웨이",
    "023530.KS":"롯데쇼핑",
    "024110.KS":"기업은행",
    "029780.KS":"삼성카드",
    "032640.KS":"LG유플러스",
    "033780.KS":"KT&G",
    "034020.KS":"두산에너빌리티",
    "034220.KS":"LG디스플레이",
    "036460.KS":"한국가스공사",
    "036570.KS":"엔씨소프트",
    "042660.KS":"한화오션",
    "047050.KS":"포스코인터내셔널",
    "051600.KS":"한전KPS",
    "060980.KS":"한세실업",
    "064350.KS":"현대로템",
    "071050.KS":"한국금융지주",
    "078930.KS":"GS",
    "086280.KS":"현대글로비스",
    "090430.KS":"아모레퍼시픽",
    "096770.KS":"SK이노베이션",
    "097950.KS":"CJ제일제당",
    "100840.KS":"SNT모티브",
    "161390.KS":"한국타이어앤테크놀로지",
    "175330.KS":"JB금융지주",
    "180640.KS":"한진칼",
    "192400.KS":"쿠쿠홀딩스",
    "204320.KS":"HL만도",
    "267250.KS":"HD현대",
    "316140.KS":"우리금융지주",
    "326030.KS":"SK바이오팜",
    "329180.KS":"HD현대중공업",
    "336260.KS":"두산밥캣",
    "035900.KQ":"JYP엔터",
    "036030.KQ":"YG엔터테인먼트",
    "039030.KQ":"이오테크닉스",
    "041960.KQ":"블루콤",
    "045390.KQ":"대아티아이",
    "048260.KQ":"오스템임플란트",
    "053800.KQ":"안랩",
    "058470.KQ":"리노공업",
    "060310.KQ":"3S",
    "064760.KQ":"티씨케이",
    "066970.KQ":"엘앤에프",
    "067160.KQ":"아프리카TV",
    "068760.KQ":"셀트리온제약",
    "078600.KQ":"대주전자재료",
    "086520.KQ":"에코프로",
    "091580.KQ":"상아프론테크",
    "095340.KQ":"ISC",
    "096530.KQ":"씨젠",
    "101490.KQ":"에스앤에스텍",
    "108320.KQ":"LX세미콘",
    "122870.KQ":"와이지-원",
    "131970.KQ":"두산테스나",
    "137310.KQ":"에스디바이오센서",
    "141080.KQ":"레고켐바이오",
    "155900.KQ":"바텍",
    "166090.KQ":"하나머티리얼즈",
    "183300.KQ":"코미코",
    "200130.KQ":"콜마비앤에이치",
    "206650.KQ":"유바이오로직스",
    "214370.KQ":"케어젠",
    "236200.KQ":"슈프리마",
    "237690.KQ":"에스티팜",
    "251270.KQ":"넷마블",
    "253450.KQ":"스튜디오드래곤",
    "256840.KQ":"한국비엔씨",
    "270210.KQ":"에스알바이오텍",
    "277810.KQ":"레인보우로보틱스",
    "290650.KQ":"엔씨소프트",
    "298380.KQ":"에이비엘바이오",
    "302440.KQ":"SK바이오사이언스",
}

st.set_page_config(page_title="J.A.R.V.I.S. 스윙레이더", page_icon="🎯", layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
/* ── 뷰포트 & 기본 ── */
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

/* ── 배경 ── */
.stApp { background: #080c14 !important; }
.main { background: #080c14 !important; }

/* ── 헤더 ── */
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

/* ── 메트릭 카드 ── */
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

/* ── 종목 카드 ── */
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

/* ── 진행 바 ── */
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

/* ── 섹션 타이틀 ── */
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

/* ── 조건 박스 ── */
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

/* ── 버튼 ── */
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

/* ── 슬라이더 ── */
.stSlider > div > div > div > div {
    background: linear-gradient(90deg, #4f8ef7, #00d4aa) !important;
}

/* ── 데이터프레임 ── */
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

/* ── 성공/에러/인포 박스 ── */
.stSuccess { background: rgba(0,212,170,0.08) !important; border: 1px solid rgba(0,212,170,0.25) !important; border-radius: 10px !important; }
.stWarning { background: rgba(255,193,7,0.08) !important; border: 1px solid rgba(255,193,7,0.25) !important; border-radius: 10px !important; }
.stInfo    { background: rgba(79,142,247,0.08) !important; border: 1px solid rgba(79,142,247,0.25) !important; border-radius: 10px !important; }
.stError   { background: rgba(255,51,85,0.08)  !important; border: 1px solid rgba(255,51,85,0.25)  !important; border-radius: 10px !important; }

/* ── 차트 터치 ── */
.js-plotly-plot, .plotly, .plot-container { touch-action: pan-y !important; }
.stPlotlyChart { touch-action: pan-y !important; }

/* ── 시장 현황 카드 ── */
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

/* ── 스크롤바 ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #2d3555; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #4f8ef7; }

/* ── 모바일 ── */
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

/* ── 태블릿 ── */
@media (max-width: 1024px) and (min-width: 769px) {
    .metric-card .val { font-size: 18px !important; }
    .main .block-container { padding: 0.4rem 0.6rem !important; }
}

/* ── 차트 터치 스크롤 (모바일) ── */
.js-plotly-plot, .plotly, .plot-container { touch-action: pan-y !important; }
.stPlotlyChart { touch-action: pan-y !important; }
.stPlotlyChart > div { touch-action: pan-y !important; }
</style>""", unsafe_allow_html=True)

# 모바일 뒤로가기 방지 + 차트 터치 스크롤 JS
st.markdown("""
<script>
// 뒤로가기로 로그인 화면 노출 방지
history.pushState(null, '', location.href);
window.addEventListener('popstate', function() {
  history.pushState(null, '', location.href);
});

(function() {
  function fixChartTouch() {
    var charts = document.querySelectorAll('.js-plotly-plot, .stPlotlyChart, .plot-container');
    charts.forEach(function(el) {
      el.style.touchAction = 'pan-y';
      var layers = el.querySelectorAll('svg, canvas, .nsewdrag, .drag');
      layers.forEach(function(layer) {
        layer.style.touchAction = 'pan-y';
        layer.addEventListener('touchstart', function(e) {
          if (e.touches.length === 1) { e.stopPropagation(); }
        }, {passive: true});
        layer.addEventListener('touchmove', function(e) {
          if (e.touches.length === 1) {
            e.stopPropagation();
            window.scrollBy(0, -e.touches[0].clientY + (this._lastY || e.touches[0].clientY));
            this._lastY = e.touches[0].clientY;
          }
        }, {passive: true});
        layer.addEventListener('touchend', function() { this._lastY = null; }, {passive: true});
      });
    });
  }
  // 초기 실행 + DOM 변경 감지
  setTimeout(fixChartTouch, 1000);
  setTimeout(fixChartTouch, 3000);
  var observer = new MutationObserver(function() { setTimeout(fixChartTouch, 500); });
  observer.observe(document.body, {childList: true, subtree: true});
})();
</script>
""", unsafe_allow_html=True)



st.markdown("""<div class="top-header">
  <div style="display:flex;align-items:center;gap:12px;">
    <span style="font-size:36px;">🎯</span>
    <div>
      <h1 style="color:#f0f4ff;margin:0;font-size:clamp(18px,4vw,28px);font-weight:800;letter-spacing:-0.5px;">J.A.R.V.I.S. 스윙레이더</h1>
      <p style="color:#4f8ef7;margin:4px 0 0;font-size:12px;font-weight:600;letter-spacing:2px;text-transform:uppercase;">Swing Radar — 240/1000 Golden Cross Strategy</p>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

# ── 상단 시장 현황 ────────────────────────────────────────────────
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
    """공포/탐욕 지수 - KOSPI 20일 변동성 기반 자체 계산"""
    try:
        df = yf.Ticker("^KS11").history(period="3mo")
        close = df["Close"]
        ret = close.pct_change().dropna()
        vol = float(ret.tail(20).std() * 100)
        rsi_val = float(calc_rsi_wilder(close, 14).iloc[-1])
        ma20 = float(close.rolling(20).mean().iloc[-1])
        cur = float(close.iloc[-1])
        momentum = (cur - ma20) / ma20 * 100
        # 점수 계산 (0~100)
        score = 50
        score -= (vol - 1.0) * 10   # 변동성 높으면 공포
        score += momentum * 2        # 모멘텀 좋으면 탐욕
        score += (rsi_val - 50) * 0.5
        score = max(0, min(100, score))
        if score >= 75:   label, color = "극도의 탐욕", "#ff3355"
        elif score >= 55: label, color = "탐욕", "#ff8c42"
        elif score >= 45: label, color = "중립", "#ffd700"
        elif score >= 25: label, color = "공포", "#4f8ef7"
        else:             label, color = "극도의 공포", "#00d4aa"
        return int(score), label, color
    except:
        return None, None, None

@st.cache_data(ttl=300)
def get_sparkline(symbol):
    """최근 20일 스파크라인 데이터"""
    try:
        df = yf.Ticker(symbol).history(period="1mo")
        return df["Close"].tail(20).tolist()
    except:
        return []

def make_sparkline(prices, color):
    """미니 스파크라인 SVG"""
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
    """네이버 금융에서 실시간(1~2분 지연) 현재가 가져오기"""
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
    """종목 최신 뉴스 1건"""
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


    """종목 최신 뉴스 1건"""
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
    arrow = "▲" if chg > 0 else "▼"
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
      <div style='color:#6b7280;font-size:10px;font-weight:600;letter-spacing:1px;text-transform:uppercase;'>공포/탐욕</div>
      <div style='color:{fear_color};font-size:20px;font-weight:800;margin:4px 0;'>{fear_score}</div>
      <div style='color:{fear_color};font-size:12px;font-weight:600;'>{fear_label}</div>
      <div style='background:rgba(255,255,255,0.06);border-radius:4px;height:3px;margin-top:6px;'>
        <div style='background:{bar_color};width:{bar_w}%;height:3px;border-radius:4px;box-shadow:0 0 6px {bar_color};'></div>
      </div>
    </div>""", unsafe_allow_html=True)

cols_m[3].markdown(f"""
    <div class='market-card' style='text-align:right;'>
      <div style='color:#6b7280;font-size:10px;font-weight:600;letter-spacing:1px;text-transform:uppercase;'>기준시각 (1~2분 지연)</div>
      <div style='color:#e8edf8;font-size:17px;font-weight:700;margin-top:6px;letter-spacing:-0.3px;'>{now}</div>
      <div style='color:#3d4466;font-size:11px;margin-top:4px;'>KST</div>
    </div>""", unsafe_allow_html=True)

# ── 상단 메뉴 탭 ─────────────────────────────────────────────────
if "mode" not in st.session_state:
    st.session_state["mode"] = "🔍 급등 예고 종목 탐지"

tab_labels = ["🔍 급등 예고 종목 탐지", "🎯 최적 급등 타이밍", "📈 개별 종목 분석", "⭐ 즐겨찾기", "📊 백테스트", "📈 성과 추적"]
tab_cols = st.columns(6)
for i, (col, label) in enumerate(zip(tab_cols, tab_labels)):
    active = st.session_state["mode"] == label
    if col.button(label, key=f"tab_{i}", width='stretch',
                  type="primary" if active else "secondary"):
        st.session_state["mode"] = label
        if label == "⭐ 즐겨찾기":
            st.session_state.pop("fav_loaded", None)  # 탭 진입 시 재로드
        st.rerun()

mode = st.session_state["mode"]
st.markdown("---")

# ── 사이드바: 조건 설정 ──────────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.markdown("### ⚙️ 스캔 조건")

    if "max_gap"   not in st.session_state: st.session_state["max_gap"]   = 10
    if "ob_days"   not in st.session_state: st.session_state["ob_days"]   = 90
    if "min_score" not in st.session_state: st.session_state["min_score"] = 15

    if st.button("⚡ 기본 셋팅", width='stretch'):
        st.session_state["max_gap"]   = 10
        st.session_state["ob_days"]   = 90
        st.session_state["min_score"] = 15
        st.rerun()

    max_gap   = st.slider("📍 240선 근처 범위 (%)", 1, 30, key="max_gap",
        help="현재가가 240일선 위 몇 % 이내인지")
    ob_days   = st.slider("⏱ RSI 70 이탈 후 경과일", 30, 180, key="ob_days",
        help="RSI 70 이탈 후 최대 경과일 (짧을수록 최근 눌림목)")
    min_score = st.slider("🎯 최소 종합점수", 0, 40, key="min_score",
        help="0=전체, 높을수록 엄격")

    # ── 과거 날짜 스캔 ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📅 과거 날짜 스캔")
    use_past_date = st.checkbox("과거 날짜 기준으로 스캔", value=False,
        help="체크하면 선택한 날짜 기준으로 백테스트 스캔")
    from datetime import date as _date, timedelta as _td
    scan_date = None
    if use_past_date:
        scan_date = st.date_input(
            "스캔 기준일",
            value=_date.today() - _td(days=30),
            min_value=_date(2020, 1, 1),
            max_value=_date.today() - _td(days=1),
            help="해당 날짜까지의 데이터만 사용해서 스캔"
        )
        st.info(f"📅 {scan_date} 기준으로 스캔합니다")

    st.markdown("---")
    st.markdown("""**📋 탐지 전략**
> RSI(20) 과매도 탈출 → 240선 돌파 → 과매수 → 조정 눌림목

| 조건 | 기준 |
|------|------|
| 📉 RSI 30 이하 탈출 | 과매도 구간 탈출 |
| 📈 240일선 상향 돌파 | 추세 전환 확인 |
| 🔥 RSI 70 이상 도달 | 과매수 확인 |
| 📉 RSI 70 이탈 | 조정 시작 |
| 📍 현재 RSI 55 이하 | 눌림목 진행 중 |
| 📍 현재가 240선 위 | 0~N% 이내 |
| 🛑 손절가 | 240선 -5% |

**📊 가산점 신호**
| 신호 | 점수 |
|------|------|
| 🚀 돌파 시 거래량 폭발(3배+) | 4점 |
| 📦 돌파 시 거래량 급증(2배+) | 3점 |
| 📊 돌파 전후 거래량 지속 | 2점 |
| 📊 최근 거래량 증가 | 2점 |
| 🔥 기관+외국인 동시 순매수 | 4점 |
| ✅ 기관 또는 외국인 순매수 | 2점 |
| 📈 OBV 지속 상승 | 2점 |
| ⚡ 이평선 정배열 | 3점 |
| 🔄 눌림목 후 재상승 | 2점 |
| 💚 RSI 건강 구간 | 2점 |
| 🔥 BB수축→확장 | 3점 |
| 📊 MACD 크로스 | 2점 |
| 🔼 240선 상승 전환 | 3점 |
| 💰 MFI 과매도 반등 | 2점 |
| 📉 스토캐스틱 크로스 | 2점 |
| 💪 ADX 강한 추세 | 2점 |
| 📍 VWAP 위 | 2점 |
| ☁️ 일목균형표 돌파 | 3점 |
| 🏆 52주 신고가 근처 | 2점 |
| 📈 상승장 가산 | 2점 |
| 🔥 섹터 강세 | 최대 3점 |
| 🔗 동종 섹터 동반 상승 | 최대 3점 |
| 📦 3일 연속 거래량+가격 | 3점 |
| 🎯 얕은 눌림목(3~15%) | 3점 |
| 🕵️ 세력 매집 감지 | 3점 |
| 🎯 눌림목 반등 | 3점 |
| 🕯 캔들 패턴 | 1~2점 |
| ⏳ 조정 기간 가산 | 1~3점 |
| 📰 긍정 뉴스 | 1~2점 |
| 📋 호재 공시 | 2점 |
| 🔀 복합 신호 승수 | ×1.2~1.3 |""")
    st.markdown("---")
    st.caption("⚠️ 투자 손실에 책임지지 않습니다")

# ── localStorage 즐겨찾기 헬퍼 ──────────────────────────────────
def ls_get_favorites() -> dict:
    """session_state에서 즐겨찾기 로드"""
    if "favorites" not in st.session_state:
        st.session_state["favorites"] = {}
    return st.session_state["favorites"]

def ls_save_favorites(favs: dict):
    """즐겨찾기 저장 - session_state"""
    st.session_state["favorites"] = favs

def ls_load_from_browser():
    """브라우저 localStorage에서 즐겨찾기 로드 - st_javascript 미사용"""
    pass  # localStorage 동기화 비활성화 (렌더링 노이즈 방지)

def ls_persist_to_browser():
    """즐겨찾기를 localStorage에 동기화 - st_javascript 미사용"""
    pass  # localStorage 동기화 비활성화 (렌더링 노이즈 방지)

# ── 캐시 함수 ────────────────────────────────────────────────────
@st.cache_data(ttl=86400)
def get_all_krx_stocks() -> dict:
    """KRX 전체 상장 종목 로드 (JSON 파일 우선, 없으면 KRX에서 다운로드)"""
    import json, os
    json_path = os.path.join(os.path.dirname(__file__), "krx_stocks.json")
    try:
        if os.path.exists(json_path):
            with open(json_path, encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    # JSON 없으면 KRX에서 다운로드
    try:
        import io
        result = {}
        for market, suffix in [("stockMkt","KS"), ("kosdaqMkt","KQ")]:
            url = f"https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType={market}"
            r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
            df = pd.read_html(io.StringIO(r.content.decode("euc-kr")), header=0)[0]
            for _, row in df.iterrows():
                name = str(row["회사명"]).strip()
                code = str(row["종목코드"]).strip().zfill(6)
                result[f"{code}.{suffix}"] = name
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
        return result
    except:
        return {}

@st.cache_data(ttl=300)
def search_stock_by_name(query: str) -> list:
    """종목명으로 검색 (KRX 전체 2600+ 종목)"""
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
        df = yf.Ticker(symbol).history(period=period, auto_adjust=False)
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
    """Wilder's Smoothing RSI (EWM 방식 - stock_surge_detector._rsi와 동일)"""
    d = close.diff()
    gain = d.where(d > 0, 0.0)
    loss = -d.where(d < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    return 100 - (100 / (1 + rs))

def show_price_levels(fig):
    """차트 아래에 목표가/매수가/손절가 박스 표시"""
    if not hasattr(fig, '_price_levels') or fig._price_levels is None:
        return
    lv = fig._price_levels
    import math
    if any(math.isnan(v) for v in [lv["target"], lv["current"], lv["stop"]] if isinstance(v, float)):
        return

    rr = lv["rr_ratio"]
    rr_color = "#00ff88" if rr >= 3 else "#ffd700" if rr >= 2 else "#ff8c42"
    rr_label = "우수" if rr >= 3 else "양호" if rr >= 2 else "주의"

    st.markdown(f"""
    <div style='display:flex;gap:8px;margin:-8px 0 4px;'>
      <div style='flex:1.2;background:rgba(0,255,136,0.08);border:1px solid #00ff88;
           border-radius:10px;padding:12px;text-align:center;'>
        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>🎯 목표가</div>
        <div style='color:#00ff88;font-size:18px;font-weight:700;margin:4px 0;'>₩{lv["target"]:,.0f}</div>
        <div style='color:#00ff88;font-size:12px;'>+{lv["upside"]:.1f}%</div>
        <div style='color:#4a5568;font-size:10px;margin-top:4px;'>Fib×ATR 가중평균</div>
      </div>
      <div style='flex:1;background:rgba(255,215,0,0.08);border:1px solid #ffd700;
           border-radius:10px;padding:12px;text-align:center;'>
        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>📍 매수가</div>
        <div style='color:#ffd700;font-size:18px;font-weight:700;margin:4px 0;'>₩{lv["entry"]:,.0f}</div>
        <div style='color:#ffd700;font-size:12px;'>{lv.get("entry_label","근거가") } 기준</div>
        <div style='color:#4a5568;font-size:10px;margin-top:4px;'>240선 근거 진입가</div>
      </div>
      <div style='flex:1;background:rgba(255,51,85,0.08);border:1px solid #ff3355;
           border-radius:10px;padding:12px;text-align:center;'>
        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>🛑 손절가</div>
        <div style='color:#ff3355;font-size:18px;font-weight:700;margin:4px 0;'>₩{lv["stop"]:,.0f}</div>
        <div style='color:#ff3355;font-size:12px;'>{lv["downside"]:.1f}%</div>
        <div style='color:#4a5568;font-size:10px;margin-top:4px;'>스윙저점+ATR×1.5</div>
      </div>
      <div style='flex:0.8;background:rgba(255,215,0,0.08);border:1px solid {rr_color};
           border-radius:10px;padding:12px;text-align:center;'>
        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>⚖️ 손익비</div>
        <div style='color:{rr_color};font-size:22px;font-weight:700;margin:4px 0;'>{rr:.1f}:1</div>
        <div style='color:{rr_color};font-size:11px;'>{rr_label}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

def make_rsi_chart(rsi_s, chart_data=None):
    """RSI 차트 - 이베스트증권 스타일, 확대/축소 비활성화"""
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

    # 30 상향돌파 (이전 <= 30, 현재 > 30) → 초록 위 화살표
    cross_up = (rsi_s.shift(1) <= 30) & (rsi_s > 30)
    for dt, val in rsi_s[cross_up].items():
        fig.add_annotation(
            x=dt, y=val,
            text="▲", showarrow=False,
            font=dict(color="#00d4aa", size=14),
            yshift=8
        )

    # 70 하향이탈 (이전 >= 70, 현재 < 70) → 빨간 아래 화살표
    cross_down = (rsi_s.shift(1) >= 70) & (rsi_s < 70)
    for dt, val in rsi_s[cross_down].items():
        fig.add_annotation(
            x=dt, y=val,
            text="▼", showarrow=False,
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

def make_candle(data, title, ma240_series=None, cross_date=None, show_levels=True):
    fig = go.Figure()
    fig.add_trace(go.Ohlc(
        x=data.index, open=data["Open"], high=data["High"],
        low=data["Low"], close=data["Close"], name="주가",
        increasing_line_color="#ff3355", decreasing_line_color="#4f8ef7"))
    for w,c,nm in [(20,"#ffd700","MA20"),(60,"#ff8c42","MA60"),(240,"#ff4b6e","MA240")]:
        ma = data["Close"].rolling(w).mean()
        fig.add_trace(go.Scatter(x=data.index, y=ma, name=nm,
            line=dict(color=c, width=3 if w==240 else 1.2)))
    if cross_date is not None:
        pass  # 돌파 표시 제거

    if show_levels:
        # 마지막 행 nan 방어 (yfinance 당일 미완성 데이터)
        data_clean = data.dropna(subset=["Close", "High", "Low"])
        if len(data_clean) < 20:
            return fig
        current  = float(data_clean["Close"].iloc[-1])
        close    = data_clean["Close"]
        high     = data_clean["High"]
        low      = data_clean["Low"]
        vol      = data_clean["Volume"] if "Volume" in data_clean.columns else None

        # ── ATR(14) 계산 ─────────────────────────────────────────
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr_series = tr.rolling(14).mean().dropna()
        atr = float(atr_series.iloc[-1]) if len(atr_series) > 0 else float((high - low).mean())

        # ── 매수가: 240선 근거 진입가 ───────────────────────────
        ma240 = close.rolling(240).mean()
        ma240_v = float(ma240.iloc[-1]) if not pd.isna(ma240.iloc[-1]) else None
        swing_low_20 = float(low.tail(20).min())
        ma20 = float(close.rolling(20).mean().dropna().iloc[-1])

        entry_candidates = []
        if ma240_v:
            entry_candidates.append(("240선", ma240_v * 1.005))
        entry_candidates.append(("MA20", ma20))
        entry_candidates.append(("스윙저점", swing_low_20))

        valid_entries = [
            (label, price) for label, price in entry_candidates
            if price < current and (ma240_v is None or price >= ma240_v * 0.995)
        ]
        if valid_entries:
            entry_label = "+".join(l for l, _ in valid_entries)
            entry = sum(p for _, p in valid_entries) / len(valid_entries)  # 평균가
        else:
            entry_label, entry = "현재가", current

        # ── 손절가: 매수가 기준 근거 있는 손절 ──────────────────
        # 매수가(entry) 아래에서 근거 있는 지지선 이탈 기준
        # 1) 240선 아래 0.5% = 240선 지지 붕괴
        # 2) 스윙 저점(20일) - ATR×1.0 = 추세 붕괴
        # 3) entry 대비 -5% ~ -10% 범위 제한
        # ── 손절가: 매수가 대비 -5% 고정 ────────────────────────
        stop = entry * 0.95
        risk = max(entry - stop, entry * 0.01)

        # ── 목표가: 다중 기법 합산 ───────────────────────────────
        recent_high = float(high.tail(120).max())
        recent_low  = float(low.tail(120).min())
        swing_range = max(recent_high - recent_low, current * 0.01)

        # 1) 피보나치 확장 (스윙 저점 기준)
        fib_1272 = recent_low + swing_range * 1.272   # 보수적 목표
        fib_1618 = recent_low + swing_range * 1.618   # 표준 목표
        fib_2000 = recent_low + swing_range * 2.000   # 공격적 목표

        # 2) 직전 고점 돌파 후 저항 → 지지 전환
        prev_high      = recent_high
        prev_high_ext  = recent_high * 1.05  # 고점 돌파 후 +5% 저항

        # 3) ATR 멀티플 (변동성 기반)
        atr_x3 = current + atr * 3.0
        atr_x5 = current + atr * 5.0

        # 4) 볼린저밴드 상단 (2σ) - 과열 저항선
        ma20_s  = close.rolling(20).mean()
        std20   = close.rolling(20).std()
        bb_upper = float((ma20_s + std20 * 2.0).dropna().iloc[-1])

        # 후보 중 현재가 +3% 이상, 손익비 2:1 이상인 것만
        min_rr2 = current + risk * 2.0
        min_rr3 = current + risk * 3.0
        all_cands = sorted([
            x for x in [fib_1272, fib_1618, fib_2000,
                         prev_high, prev_high_ext,
                         atr_x3, atr_x5, bb_upper]
            if x > current * 1.03
        ])

        valid_3 = [x for x in all_cands if x >= min_rr3]
        valid_2 = [x for x in all_cands if x >= min_rr2]

        if valid_3:
            # 3:1 이상 후보들의 가중 평균 (가장 가까운 것에 가중치)
            weights = [1 / (x - current) for x in valid_3]
            target = sum(x * w for x, w in zip(valid_3, weights)) / sum(weights)
        elif valid_2:
            target = valid_2[-1]
        elif all_cands:
            target = all_cands[-1]
        else:
            target = current + risk * 3.0

        target   = min(target, current * 2.0)  # 상한 100%

        # 호가 단위 적용
        entry  = round_to_tick(entry)
        stop   = round_to_tick(stop)
        target = round_to_tick(target)

        rr_ratio = (target - entry) / (entry - stop + 1e-9)
        upside   = (target / entry - 1) * 100
        downside = (stop / entry - 1) * 100

        # 목표가 수평선 (초록)
        fig.add_hline(y=target, line=dict(color="#00ff88", width=2, dash="dash"))
        fig.add_hrect(y0=entry, y1=target, fillcolor="rgba(0,255,136,0.08)", line_width=0)
        # 매수가 수평선 (노란색)
        if entry < current:
            fig.add_hline(y=entry, line=dict(color="#ffd700", width=2, dash="dashdot"))
            fig.add_hrect(y0=stop, y1=entry, fillcolor="rgba(255,51,85,0.08)", line_width=0)
        # 현재가 수평선 (흰색)
        fig.add_hline(y=current, line=dict(color="#ffffff", width=1.5, dash="dot"))
        # 손절가 수평선 (빨강)
        fig.add_hline(y=stop, line=dict(color="#ff3355", width=2, dash="dash"))

    fig.update_layout(
        title=dict(text=title, font=dict(color="#e0e6f0", size=13)),
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font=dict(color="#8b92a5"),
        yaxis=dict(gridcolor="#1e2540", fixedrange=True, side="right", showticklabels=True),
        xaxis=dict(gridcolor="#1e2540", rangeslider_visible=False, fixedrange=True),
        legend=dict(bgcolor="#1e2130", bordercolor="#2d3555", visible=False),
        dragmode=False,
        height=500, margin=dict(l=0,r=50,t=30,b=0))
    # 차트 아래 목표가/손절가 정보 박스는 호출부에서 별도 표시
    fig._price_levels = dict(target=target, current=current, entry=entry, entry_label=entry_label, stop=stop,
                             upside=upside, downside=downside, rr_ratio=rr_ratio) if show_levels else None
    return fig

# ── 급등 예고 종목 탐지 ──────────────────────────────────────────
if mode == "🔍 급등 예고 종목 탐지":

    # 현재 조건 표시
    date_label = f"📅 {scan_date} 기준" if (use_past_date and scan_date) else "오늘 기준"
    st.markdown(f"""<div class="cond-box">
      <b style="color:#e0e6f0;">현재 탐지 조건</b>  <span style="color:#ffd700;">{date_label}</span><br>
      📉 RSI(20) 30탈출 → 📈 240선 돌파 → 🔥 RSI 70도달 → 📉 RSI 70이탈 →
      📍 현재 RSI 55↓ + 240선 위 <b style="color:#4f8ef7;">0~{max_gap}%</b> 이내
      (이탈 후 <b style="color:#ffd700;">{ob_days}일</b> 이내)
    </div>""", unsafe_allow_html=True)

    if st.button("🚀 스캔 시작", type="primary", width='stretch'):
        _as_of = scan_date if (use_past_date and scan_date) else None
        det = KoreanStockSurgeDetector(max_gap, 60, 90)
        det._ob_days = ob_days  # RSI 70 이탈 후 경과일 전달
        symbols = list(dict.fromkeys(det.all_symbols))
        total = len(symbols)

        st.markdown("<div class='sec-title'>📡 스캔 진행 중...</div>", unsafe_allow_html=True)
        prog_bar  = st.progress(0)
        prog_text = st.empty()

        results = []
        completed = [0]

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _scan(symbol):
            return det.analyze_stock(symbol, as_of_date=_as_of)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(_scan, sym): sym for sym in symbols}
            for future in as_completed(futures):
                completed[0] += 1
                sym = futures[future]
                prog_text.markdown(
                    f"<span style='color:#8b92a5;font-size:13px;'>"
                    f"({completed[0]}/{total}) {sym} 분석 중...</span>",
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
        if min_score > 0:
            results = [r for r in results if r["total_score"] >= min_score]

        st.session_state["scan_results"] = results

        # DB 캐싱
        try:
            save_scan([{k: v for k, v in r.items() if k not in ("close_series","rsi_series","ma240_series","ma60_series","ma20_series","volume_series","vol_ma_series")} for r in results])
        except:
            pass

    # session_state 없으면 오늘 DB 캐시 자동 로드
    if "scan_results" not in st.session_state:
        try:
            from datetime import date
            today = str(date.today())
            cached_today = load_scan(today)
            if cached_today:
                # 차트 데이터 복원 (yfinance 재호출)
                for r in cached_today:
                    if r.get("close_series") is None:
                        try:
                            cd = get_chart_data(r["symbol"], "2y")
                            if cd is not None and len(cd) > 20:
                                r["close_series"]  = cd["Close"]
                                r["open_series"]   = cd["Open"]
                                r["high_series"]   = cd["High"]
                                r["low_series"]    = cd["Low"]
                                r["volume_series"] = cd["Volume"]
                        except:
                            pass
                st.session_state["scan_results"] = cached_today
                st.info(f"📦 오늘({today}) 저장된 스캔 결과 {len(cached_today)}개 자동 로드됨")
        except:
            pass

    results = st.session_state.get("scan_results", [])

    if "scan_results" not in st.session_state:
        pass  # 스캔 전 - 빈 화면
    elif not results:
        st.warning("현재 조건을 만족하는 종목이 없습니다.")
        st.info("💡 사이드바에서 조건을 완화해보세요:\n- '240선 근처 범위'를 늘리거나\n- '최소 조정 기간'을 줄이거나\n- '돌파 후 최대 경과'를 늘려보세요")
    else:
            st.success(f"✅ {len(results)}개 종목이 모든 핵심 조건을 충족합니다!")

            # 요약 카드
            c1,c2,c3,c4 = st.columns(4)
            metric_card(c1, "발견 종목", f"{len(results)}개")
            metric_card(c2, "평균 1000선 이격", f"+{sum(r.get('ma240_gap',0) for r in results)/len(results):.1f}%")
            metric_card(c3, "골든크로스 평균", f"{int(sum(r.get('gc_days',0) or 0 for r in results)/len(results))}일 전")
            metric_card(c4, "최고 점수", f"{max(r['total_score'] for r in results)}점")

            st.markdown("<div class='sec-title'>🏆 급등 예고 종목 전체</div>", unsafe_allow_html=True)

            # 테이블
            rows = []
            for r in results:
                s = r["signals"]
                rows.append({
                    "종목명":     r["name"],
                    "종목코드":   r["symbol"],
                    "현재가":     f"₩{r['current_price']:,.0f}",
                    "등락률":     f"{'🔺' if r['price_change_1d']>0 else '🔽'}{r['price_change_1d']:.2f}%",
                    "1000일선":   f"₩{r.get('ma1000') or r['ma240']:,.0f}",
                    "1000선이격": f"+{r['ma240_gap']:.1f}%",
                    "골든크로스": f"{r.get('gc_days') or '-'}일 전",
                    "RSI":        r["rsi"],
                    "종합점수":   r["total_score"],
                    "원점수":     r.get("raw_score", r["total_score"]),
                    "핵심신호":   f"{r.get('core_signal_count', 0)}개",
                    "거래량":     "✅" if s.get("vol_strong_cross") else ("🔶" if s.get("vol_at_cross") else "❌"),
                    "수급":       "🔥" if r.get("both_buying") else ("✅" if r.get("smart_money_in") else "❌"),
                    "OBV":        "✅" if s.get("obv_rising") else "❌",
                    "정배열":     "✅" if s.get("ma_align") else "❌",
                    "BB수축":     "✅" if s.get("bb_squeeze_expand") else "❌",
                    "MACD":       "✅" if s.get("macd_cross") else "❌",
                    "240전환":    "✅" if s.get("ma240_turning_up") else "❌",
                    "MFI":        "✅" if s.get("mfi_oversold_recovery") else "❌",
                    "스토캐스틱": "✅" if s.get("stoch_cross") else "❌",
                    "ADX":        "✅" if s.get("adx_strong") else "❌",
                    "VWAP":       "✅" if s.get("above_vwap") else "❌",
                    "일목":       "✅" if s.get("ichimoku_bull") else "❌",
                    "52주고점":   "✅" if s.get("near_52w_high") else "❌",
                })
            df = pd.DataFrame(rows)
            st.dataframe(df,
                column_config={
                    "종합점수": st.column_config.ProgressColumn(
                        "종합점수(ML보정)", min_value=0, max_value=50, format="%d점"),
                    "원점수": st.column_config.ProgressColumn(
                        "원점수", min_value=0, max_value=39, format="%d점"),
                    "RSI": st.column_config.ProgressColumn(
                        "RSI", min_value=0, max_value=100, format="%.1f"),
                    "수급": st.column_config.TextColumn("기관/외국인", help="🔥=동시매수 ✅=한쪽매수 ❌=없음"),
                    "거래량": st.column_config.TextColumn("거래량", help="✅=3배이상 🔶=2배이상 ❌=미달"),
                },
                width='stretch', hide_index=True)

            # 차트
            if len(results) > 1:
                fig = px.bar(pd.DataFrame(results), x="name", y="total_score",
                    color="total_score", color_continuous_scale="Greens",
                    labels={"name":"종목명","total_score":"점수"}, title="종합 점수")
                fig.update_layout(paper_bgcolor="#0e1117",plot_bgcolor="#0e1117",
                    font=dict(color="#8b92a5"),xaxis_tickangle=30,
                    coloraxis_showscale=False,height=240,margin=dict(l=5,r=5,t=30,b=50))
                st.plotly_chart(fig, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, width='stretch', key="chart_score_bar")

            # 상세 카드
            st.markdown("<div class='sec-title'>🎯 종목별 상세 분석</div>", unsafe_allow_html=True)
            medals = ["gold","silver","bronze"]
            icons  = ["🥇","🥈","🥉"]

            for i, r in enumerate(results):
                medal = medals[i] if i < 3 else "rank-card"
                icon  = icons[i]  if i < 3 else f"{i+1}."
                pct   = r["total_score"] / 28 * 100
                color = "#ff3355" if r["price_change_1d"] > 0 else "#4f8ef7"
                arrow = "▲" if r["price_change_1d"] > 0 else "▼"

                # 스파크라인 제거 (렌더링 충돌 방지)
                spark_svg = ""
                news = get_news_headline(r["symbol"])
                import html as _html
                news_safe = _html.escape(news) if news else ""
                below_months = r["below_days"] // 20
                # 실시간 가격
                rt_price = get_realtime_price(r["symbol"])
                display_price = rt_price if rt_price else r["current_price"]
                # 수급 문자열 사전 계산 (f-string 충돌 방지)
                if r.get("both_buying"):
                    supply_str = "🔥기관+외국인"
                elif r.get("smart_money_in"):
                    supply_str = "✅수급있음"
                else:
                    supply_str = "❌수급없음"

                st.markdown(f"""<div class="rank-card {medal}">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                      <span style="font-size:20px;">{icon}</span>
                      <span style="color:#fff;font-size:clamp(14px,3vw,18px);font-weight:700;margin-left:6px;">{r["name"]}</span>
                      <span style="color:#8b92a5;font-size:13px;margin-left:8px;">{r["symbol"]}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:12px;">
                      <div style="text-align:right;">
                        <span style="color:#fff;font-size:clamp(14px,3vw,20px);font-weight:700;">₩{display_price:,.0f}</span>
                        <span style="color:{color};font-size:14px;margin-left:8px;">{arrow} {abs(r["price_change_1d"]):.2f}%</span>
                      </div>
                    </div>
                  </div>
                  <div style="margin-top:6px;color:#8b92a5;font-size:12px;">
                    1000일선 ₩{r.get('ma1000') or r['ma240']:,.0f} | 이격 +{r['ma240_gap']:.1f}% |
                    골든크로스 {r.get('gc_days') or '-'}일 전 |
                    수급 {supply_str} | 핵심신호 {r.get("core_signal_count",0)}개
                  </div>
                </div>""", unsafe_allow_html=True)
                # 즐겨찾기 버튼 (localStorage 기반 - 기기별 영구 저장)
                _fav_col, _news_col = st.columns([1, 5])
                _favs = ls_get_favorites()
                _is_fav = r["symbol"] in _favs
                _fav_label = "⭐ 즐겨찾기 해제" if _is_fav else "☆ 즐겨찾기"
                if _fav_col.button(_fav_label, key=f"fav_{r['symbol']}_{i}", width='stretch'):
                    if _is_fav:
                        _favs.pop(r["symbol"], None)
                    else:
                        _favs[r["symbol"]] = r["name"]
                    ls_save_favorites(_favs)
                    st.toast("⭐ 즐겨찾기에 추가됐어요!" if not _is_fav else "즐겨찾기에서 제거됐어요")
                if news_safe:
                    st.markdown(f'<div style="color:#6b7280;font-size:11px;padding:2px 8px 4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">📰 {news_safe}</div>', unsafe_allow_html=True)
                pct_str = f"{pct:.2f}"
                st.markdown(f"""<div style="padding:4px 8px 8px;">
                  <div style="color:#8b92a5;font-size:11px;margin-bottom:3px;">종합점수 {r["total_score"]}점</div>
                  <div class="bar-bg"><div class="bar-fill" style="width:{pct_str}%;"></div></div>
                </div>""", unsafe_allow_html=True)

                if True:  # 바로 표시
                    m1,m2,m3,m4,m5 = st.columns(5)
                    m1.metric("RSI(20)", f"{r['rsi']:.1f}")
                    m2.metric("1000선 이격", f"+{r['ma240_gap']:.1f}%")
                    m3.metric("골든크로스", f"{r.get('gc_days') or '-'}일 전")
                    m4.metric("1000일선", f"₩{r.get('ma1000') or r['ma240']:,.0f}")
                    m5.metric("점수", f"{r['total_score']}점")
                    # 수급 정보
                    supply_label = "🔥 기관+외국인" if r.get("both_buying") else ("✅ 수급있음" if r.get("smart_money_in") else "❌ 수급없음")
                    st.caption(f"수급: {supply_label}  |  핵심신호: {r.get('core_signal_count',0)}개  |  거래량배수: {r.get('vol_ratio',0):.1f}배")

                    s = r["signals"]
                    active = []
                    if s.get("vol_strong_cross"):       active.append(f"🚀 돌파 시 거래량 폭발 ({s['cross_vol_ratio']:.1f}배 - 강한 돌파)")
                    elif s.get("vol_at_cross"):         active.append(f"📦 돌파 시 거래량 급증 ({s['cross_vol_ratio']:.1f}배)")
                    if s.get("vol_surge_sustained"):    active.append("📊 돌파 전후 거래량 지속 증가")
                    if s.get("recent_vol"):             active.append(f"📊 최근 거래량 증가 ({s['recent_vol_ratio']:.1f}배)")
                    if r.get("both_buying"):            active.append("🔥 기관+외국인 동시 순매수 (강한 수급)")
                    elif r.get("smart_money_in"):       active.append("✅ 기관 또는 외국인 순매수")
                    if s.get("obv_rising"):             active.append("📈 OBV 지속 상승 (매집 진행 중)")
                    if s.get("ma_align"):               active.append("⚡ 이평선 정배열 (MA5>MA20>MA60)")
                    if s.get("pullback_recovery"):      active.append("🔄 눌림목 후 재상승")
                    if s.get("rsi_healthy"):            active.append(f"💚 RSI 건강 구간 ({s.get('rsi',0):.1f})")
                    if s.get("bb_squeeze_expand"):      active.append("🔥 볼린저밴드 수축→확장 (폭발 직전)")
                    if s.get("macd_cross"):             active.append("📊 MACD 골든크로스")
                    if s.get("ma240_turning_up"):       active.append("🔼 240일선 하락→상승 전환")
                    if s.get("stealth_accumulation"):   active.append("🕵️ 세력 매집 감지 (조용한 거래량 증가)")
                    if s.get("pullback_bounce"):        active.append("🎯 눌림목 반등 (최적 진입 타이밍)")
                    if s.get("peer_momentum", 0) >= 2: active.append(f"🔗 동종 섹터 동반 상승 ({s.get('peer_momentum')}개)")
                    if s.get("mfi_oversold_recovery"):  active.append(f"💰 MFI 과매도 반등 ({s.get('mfi',0):.0f})")
                    if s.get("stoch_cross"):            active.append(f"📉 스토캐스틱 골든크로스 ({s.get('stoch_k',0):.0f})")
                    if s.get("adx_strong"):             active.append(f"💪 ADX 강한 추세 ({s.get('adx',0):.0f})")
                    if s.get("above_vwap"):             active.append("📍 VWAP 위 (매수세 우위)")
                    if s.get("ichimoku_bull"):          active.append("☁️ 일목균형표 구름대 돌파")
                    if s.get("near_52w_high"):          active.append(f"🏆 52주 신고가 근처 ({s.get('high_ratio',0):.1f}%)")
                    if s.get("market_bull"):            active.append(f"📈 상승장 ({s.get('market_slope',0):+.1f}%)")
                    if s.get("sector_momentum",0) > 2:  active.append(f"🔥 섹터 강세 ({s.get('sector_momentum',0):+.1f}%)")
                    if s.get("vol_price_rising3"):      active.append("📦 3일 연속 거래량+가격 상승")
                    pd_val = s.get("pullback_depth", 0)
                    if 3 <= pd_val <= 15:               active.append(f"🎯 얕은 눌림목 ({pd_val:.1f}%)")
                    if s.get("hammer"):                 active.append("🔨 망치형 캔들")
                    if s.get("bullish_engulf"):         active.append("🕯 장악형 캔들")
                    if r.get("gc_days") is not None:    active.append(f"🔀 240/1000 골든크로스 {r['gc_days']}일 전")
                    if s.get("news_sentiment",0) > 0:   active.append(f"📰 긍정 뉴스 {s.get('pos_news',0)}건")
                    if s.get("has_disclosure"):         active.append(f"📋 호재 공시: {', '.join(s.get('disclosure_types',[]))}")

                    cols = st.columns(2)
                    for j, sig in enumerate(active):
                        cols[j%2].success(sig)
                    if not active:
                        st.info("추가 신호 없음 (핵심 조건만 충족)")

                    # 스캔 시 이미 가져온 OHLC 데이터 직접 사용 (yfinance 재호출 없음)
                    close_s = r.get("close_series")
                    if close_s is not None and len(close_s) > 20:
                        try:
                            cd = pd.DataFrame({
                                "Open":   r.get("open_series",  close_s),
                                "High":   r.get("high_series",  close_s),
                                "Low":    r.get("low_series",   close_s),
                                "Close":  close_s,
                                "Volume": r.get("volume_series", pd.Series(0, index=close_s.index))
                            })
                            cross_date = None
                            if r["days_since_cross"] < len(close_s):
                                cross_date = close_s.index[-(r["days_since_cross"]+1)]
                            _c1 = make_candle(cd, f"{r['name']} ({r['symbol']})", cross_date=cross_date)
                            st.plotly_chart(_c1, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, width='stretch', key=f"candle_{r['symbol']}_{i}")
                            show_price_levels(_c1)
                        except Exception as chart_err:
                            st.caption(f"차트 오류: {chart_err}")

# ── 개별 종목 분석 ───────────────────────────────────────────────
elif mode == "📈 개별 종목 분석":
    st.markdown("<div class='sec-title'>📈 개별 종목 분석</div>", unsafe_allow_html=True)

    from stock_surge_detector import STOCK_NAMES as DET_NAMES
    all_names = {**STOCK_NAMES, **DET_NAMES}
    opts = [f"{v} ({k})" for k,v in sorted(all_names.items(), key=lambda x:x[1])]

    # 종목명 검색
    search_col, period_col = st.columns([4, 1])
    with search_col:
        search_query = st.text_input("🔍 종목명 검색", placeholder="예: 우리기술, 삼성전자, 알테오젠...")
    with period_col:
        period = st.selectbox("기간", ["2y","1y","6mo"])

    symbol = None
    name   = None

    if search_query.strip():
        matches = search_stock_by_name(search_query.strip())
        if matches:
            search_opts = [f"{v} ({k})" for k, v in matches]
            sel_search = st.selectbox("검색 결과", search_opts, key="search_result")
            symbol = sel_search.split("(")[1].replace(")","").strip()
            name   = sel_search.split("(")[0].strip()
        else:
            st.warning(f"'{search_query}' 검색 결과 없음")
    else:
        sel = st.selectbox("종목 선택 (전체 목록)", opts)
        symbol = sel.split("(")[1].replace(")","").strip()
        name   = sel.split("(")[0].strip()

    if symbol and st.button("분석", type="primary"):
        with st.spinner(f"{name} 분석 중..."):
            det = KoreanStockSurgeDetector(max_gap, 60, 90)
            det._ob_days = ob_days
            result = det.analyze_stock(symbol)
            data = get_chart_data(symbol, period)
        # 결과를 session_state에 저장 (즐겨찾기 버튼 클릭 후에도 유지)
        st.session_state["indiv_result"] = result
        st.session_state["indiv_data"]   = data
        st.session_state["indiv_symbol"] = symbol
        st.session_state["indiv_name"]   = name

    # session_state에서 결과 로드
    result = st.session_state.get("indiv_result") if st.session_state.get("indiv_symbol") == symbol else None
    data   = st.session_state.get("indiv_data")   if st.session_state.get("indiv_symbol") == symbol else None

    if data is not None:
        current = float(data["Close"].iloc[-1])
        prev    = float(data["Close"].iloc[-2])
        chg     = (current - prev) / prev * 100
        color   = "#00d4aa" if chg > 0 else "#ff4b6e"
        arrow   = "▲" if chg > 0 else "▼"

        if result:
            pct = result["total_score"] / 28 * 100
            st.markdown(f"""<div class="rank-card gold" style="margin-bottom:16px;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <span style="color:#fff;font-size:24px;font-weight:700;">✅ {name}</span>
                  <span style="color:#00d4aa;font-size:13px;margin-left:10px;">핵심 조건 충족</span>
                </div>
                <div style="text-align:right;">
                  <span style="color:#fff;font-size:24px;font-weight:700;">₩{current:,.0f}</span>
                  <span style="color:{color};font-size:15px;margin-left:8px;">{arrow} {abs(chg):.2f}%</span>
                </div>
              </div>
              <div style="margin-top:10px;">
                <div style="color:#8b92a5;font-size:12px;margin-bottom:3px;">종합점수 {result["total_score"]}점 / 28점</div>
                <div class="bar-bg"><div class="bar-fill" style="width:{pct}%;"></div></div>
              </div>
            </div>""", unsafe_allow_html=True)

            c1,c2,c3,c4 = st.columns(4)
            metric_card(c1,"RSI(20)",f"{result['rsi']:.1f}")
            metric_card(c2,"1000선 이격",f"+{result['ma240_gap']:.1f}%")
            metric_card(c3,"골든크로스",f"{result.get('gc_days') or '-'}일 전")
            metric_card(c4,"1000일선",f"₩{result.get('ma1000') or result['ma240']:,.0f}")

            st.markdown("<div class='sec-title'>📊 신호 분석</div>", unsafe_allow_html=True)
            s = result["signals"]
            active, inactive = [], []
            checks = [
                (s.get("vol_at_cross"),         f"📦 돌파 시 거래량 급증 ({s.get('cross_vol_ratio',0):.1f}배)"),
                (s.get("recent_vol"),            f"📊 최근 거래량 증가 ({s.get('recent_vol_ratio',0):.1f}배)"),
                (s.get("stealth_accumulation"),  "🕵️ 세력 매집 감지 (조용한 거래량 증가)"),
                (s.get("pullback_bounce"),       "🎯 눌림목 반등 (최적 진입 타이밍)"),
                (s.get("obv_rising"),            "📈 OBV 지속 상승 (매집 진행 중)"),
                (s.get("ma_align"),              "⚡ 이평선 정배열 (MA5>MA20>MA60)"),
                (s.get("pullback_recovery"),     "🔄 눌림목 후 재상승"),
                (s.get("rsi_healthy"),           f"💚 RSI 건강 구간 ({s.get('rsi',0):.1f})"),
                (s.get("bb_squeeze_expand"),     "🔥 볼린저밴드 수축→확장 (폭발 직전)"),
                (s.get("macd_cross"),            "📊 MACD 골든크로스"),
                (s.get("ma240_turning_up"),      "🔼 240일선 하락→상승 전환"),
                (s.get("peer_momentum",0) >= 2,  f"🔗 동종 섹터 동반 상승 ({s.get('peer_momentum',0)}개)"),
                (s.get("hammer"),                "🔨 망치형 캔들"),
                (s.get("bullish_engulf"),        "🕯 장악형 캔들"),
                (result.get("gc_days") is not None, f"🔀 240/1000 골든크로스 {result.get('gc_days')}일 전"),
                (s.get("news_sentiment",0) > 0,  f"📰 긍정 뉴스 {s.get('pos_news',0)}건"),
                (s.get("has_disclosure"),        f"📋 호재 공시: {', '.join(s.get('disclosure_types',[]))}"),
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

            close_s2 = result.get("close_series")
            cross_date = close_s2.index[-(result["days_since_cross"]+1)] if close_s2 is not None else None
            _c2 = make_candle(data, f"{name} ({symbol})", cross_date=cross_date)
            st.plotly_chart(_c2, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, width='stretch')
            show_price_levels(_c2)

            _favs2 = ls_get_favorites()
            _is_fav2 = symbol in _favs2
            if st.button("⭐ 즐겨찾기 해제" if _is_fav2 else "☆ 즐겨찾기 추가", key=f"fav_indiv_{symbol}"):
                if _is_fav2: _favs2.pop(symbol, None)
                else: _favs2[symbol] = name
                ls_save_favorites(_favs2)
                st.toast("⭐ 추가됐어요!" if not _is_fav2 else "즐겨찾기에서 제거됐어요")

            rsi_s = result["rsi_series"]

        else:
            st.markdown(f"""<div class="rank-card" style="margin-bottom:16px;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <span style="color:#fff;font-size:24px;font-weight:700;">⚠️ {name}</span>
                  <span style="color:#ff4b6e;font-size:13px;margin-left:10px;">핵심 조건 미충족</span>
                </div>
                <div style="text-align:right;">
                  <span style="color:#fff;font-size:24px;font-weight:700;">₩{current:,.0f}</span>
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
                metric_card(c1,"현재 240선 이격",f"{gap:+.1f}%")
                metric_card(c2,"240일선",f"₩{ma240_now:,.0f}")
                if gap < 0:
                    st.warning(f"📉 현재 주가가 240일선 아래 ({gap:.1f}%) — 아직 조정 중")
                elif gap > max_gap:
                    st.warning(f"📈 240일선 위 {gap:.1f}% — 이미 많이 올라 근처 범위({max_gap}%) 초과")
                else:
                    st.warning("📊 240일선 돌파 이력 또는 조정 기간 조건 미충족")

            _c3 = make_candle(data, f"{name} ({symbol})")
            st.plotly_chart(_c3, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, width='stretch', key="chart_candle_no_cond")
            show_price_levels(_c3)

            _favs3 = ls_get_favorites()
            _is_fav3 = symbol in _favs3
            if st.button("⭐ 즐겨찾기 해제" if _is_fav3 else "☆ 즐겨찾기 추가", key=f"fav_indiv_nc_{symbol}"):
                if _is_fav3: _favs3.pop(symbol, None)
                else: _favs3[symbol] = name
                ls_save_favorites(_favs3)
                st.toast("⭐ 추가됐어요!" if not _is_fav3 else "즐겨찾기에서 제거됐어요")

            rsi_s = calc_rsi_wilder(data["Close"], period=20)


# ── 우량주 RSI 70 이탈 스캐너 ────────────────────────────────────
elif mode == "💎 우량주 RSI 70 이탈":

    # 재무 우량 + 성장성 높은 종목 (시총 상위 + 실적 안정)
    QUALITY_STOCKS = {
        # 반도체/IT
        "005930.KS": "삼성전자",
        "000660.KS": "SK하이닉스",
        "011070.KS": "LG이노텍",
        "035420.KS": "NAVER",
        "035720.KS": "카카오",
        # 자동차
        "005380.KS": "현대차",
        "000270.KS": "기아",
        "012330.KS": "현대모비스",
        # 바이오/헬스
        "207940.KS": "삼성바이오로직스",
        "068270.KS": "셀트리온",
        "145020.KQ": "휴젤",
        "214150.KQ": "클래시스",
        "196170.KQ": "알테오젠",
        # 2차전지
        "006400.KS": "삼성SDI",
        "051910.KS": "LG화학",
        "373220.KS": "LG에너지솔루션",
        "247540.KQ": "에코프로비엠",
        # 금융
        "105560.KS": "KB금융",
        "055550.KS": "신한지주",
        "316140.KS": "우리금융지주",
        # 방산/중공업
        "042660.KS": "한화오션",
        "064350.KS": "현대로템",
        "329180.KS": "HD현대중공업",
        # 소비/유통
        "090430.KS": "아모레퍼시픽",
        "097950.KS": "CJ제일제당",
        # 통신
        "017670.KS": "SK텔레콤",
        "030200.KS": "KT",
        # 소재
        "010130.KS": "고려아연",
        "005490.KS": "POSCO홀딩스",
    }

    st.markdown("""
    <div style='background:linear-gradient(135deg,#1a1f35,#0e1117);
         padding:20px 24px;border-radius:12px;margin-bottom:16px;border:1px solid #2d3555;'>
      <h3 style='color:#fff;margin:0;'>💎 재무 우량주 RSI(20) 사이클 완성 스캐너</h3>
      <p style='color:#8b92a5;margin:8px 0 0;font-size:13px;'>
        ① RSI 30 이하 (과매도) → ② RSI 30 상향돌파 → ③ RSI 70 도달 → ④ RSI 70 이탈<br>
        <b style='color:#ffd700;'>한 사이클 완성 후 다음 매수 타이밍 준비 종목</b>
      </p>
    </div>
    """, unsafe_allow_html=True)

    days_ago = st.slider("📅 최근 며칠 이내 70 이탈", 1, 60, 20, help="70선 이탈이 며칠 이내인지")

    if st.button("🔍 스캔 시작", type="primary", width='stretch'):
        results = []
        prog = st.progress(0)
        total = len(QUALITY_STOCKS)

        for idx, (symbol, name) in enumerate(QUALITY_STOCKS.items()):
            prog.progress((idx + 1) / total)
            try:
                df = yf.Ticker(symbol).history(period="2y", auto_adjust=False)
                if df is None or len(df) < 60:
                    continue
                rsi = calc_rsi_wilder(df["Close"], 20).dropna()
                if len(rsi) < 40:
                    continue

                # ── 사이클 탐지 ──────────────────────────────
                # 1) RSI 30 이하 구간 존재
                below30 = rsi[rsi <= 30]
                if len(below30) == 0:
                    continue
                bottom_date = below30.index[0]
                bottom_rsi  = float(below30.min())

                # 2) 30 상향돌파 (bottom 이후)
                after_bottom = rsi[rsi.index > bottom_date]
                cross30 = after_bottom[after_bottom > 30]
                if len(cross30) == 0:
                    continue
                cross30_date = cross30.index[0]

                # 3) 70 도달 (30돌파 이후)
                after_cross30 = rsi[rsi.index > cross30_date]
                above70 = after_cross30[after_cross30 >= 70]
                if len(above70) == 0:
                    continue
                peak_date = above70.index[0]
                peak_rsi  = float(above70.max())

                # 4) 70 이탈 (peak 이후) — 최근 days_ago 이내
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
            st.warning(f"최근 {days_ago}일 이내 RSI 사이클 완성 종목이 없습니다. 기간을 늘려보세요.")
        else:
            results.sort(key=lambda x: x["days_since"])
            st.success(f"✅ {len(results)}개 종목 발견!")

            c1, c2, c3 = st.columns(3)
            metric_card(c1, "발견 종목", f"{len(results)}개")
            metric_card(c2, "평균 현재 RSI", f"{sum(r['current_rsi'] for r in results)/len(results):.1f}")
            metric_card(c3, "최근 이탈", f"{min(r['days_since'] for r in results)}일 전")

            st.markdown("<div class='sec-title'>📋 RSI 사이클 완성 종목</div>", unsafe_allow_html=True)

            df_out = pd.DataFrame([{
                "종목명":    r["name"],
                "종목코드":  r["symbol"],
                "현재가":    f"₩{r['current_price']:,.0f}",
                "등락률":    f"{'🔺' if r['price_change_1d']>0 else '🔽'}{r['price_change_1d']:.2f}%",
                "현재RSI":   round(r["current_rsi"], 1),
                "바닥RSI":   round(r["bottom_rsi"], 1),
                "고점RSI":   round(r["peak_rsi"], 1),
                "30돌파일":  r["cross30_date"],
                "70이탈일":  r["cross70_date"],
                "경과일":    f"{r['days_since']}일",
            } for r in results])

            st.dataframe(df_out,
                column_config={
                    "현재RSI": st.column_config.ProgressColumn("현재RSI", min_value=0, max_value=100, format="%.1f"),
                    "고점RSI": st.column_config.ProgressColumn("고점RSI", min_value=0, max_value=100, format="%.1f"),
                },
                width='stretch', hide_index=True)

            st.markdown("<div class='sec-title'>📈 종목별 RSI 차트</div>", unsafe_allow_html=True)
            for r in results:
                with st.expander(f"📊 {r['name']} ({r['symbol']}) — 현재 RSI: {r['current_rsi']:.1f} | 70이탈: {r['cross70_date']}", expanded=True):
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("바닥 RSI", f"{r['bottom_rsi']:.1f}")
                    m2.metric("고점 RSI", f"{r['peak_rsi']:.1f}")
                    m3.metric("현재 RSI", f"{r['current_rsi']:.1f}")
                    m4.metric("70이탈 후", f"{r['days_since']}일")
                    st.plotly_chart(
                        make_rsi_chart(r["rsi_series"], r["df"]),
                        config={"scrollZoom": False, "displayModeBar": False},
                        width='stretch', key=f"rsi_quality_{r['symbol']}")
                    _c4 = make_candle(r["df"], f"{r['name']} ({r['symbol']})")
                    st.plotly_chart(_c4, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, width='stretch', key=f"candle_quality_{r['symbol']}")
                    show_price_levels(_c4)


# ── 최적 급등 타이밍 탐지 ────────────────────────────────────────
elif mode == "🎯 최적 급등 타이밍":

    st.markdown("""
    <div style='background:linear-gradient(135deg,#0d1528,#111827);
         padding:20px 24px;border-radius:14px;margin-bottom:16px;border:1px solid rgba(79,142,247,0.2);'>
      <h3 style='color:#f0f4ff;margin:0;font-size:18px;font-weight:800;'>🎯 최적 급등 타이밍 탐지 시스템</h3>
      <p style='color:#8b92a5;margin:8px 0 0;font-size:13px;line-height:1.6;'>
        9가지 핵심 조건이 동시에 겹치는 순간을 포착합니다.<br>
        <b style='color:#ffd700;'>에너지 축적 → 세력 매집 → 변동성 수축 → 돌파 직전</b> 패턴
      </p>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📖 9가지 핵심 조건 설명", expanded=False):
        st.markdown("""
| # | 조건 | 점수 | 설명 |
|---|------|------|------|
| 1 | 🏔 충분한 조정 후 바닥 | 최대 4점 | 120일+ 하락 조정 후 바닥 다지기 (에너지 축적) |
| 2 | 📦 세력 매집 신호 | 3점 | OBV 상승 + 가격 횡보 (가격 안 오르는데 거래량 증가) |
| 3 | 🔥 볼린저밴드 수축 | 3점 | BB Width 최저점 근처 (폭발 직전 에너지 압축) |
| 4 | 💚 RSI 바닥 사이클 | 3점 | RSI 30 이하 → 30 돌파 → 50 이상 (건강한 반등) |
| 5 | ⚡ 이평선 정배열 | 3점 | MA5 > MA20 > MA60 순서 정렬 |
| 6 | 📊 MACD 골든크로스 | 2점 | MACD 히스토그램 0선 상향 돌파 |
| 7 | 🕯 장대양봉 + 거래량 | 3점 | 평균 대비 2배+ 거래량에 양봉 (세력 진입 확인) |
| 8 | 🏆 52주 신고가 돌파 직전 | 3점 | 52주 고점 5% 이내 (저항선 돌파 임박) |
| 9 | 📈 240선 확인 돌파 | 최대 4점 | 가짜 돌파 없음 + 기울기 정상 + 재이탈 없음 |
        """)

    def calc_surge_timing_score(symbol):
        """최적 급등 타이밍 - 필수 3조건 + 가산점"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="2y", auto_adjust=False)
            if df is None or len(df) < 60:
                return None

            close = df["Close"].dropna()
            high  = df["High"].dropna()
            low   = df["Low"].dropna()
            vol   = df["Volume"].dropna()
            n     = len(close)
            if n < 60: return None

            current = float(close.iloc[-1])
            prev    = float(close.iloc[-2])
            chg     = (current - prev) / prev * 100

            ma5   = close.rolling(5).mean()
            ma20  = close.rolling(20).mean()
            ma60  = close.rolling(60).mean()
            ma240 = close.rolling(240).mean() if n >= 240 else None

            score   = 0
            signals = {}

            # ══════════════════════════════════════════════════════
            # 필수 조건 1: 240선 위 0~10% + 3일 연속 유지
            # ══════════════════════════════════════════════════════
            if ma240 is None or pd.isna(ma240.iloc[-1]):
                return None
            ma240_v   = float(ma240.iloc[-1])
            ma240_gap = (current - ma240_v) / ma240_v * 100
            if not (0 <= ma240_gap <= 10):
                return None
            days_above = sum(1 for i in range(-3, 0) if float(close.iloc[i]) > float(ma240.iloc[i]))
            if days_above < 3:
                return None
            signals["ma240_gap"]       = round(ma240_gap, 1)
            signals["ma240_confirmed"] = True

            # ══════════════════════════════════════════════════════
            # 필수 조건 2: 이평선 정배열 (MA5 > MA20 > MA60)
            # ══════════════════════════════════════════════════════
            if pd.isna(ma60.iloc[-1]):
                return None
            if not (float(ma5.iloc[-1]) > float(ma20.iloc[-1]) > float(ma60.iloc[-1])):
                return None
            signals["ma_align"] = True

            # ══════════════════════════════════════════════════════
            # 필수 조건 3: 거래량 동반 (최근 5일 평균 > 20일 평균의 1.3배)
            # ══════════════════════════════════════════════════════
            vol_ma5  = float(vol.tail(5).mean())
            vol_ma20 = float(vol.rolling(20).mean().iloc[-1])
            vol_ratio_5 = vol_ma5 / (vol_ma20 + 1e-9)
            if vol_ratio_5 < 1.3:
                return None
            signals["vol_ratio"] = round(vol_ratio_5, 2)

            # ══════════════════════════════════════════════════════
            # 가산점 조건들
            # ══════════════════════════════════════════════════════

            # 240선 기울기 상승 전환 (+3)
            ma240_slope = (float(ma240.iloc[-1]) - float(ma240.iloc[-20])) / float(ma240.iloc[-20]) * 100 if n >= 20 else 0
            signals["ma240_slope"] = round(ma240_slope, 2)
            if ma240_slope >= 0:
                score += 3
                signals["ma240_turning_up"] = True
            elif ma240_slope >= -1.0:
                score += 1
                signals["ma240_turning_up"] = False
            else:
                signals["ma240_turning_up"] = False

            # 돌파 후 재이탈 없음 (+3)
            cross_found = False
            broke_below = False
            for i in range(n-2, max(n-61, 0), -1):
                if float(close.iloc[i]) > float(ma240.iloc[i]) and float(close.iloc[i-1]) <= float(ma240.iloc[i-1]):
                    cross_found = True
                    broke_below = any(float(close.iloc[j]) < float(ma240.iloc[j]) for j in range(i+1, n))
                    break
            signals["ma240_no_rebreak"] = cross_found and not broke_below
            if signals["ma240_no_rebreak"]: score += 3

            # RSI 바닥 사이클 완성 (+3)
            rsi = calc_rsi_wilder(close, 20)
            cur_rsi = float(rsi.iloc[-1])
            signals["rsi"] = round(cur_rsi, 1)
            rsi_90 = rsi.tail(90).dropna()
            had_below30 = (rsi_90 < 30).any()
            crossed_30  = ((rsi_90.shift(1) <= 30) & (rsi_90 > 30)).any()
            rsi_healthy = 40 <= cur_rsi <= 65
            signals["rsi_cycle"]   = had_below30 and crossed_30 and rsi_healthy
            signals["rsi_healthy"] = rsi_healthy
            if signals["rsi_cycle"]: score += 3
            elif rsi_healthy:        score += 1

            # BB 수축→확장 (+3)
            bb_std = close.rolling(20).std()
            bb_mid = close.rolling(20).mean()
            bb_w   = (4 * bb_std) / bb_mid.replace(0, np.nan)
            bb_w_min60 = float(bb_w.tail(60).min())
            bb_w_now   = float(bb_w.iloc[-1])
            bb_w_prev5 = float(bb_w.iloc[-5])
            signals["bb_squeeze"]   = bb_w_now <= bb_w_min60 * 1.2
            signals["bb_expanding"] = bb_w_now > bb_w_prev5 * 1.03
            signals["bb_width"]     = round(bb_w_now, 4)
            if signals["bb_squeeze"] and signals["bb_expanding"]: score += 3
            elif signals["bb_squeeze"]:                           score += 1

            # MACD 골든크로스 (+2)
            macd   = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
            macd_s = macd.ewm(span=9, adjust=False).mean()
            macd_h = macd - macd_s
            signals["macd_cross"]    = bool(macd_h.iloc[-1] > 0 and macd_h.iloc[-2] <= 0)
            signals["macd_positive"] = bool(macd_h.iloc[-1] > 0)
            if signals["macd_cross"]:    score += 2
            elif signals["macd_positive"]: score += 1

            # 세력 매집 (+2)
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

            # 장대양봉 (+2)
            body_ratio = (float(close.iloc[-1]) - float(df["Open"].iloc[-1])) / (float(high.iloc[-1]) - float(low.iloc[-1]) + 1e-9)
            vol_today  = float(vol.iloc[-1]) / (vol_ma20 + 1e-9)
            signals["big_bull_candle"] = vol_today >= 2.0 and body_ratio >= 0.6 and chg > 0
            signals["vol_surge"]       = vol_today >= 1.5
            if signals["big_bull_candle"]: score += 2
            elif signals["vol_surge"]:     score += 1

            # 52주 신고가 근처 (+2)
            high_52w   = float(high.tail(252).max())
            high_ratio = current / high_52w
            signals["near_52w_high"] = high_ratio >= 0.92
            signals["high_ratio"]    = round(high_ratio * 100, 1)
            if high_ratio >= 0.98:   score += 2
            elif high_ratio >= 0.92: score += 1

            # 눌림목 반등 구간 (+2)
            low_120  = float(close.tail(120).min())
            high_120 = float(close.tail(120).max())
            recovery = (current - low_120) / (high_120 - low_120 + 1e-9)
            signals["recovery_zone"] = 0.10 <= recovery <= 0.50
            signals["recovery_pct"]  = round(recovery * 100, 1)
            if 0.10 <= recovery <= 0.30: score += 2
            elif 0.30 < recovery <= 0.50: score += 1

            signals["ma240_gap"]       = round(ma240_gap, 1)
            signals["ma_align_forming"] = False

            return {
                "symbol":          symbol,
                "name":            STOCK_NAMES.get(symbol, symbol),
                "current_price":   current,
                "price_change_1d": round(chg, 2),
                "total_score":     score,
                "max_score":       22,
                "signals":         signals,
                "rsi":             cur_rsi,
                "rsi_series":      rsi,
                "df":              df,
            }
        except Exception:
            return None

    if st.button("🚀 최적 타이밍 스캔", type="primary", width='stretch'):
        from stock_surge_detector import ALL_SYMBOLS as SCAN_SYMBOLS
        from concurrent.futures import ThreadPoolExecutor, as_completed

        symbols  = list(dict.fromkeys(SCAN_SYMBOLS))  # 중복 제거
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
                prog_text.markdown(f"<span style='color:#8b92a5;font-size:13px;'>({completed[0]}/{total}) {sym} 분석 중...</span>", unsafe_allow_html=True)
                prog.progress(completed[0] / total)
                try:
                    r = future.result()
                    if r and r["total_score"] >= 5:
                        results.append(r)
                except:
                    pass

        prog.empty()
        prog_text.empty()
        results.sort(key=lambda x: x["total_score"], reverse=True)

        if not results:
            st.warning("현재 조건을 충족하는 종목이 없습니다.")
        else:
            st.success(f"✅ {len(results)}개 종목 발견!")

            c1, c2, c3, c4 = st.columns(4)
            metric_card(c1, "발견 종목", f"{len(results)}개")
            metric_card(c2, "최고 점수", f"{results[0]['total_score']}점")
            metric_card(c3, "평균 점수", f"{sum(r['total_score'] for r in results)/len(results):.1f}점")
            metric_card(c4, "만점", "30점")

            st.markdown("<div class='sec-title'>🏆 최적 급등 타이밍 TOP 종목</div>", unsafe_allow_html=True)

            rows = []
            for r in results:
                s = r["signals"]
                rows.append({
                    "종목명":   r["name"],
                    "현재가":   f"₩{r['current_price']:,.0f}",
                    "등락률":   f"{'🔺' if r['price_change_1d']>0 else '🔽'}{r['price_change_1d']:.2f}%",
                    "종합점수": r["total_score"],
                    "RSI":      round(r["rsi"], 1),
                    "거래량비": f"{s.get('vol_ratio',0):.1f}배",
                    "반등위치": f"{s.get('recovery_pct',0):.0f}%",
                    "52주고점": f"{s.get('high_ratio',0):.1f}%",
                    "240선":    "🔥" if s.get("ma240_confirmed") and s.get("ma240_no_rebreak") else ("✅" if s.get("ma240_gap") is not None and 0 <= (s.get("ma240_gap") or -1) <= 10 else "❌"),
                    "매집":     "✅" if s.get("accumulation") else "❌",
                    "BB수축":   "✅" if s.get("bb_squeeze") else "❌",
                    "RSI사이클":"✅" if s.get("rsi_cycle") else "❌",
                    "정배열":   "✅" if s.get("ma_align") else "❌",
                    "MACD":     "✅" if s.get("macd_cross") or s.get("macd_positive") else "❌",
                    "장대양봉": "✅" if s.get("big_bull_candle") else "❌",
                })
            df_tbl = pd.DataFrame(rows)
            st.dataframe(df_tbl,
                column_config={
                    "종합점수": st.column_config.ProgressColumn(
                        "종합점수", min_value=0, max_value=30, format="%d점"),
                    "240선": st.column_config.TextColumn("240선 확인", help="🔥=완전확인 ✅=근처 ❌=해당없음"),
                },
                width='stretch', hide_index=True)

            # 상위 종목 상세
            st.markdown("<div class='sec-title'>🔍 상위 종목 상세 분석</div>", unsafe_allow_html=True)
            medals = ["gold","silver","bronze"]
            icons  = ["🥇","🥈","🥉"]

            for i, r in enumerate(results[:10]):
                medal = medals[i] if i < 3 else ""
                icon  = icons[i]  if i < 3 else f"{i+1}."
                s     = r["signals"]
                pct   = r["total_score"] / 30 * 100
                color = "#00d4aa" if r["price_change_1d"] > 0 else "#ff4b6e"
                arrow = "▲" if r["price_change_1d"] > 0 else "▼"

                st.markdown(f"""<div class="rank-card {medal}">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                      <span style="font-size:20px;">{icon}</span>
                      <span style="color:#fff;font-size:18px;font-weight:700;margin-left:6px;">{r["name"]}</span>
                      <span style="color:#8b92a5;font-size:13px;margin-left:8px;">{r["symbol"]}</span>
                    </div>
                    <div style="text-align:right;">
                      <span style="color:#fff;font-size:20px;font-weight:700;">₩{r["current_price"]:,.0f}</span>
                      <span style="color:{color};font-size:14px;margin-left:8px;">{arrow} {abs(r["price_change_1d"]):.2f}%</span>
                    </div>
                  </div>
                  <div style="margin-top:8px;color:#8b92a5;font-size:12px;">
                    RSI {s.get('rsi',0):.1f} | 거래량 {s.get('vol_ratio',0):.1f}배 |
                    반등위치 {s.get('recovery_pct',0):.0f}% | 52주고점 {s.get('high_ratio',0):.1f}%
                    {f"| 240선 +{s['ma240_gap']:.1f}%" if s.get('ma240_gap') is not None and s['ma240_gap'] >= 0 else ""}
                  </div>
                  <div style="margin-top:8px;">
                    <div style="color:#8b92a5;font-size:11px;margin-bottom:3px;">종합점수 {r["total_score"]}점 / 30점</div>
                    <div class="bar-bg"><div class="bar-fill" style="width:{pct}%;"></div></div>
                  </div>
                </div>""", unsafe_allow_html=True)

                with st.expander(f"📊 {r['name']} 상세 신호 + 차트", expanded=(i==0)):
                    active, inactive = [], []
                    checks = [
                        (s.get("recovery_zone"),      f"🏔 최적 반등 구간 ({s.get('recovery_pct',0):.0f}%)"),
                        (s.get("accumulation"),        "📦 세력 매집 신호 (OBV↑ + 가격횡보)"),
                        (s.get("obv_rising"),          "📈 OBV 상승 중"),
                        (s.get("bb_squeeze"),          f"🔥 볼린저밴드 수축 ({s.get('bb_width',0):.4f})"),
                        (s.get("bb_expanding"),        "💥 BB 확장 시작 (폭발 직전)"),
                        (s.get("rsi_cycle"),           f"💚 RSI 바닥 사이클 완성 ({s.get('rsi',0):.1f})"),
                        (s.get("ma_align"),            "⚡ 이평선 완전 정배열"),
                        (s.get("ma_align_forming"),    "⚡ 이평선 정배열 형성 중"),
                        (s.get("macd_cross"),          "📊 MACD 골든크로스"),
                        (s.get("macd_positive"),       "📊 MACD 양전환"),
                        (s.get("big_bull_candle"),     f"🕯 장대양봉 + 거래량 급증 ({s.get('vol_ratio',0):.1f}배)"),
                        (s.get("vol_surge"),           f"📦 거래량 급증 ({s.get('vol_ratio',0):.1f}배)"),
                        (s.get("near_52w_high"),       f"🏆 52주 신고가 직전 ({s.get('high_ratio',0):.1f}%)"),
                        (s.get("ma240_confirmed") and s.get("ma240_no_rebreak"),
                                                       f"🔥 240선 완전 확인 돌파 (+{s.get('ma240_gap',0):.1f}%)"),
                        (s.get("ma240_gap") is not None and 0 <= s.get("ma240_gap",999) <= 10 and not s.get("ma240_confirmed"),
                                                       f"📍 240일선 근처 (+{s.get('ma240_gap',0):.1f}%)"),
                    ]
                    for flag, label in checks:
                        (active if flag else inactive).append(label)

                    ca, cb = st.columns(2)
                    with ca:
                        st.write("**✅ 충족 신호**")
                        for sig in active: st.success(sig)
                    with cb:
                        st.write("**❌ 미충족**")
                        for sig in inactive[:6]: st.error(sig)

                    cd = r["df"]
                    _c5 = make_candle(cd, f"{r['name']} ({r['symbol']})", show_levels=True)
                    st.plotly_chart(_c5, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, width='stretch', key=f"candle_timing_{r['symbol']}")
                    show_price_levels(_c5)
                    st.plotly_chart(
                        make_rsi_chart(r["rsi_series"], cd),
                        config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True},
                        width='stretch', key=f"rsi_timing_{r['symbol']}")


# ── 즐겨찾기 탭 ──────────────────────────────────────────────────
elif mode == "⭐ 즐겨찾기":
    st.markdown("<div class='sec-title'>⭐ 즐겨찾기 종목</div>", unsafe_allow_html=True)

    # 탭 진입 시 1회만 localStorage에서 로드
    if "fav_loaded" not in st.session_state:
        ls_load_from_browser()
        st.session_state["fav_loaded"] = True

    # 현재 즐겨찾기를 localStorage에 동기화
    ls_persist_to_browser()

    favs_dict = ls_get_favorites()

    if not favs_dict:
        st.info("즐겨찾기한 종목이 없습니다. 급등 탐지 탭에서 종목 카드의 ☆ 버튼을 눌러 추가하세요.")
    else:
        st.success(f"총 {len(favs_dict)}개 종목 (이 기기에 저장됨)")
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
                      <span style='color:#fff;font-size:18px;font-weight:700;'>₩{cur_f:,.0f}</span>
                      <span style='color:{color_f};font-size:13px;margin-left:8px;'>{"▲" if chg_f>0 else "▼"} {abs(chg_f):.2f}%</span>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"**{name}** ({sym})")
            with col2:
                if st.button("🗑 삭제", key=f"del_fav_{sym}"):
                    favs_dict.pop(sym, None)
                    ls_save_favorites(favs_dict)
                    st.rerun()
            st.markdown("")

        if st.button("📊 즐겨찾기 전체 차트 보기", type="primary"):
            for sym, name in favs_dict.items():
                cd = get_chart_data(sym, "2y")
                if cd is not None:
                    fig_f = make_candle(cd, f"{name} ({sym})")
                    st.plotly_chart(fig_f, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True},
                                    width='stretch', key=f"fav_chart_{sym}")
                    show_price_levels(fig_f)

# ── 백테스트 탭 ───────────────────────────────────────────────────
elif mode == "📊 백테스트":
    st.markdown("<div class='sec-title'>📊 전략 백테스트 결과</div>", unsafe_allow_html=True)

    st.markdown("""
    <div style='background:#1a1f35;border-radius:12px;padding:16px;border:1px solid #2d3555;margin-bottom:16px;'>
      <div style='color:#e0e6f0;font-size:14px;font-weight:600;margin-bottom:8px;'>📌 백테스트 방법론</div>
      <div style='color:#8b92a5;font-size:13px;line-height:1.8;'>
        • 과거 2년 데이터에서 신호 발생 시점 탐지<br>
        • 신호 발생 후 <b style='color:#ffd700;'>20일 수익률</b> 측정<br>
        • BB수축+MACD+거래량 3종 세트 동시 발생 시점 기준<br>
        • 슬리피지/수수료 미반영 (참고용)
      </div>
    </div>
    """, unsafe_allow_html=True)

    # 신호 가중치 표
    st.markdown("#### 신호별 가중치 (백테스팅 기반)")
    try:
        weight_df = pd.DataFrame([
            {"신호": k, "가중치": v,
             "설명": {
                "bb_squeeze_expand": "볼린저밴드 수축→확장 (폭발 직전)",
                "vol_price_rising3": "3일 연속 거래량+가격 상승",
                "ichimoku_bull": "일목균형표 상승 신호",
                "ma240_turning_up": "240일선 하락→상승 전환",
                "vol_at_cross": "240선 돌파 시 거래량 급증",
                "ma_align": "이동평균선 정배열",
                "macd_cross": "MACD 골든크로스",
                "pullback_recovery": "눌림목 회복",
                "mfi_oversold_recovery": "MFI 과매도 반등",
                "near_52w_high": "52주 신고가 근처",
             }.get(k, k)}
            for k, v in sorted(SIGNAL_WEIGHTS.items(), key=lambda x: -x[1])
        ])
        st.dataframe(weight_df,
            column_config={
                "가중치": st.column_config.ProgressColumn("가중치", min_value=0, max_value=2.5, format="%.1f")
            },
            width='stretch', hide_index=True)
    except:
        st.warning("백테스트 모듈을 불러올 수 없습니다.")

    st.markdown("---")
    st.markdown("#### 종목별 백테스트 실행")
    st.caption("선택 종목의 과거 신호 발생 시점 → 20일 후 평균 수익률 계산")

    bt_col1, bt_col2 = st.columns([3, 2])
    with bt_col1:
        bt_query = st.text_input("🔍 종목명 검색 (KRX 전체)", placeholder="예: 우리기술, 삼성전자, 알테오젠...", key="bt_search")
    with bt_col2:
        bt_direct = st.text_input("직접 입력 (종목코드)", placeholder="예: 041190.KQ", key="bt_direct")

    bt_sym  = None
    bt_name = ""

    if bt_direct.strip():
        bt_sym  = bt_direct.strip()
        bt_name = bt_sym
        st.info(f"직접 입력: {bt_sym}")
    elif bt_query.strip():
        bt_matches = search_stock_by_name(bt_query.strip())
        if bt_matches:
            bt_opts2 = [f"{v} ({k})" for k, v in bt_matches]
            bt_sel2  = st.selectbox("검색 결과", bt_opts2, key="bt_symbol2")
            bt_sym   = bt_sel2.split("(")[-1].replace(")", "").strip()
            bt_name  = bt_sel2.split("(")[0].strip()
        else:
            st.warning(f"'{bt_query}' 검색 결과 없음. 종목코드로 직접 입력해보세요.")
    else:
        from stock_surge_detector import STOCK_NAMES as DET_NAMES
        all_bt = {**STOCK_NAMES, **DET_NAMES}
        bt_opts = [f"{v} ({k})" for k, v in sorted(all_bt.items(), key=lambda x: x[1])]
        bt_sel  = st.selectbox("종목 선택", bt_opts, key="bt_symbol")
        bt_sym  = bt_sel.split("(")[-1].replace(")", "").strip()
        bt_name = bt_sel.split("(")[0].strip()

    if bt_sym and st.button("🔬 백테스트 실행", type="primary"):
        with st.spinner(f"{bt_name} 백테스트 중... (1~2분 소요)"):
            try:
                bt_result = backtest_signal(bt_sym)
            except:
                bt_result = None

        if bt_result is None:
            st.warning("데이터 부족 또는 신호 발생 이력 없음")
        else:
            avg_ret  = bt_result["avg_ret"]
            win_rate = bt_result["win_rate"]
            trades   = bt_result["trades"]
            hold_d   = bt_result["hold_days"]
            color_bt = "#00d4aa" if avg_ret > 0 else "#ff4b6e"
            grade    = "🔥 강력" if avg_ret > 10 else "✅ 양호" if avg_ret > 3 else "⚠️ 보통" if avg_ret > 0 else "❌ 주의"

            c1, c2, c3, c4 = st.columns(4)
            c1.metric(f"{hold_d}일 평균 수익률", f"{avg_ret:+.2f}%")
            c2.metric("승률", f"{win_rate:.1f}%")
            c3.metric("신호 발생 횟수", f"{trades}회")
            c4.metric("전략 등급", grade)

            st.markdown(f"""
            <div style='background:#1a1f35;border-radius:12px;padding:20px;border:1px solid {color_bt};margin-top:12px;text-align:center;'>
              <div style='color:#8b92a5;font-size:13px;'>앱 전체 신호(10종) 가중치 합산 기준 | {hold_d}일 후 평균 수익률</div>
              <div style='color:{color_bt};font-size:48px;font-weight:800;margin:12px 0;'>{avg_ret:+.2f}%</div>
              <div style='color:#8b92a5;font-size:12px;'>과거 2년 데이터 기준 | 슬리피지 미반영 | 5일 간격 샘플링</div>
            </div>
            """, unsafe_allow_html=True)

            # 신호별 기여도
            if bt_result.get("sig_contrib"):
                st.markdown("#### 신호별 평균 수익률 기여도")
                contrib_df = pd.DataFrame([
                    {"신호": k, "평균수익률": v,
                     "발생횟수": bt_result["sig_contrib"].get(k, 0)}
                    for k, v in sorted(bt_result["sig_contrib"].items(), key=lambda x: -x[1])
                ])
                st.dataframe(contrib_df,
                    column_config={
                        "평균수익률": st.column_config.NumberColumn("평균수익률(%)", format="%.2f")
                    },
                    width='stretch', hide_index=True)

    # 과거 스캔 결과 히스토리
    st.markdown("---")
    st.markdown("#### 📅 과거 스캔 결과 히스토리")
    try:
        scan_dates = list_scan_dates()
        if not scan_dates:
            st.info("저장된 스캔 결과가 없습니다. 급등 탐지 탭에서 스캔을 실행하면 자동 저장됩니다.")
        else:
            date_opts = [d["date"] for d in scan_dates]
            sel_date  = st.selectbox("날짜 선택", date_opts)
            cached    = load_scan(sel_date)
            if cached:
                st.success(f"{sel_date} — {len(cached)}개 종목")
                hist_df = pd.DataFrame([{
                    "종목명": r.get("name",""),
                    "종목코드": r.get("symbol",""),
                    "현재가": f"₩{r.get('current_price',0):,.0f}",
                    "240선이격": f"+{r.get('ma240_gap',0):.1f}%",
                    "조정기간": f"{r.get('below_days',0)}일",
                    "종합점수": r.get("total_score", 0),
                } for r in cached])
                st.dataframe(hist_df, width='stretch', hide_index=True)
    except:
        st.info("히스토리 기능을 사용하려면 먼저 스캔을 실행하세요.")

# ── 성과 추적 탭 ──────────────────────────────────────────────────
elif mode == "📈 성과 추적":
    st.markdown("<div class='sec-title'>📈 알림 종목 성과 추적</div>", unsafe_allow_html=True)

    try:
        from cache_db import (get_alert_history, get_alert_history_range,
                               get_performance_summary, update_alert_status,
                               get_monthly_stats, get_available_date_range)

        col_refresh, col_empty = st.columns([1, 4])
        with col_refresh:
            if st.button("🔄 상태 업데이트", type="primary", width='stretch'):
                with st.spinner("현재가 확인 중..."):
                    update_alert_status()
                st.success("업데이트 완료!")
                st.rerun()

        # ── 기간 필터 ──────────────────────────────────────────
        st.markdown("<div class='sec-title'>📅 기간 설정</div>", unsafe_allow_html=True)
        db_min, db_max = get_available_date_range()

        filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 2])
        with filter_col1:
            period_preset = st.selectbox("기간 프리셋", ["전체", "이번 달", "최근 3개월", "최근 6개월", "올해", "직접 입력"], key="perf_period")
        with filter_col2:
            view_mode = st.selectbox("보기 모드", ["요약 + 내역", "월별 통계"], key="perf_view")

        from datetime import date as _date, timedelta as _td
        today_str = _date.today().isoformat()
        if period_preset == "이번 달":
            d_from = _date.today().replace(day=1).isoformat()
            d_to   = today_str
        elif period_preset == "최근 3개월":
            d_from = (_date.today() - _td(days=90)).isoformat()
            d_to   = today_str
        elif period_preset == "최근 6개월":
            d_from = (_date.today() - _td(days=180)).isoformat()
            d_to   = today_str
        elif period_preset == "올해":
            d_from = _date.today().replace(month=1, day=1).isoformat()
            d_to   = today_str
        elif period_preset == "직접 입력":
            with filter_col3:
                dc1, dc2 = st.columns(2)
                d_from = dc1.text_input("시작일 (YYYY-MM-DD)", value=db_min or today_str, key="perf_from")
                d_to   = dc2.text_input("종료일 (YYYY-MM-DD)", value=today_str, key="perf_to")
        else:  # 전체
            d_from = None
            d_to   = None

        period_label = period_preset if period_preset != "직접 입력" else f"{d_from} ~ {d_to}"

        # ── 월별 통계 뷰 ──────────────────────────────────────
        if view_mode == "월별 통계":
            monthly = get_monthly_stats()
            if not monthly:
                st.info("아직 성과 데이터가 없어요.")
            else:
                # 기간 필터 적용
                if d_from:
                    monthly = [m for m in monthly if m["month"] >= d_from[:7]]
                if d_to:
                    monthly = [m for m in monthly if m["month"] <= d_to[:7]]

                if not monthly:
                    st.warning("해당 기간에 데이터가 없습니다.")
                else:
                    months      = [m["month"] for m in monthly]
                    win_rates   = [m["win_rate"] for m in monthly]
                    avg_returns = [m["avg_return"] for m in monthly]
                    total_rets  = [m["total_return"] for m in monthly]
                    totals      = [m["total"] for m in monthly]

                    # 월별 승률 + 평균수익률 차트
                    fig_monthly = go.Figure()
                    fig_monthly.add_trace(go.Bar(
                        x=months, y=[m["wins"] for m in monthly],
                        name="목표달성", marker_color="#00d4aa", opacity=0.85
                    ))
                    fig_monthly.add_trace(go.Bar(
                        x=months, y=[m["losses"] for m in monthly],
                        name="손절", marker_color="#ff3355", opacity=0.85
                    ))
                    fig_monthly.add_trace(go.Bar(
                        x=months, y=[m["expired"] for m in monthly],
                        name="만료", marker_color="#3d4466", opacity=0.85
                    ))
                    fig_monthly.add_trace(go.Scatter(
                        x=months, y=win_rates,
                        name="승률(%)", mode="lines+markers",
                        line=dict(color="#ffd700", width=2),
                        marker=dict(size=7),
                        yaxis="y2",
                        hovertemplate="%{x}<br>승률: %{y:.1f}%<extra></extra>"
                    ))
                    fig_monthly.update_layout(
                        title=f"월별 성과 ({period_label})",
                        barmode="stack",
                        paper_bgcolor="#0f1628", plot_bgcolor="#0f1628",
                        font=dict(color="#8b92a5"),
                        height=320, margin=dict(l=0,r=0,t=40,b=0),
                        xaxis=dict(gridcolor="#1e2540"),
                        yaxis=dict(title="종목 수", gridcolor="#1e2540"),
                        yaxis2=dict(title="승률(%)", overlaying="y", side="right",
                                    range=[0,100], ticksuffix="%", gridcolor="rgba(0,0,0,0)"),
                        legend=dict(orientation="h", y=-0.15),
                    )
                    st.plotly_chart(fig_monthly, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, width='stretch')

                    # 월별 수익률 차트
                    ret_colors = ["#00d4aa" if r >= 0 else "#ff3355" for r in avg_returns]
                    fig_ret = go.Figure()
                    fig_ret.add_trace(go.Bar(
                        x=months, y=avg_returns,
                        name="평균 수익률",
                        marker_color=ret_colors,
                        hovertemplate="%{x}<br>평균: %{y:+.2f}%<extra></extra>"
                    ))
                    fig_ret.add_trace(go.Scatter(
                        x=months, y=total_rets,
                        name="누적 수익률", mode="lines+markers",
                        line=dict(color="#4f8ef7", width=2),
                        marker=dict(size=6),
                        yaxis="y2",
                        hovertemplate="%{x}<br>누적: %{y:+.2f}%<extra></extra>"
                    ))
                    fig_ret.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.15)")
                    fig_ret.update_layout(
                        title="월별 수익률",
                        paper_bgcolor="#0f1628", plot_bgcolor="#0f1628",
                        font=dict(color="#8b92a5"),
                        height=280, margin=dict(l=0,r=0,t=40,b=0),
                        xaxis=dict(gridcolor="#1e2540"),
                        yaxis=dict(title="평균 수익률(%)", gridcolor="#1e2540", ticksuffix="%"),
                        yaxis2=dict(title="누적(%)", overlaying="y", side="right",
                                    ticksuffix="%", gridcolor="rgba(0,0,0,0)"),
                        legend=dict(orientation="h", y=-0.15),
                    )
                    st.plotly_chart(fig_ret, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, width='stretch')

                    # 월별 테이블
                    st.markdown("<div class='sec-title'>📋 월별 상세</div>", unsafe_allow_html=True)
                    month_rows = []
                    for m in reversed(monthly):
                        closed_cnt = m["wins"] + m["losses"]
                        wr_str = f"{m['win_rate']:.1f}%" if closed_cnt > 0 else "-"
                        ar_str = f"{m['avg_return']:+.2f}%" if closed_cnt > 0 else "-"
                        tr_str = f"{m['total_return']:+.2f}%" if closed_cnt > 0 else "-"
                        month_rows.append({
                            "월":        m["month"],
                            "알림 수":   m["total"],
                            "목표달성":  m["wins"],
                            "손절":      m["losses"],
                            "만료":      m["expired"],
                            "승률":      wr_str,
                            "평균수익률": ar_str,
                            "합산수익률": tr_str,
                        })
                    st.dataframe(pd.DataFrame(month_rows), width='stretch', hide_index=True)

        # ── 요약 + 내역 뷰 ────────────────────────────────────
        else:
            perf = get_performance_summary(d_from, d_to)
            if perf["total"] > 0:
                c1, c2, c3, c4, c5 = st.columns(5)
                metric_card(c1, "청산 종목", f"{perf['total']}개")
                metric_card(c2, "목표가 달성", f"{perf['win']}개")
                metric_card(c3, "손절 발생", f"{perf['loss']}개")
                win_color = "#00d4aa" if perf['win_rate'] >= 50 else "#ff3355"
                c4.markdown(f"""<div class='metric-card'>
                  <div class='lbl'>승률</div>
                  <div class='val' style='color:{win_color};'>{perf['win_rate']}%</div>
                </div>""", unsafe_allow_html=True)
                ret_color = "#00d4aa" if perf['avg_return'] >= 0 else "#ff3355"
                c5.markdown(f"""<div class='metric-card'>
                  <div class='lbl'>평균 수익률</div>
                  <div class='val' style='color:{ret_color};'>{perf['avg_return']:+.1f}%</div>
                </div>""", unsafe_allow_html=True)

                if perf['win'] > 0 or perf['loss'] > 0:
                    st.markdown(f"""<div class='cond-box' style='margin-top:8px;'>
                      평균 수익: <b style='color:#00d4aa;'>{perf['avg_win']:+.1f}%</b> &nbsp;|&nbsp;
                      평균 손실: <b style='color:#ff3355;'>{perf['avg_loss']:+.1f}%</b> &nbsp;|&nbsp;
                      진입 모니터링: <b style='color:#4f8ef7;'>{perf.get('active',0)}개</b> &nbsp;|&nbsp;
                      매수가 대기: <b style='color:#8b92a5;'>{perf.get('pending',0)}개</b> &nbsp;|&nbsp;
                      만료: <b style='color:#8b92a5;'>{perf['expired']}개</b>
                    </div>""", unsafe_allow_html=True)

                # ── 수익률 곡선 차트 ──────────────────────────
                history_all = get_alert_history_range(d_from, d_to, 500)
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
                        hovertemplate="%{text}<br>누적: %{y:+.1f}%<extra></extra>",
                        fill="tozeroy",
                        fillcolor="rgba(79,142,247,0.08)"
                    ))
                    fig_perf.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.2)")
                    fig_perf.update_layout(
                        title=f"누적 수익률 곡선 ({period_label})",
                        paper_bgcolor="#0f1628", plot_bgcolor="#0f1628",
                        font=dict(color="#8b92a5"),
                        height=280, margin=dict(l=0,r=0,t=40,b=0),
                        xaxis=dict(gridcolor="#1e2540"),
                        yaxis=dict(gridcolor="#1e2540", ticksuffix="%"),
                    )
                    st.plotly_chart(fig_perf, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, width='stretch')
            else:
                st.info("해당 기간에 성과 데이터가 없어요.")

            # ── 상세 내역 ──────────────────────────────────────
            history = get_alert_history_range(d_from, d_to, 200)
            if history:
                st.markdown("<div class='sec-title'>📋 알림 내역</div>", unsafe_allow_html=True)

                status_filter = st.selectbox("상태 필터", ["전체", "매수대기", "진입중", "목표달성", "손절", "만료"], key="perf_filter")
                status_map = {"전체": None, "매수대기": "pending", "진입중": "active", "목표달성": "hit_target", "손절": "hit_stop", "만료": "expired"}
                filtered = [h for h in history if status_map[status_filter] is None or h["status"] == status_map[status_filter]]

                rows = []
                for h in filtered:
                    status_emoji = {"pending": "⏳ 매수대기", "active": "🔵 진입중", "hit_target": "✅ 목표달성", "hit_stop": "🛑 손절", "expired": "⏰ 만료"}.get(h["status"], h["status"])
                    ret_str = f"{h['return_pct']:+.1f}%" if h["return_pct"] is not None else "-"
                    ret_color_str = "🟢" if (h["return_pct"] or 0) > 0 else "🔴" if (h["return_pct"] or 0) < 0 else "⚪"
                    rows.append({
                        "날짜":    h["alert_date"],
                        "종목명":  h["name"],
                        "점수":    h["score"],
                        "매수가":  f"₩{h['entry_price']:,.0f}" if h["entry_price"] else "-",
                        "목표가":  f"₩{h['target_price']:,.0f}" if h["target_price"] else "-",
                        "손절가":  f"₩{h['stop_price']:,.0f}" if h["stop_price"] else "-",
                        "손익비":  f"{h['rr_ratio']:.1f}:1" if h["rr_ratio"] else "-",
                        "상태":    status_emoji,
                        "수익률":  f"{ret_color_str} {ret_str}",
                        "청산일":  h["exit_date"] or "-",
                    })
                st.dataframe(pd.DataFrame(rows),
                    column_config={
                        "점수": st.column_config.ProgressColumn("점수", min_value=0, max_value=50, format="%d점"),
                    },
                    width='stretch', hide_index=True)
            else:
                st.info("해당 기간에 알림 내역이 없습니다.")

    except Exception as e:
        if "unable to open database" in str(e) or "no such file" in str(e).lower():
            st.info("성과 데이터는 스케줄러 서버에서만 접근 가능합니다. 텔레그램 알림으로 확인해주세요.")
        else:
            st.error(f"성과 추적 오류: {e}")

# ── 하단 면책조항 ─────────────────────────────────────────────────
st.markdown("---")

# 텔레그램 알림 사이드바 버튼
with st.sidebar:
    st.markdown("---")
    st.markdown("### 📲 텔레그램 알림")
    st.button("🔔 지금 알림 전송", width='stretch', disabled=True)
    st.button("🧪 연결 테스트", width='stretch', disabled=True)
st.markdown("""
<div style='text-align:center;color:#555;font-size:11px;padding:10px 0 20px;'>
⚠️ 본 서비스는 투자 참고용 정보 제공 목적이며, 투자 권유가 아닙니다.<br>
주식 투자는 원금 손실 위험이 있으며, 모든 투자 결정과 책임은 투자자 본인에게 있습니다.
</div>
""", unsafe_allow_html=True)
