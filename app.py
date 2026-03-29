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
    # 스케줄러 시작 (앱 최초 로드 시 1회)
    if "scheduler_started" not in st.session_state:
        start_scheduler()
        st.session_state["scheduler_started"] = True
except Exception as e:
    st.warning(f"캐시/백테스트 모듈 로드 실패: {e}")

# ── 접근 제어 ────────────────────────────────────────────────────
PASSWORDS = ["hotstock2026", "vip1234", "comfreec"]  # 허가된 비밀번호 목록

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
        <div class='rocket-icon'>🚀</div>
        <h2 style='color:#fff;margin:16px 0 6px;font-size:26px;font-weight:800;letter-spacing:-0.5px;'>주식 급등 예측</h2>
        <p style='color:#4f8ef7;font-size:13px;margin:0 0 32px;font-weight:500;letter-spacing:2px;'>STOCK SURGE PREDICTOR</p>
        <div style='width:40px;height:2px;background:linear-gradient(90deg,#4f8ef7,#00d4aa);margin:0 auto 32px;border-radius:2px;'></div>
        <p style='color:#8b92a5;font-size:13px;margin:0 0 24px;'>허가된 사용자만 접근 가능합니다</p>
      </div>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        pw = st.text_input("", type="password", placeholder="🔑  비밀번호 입력", label_visibility="collapsed")
        if st.button("로그인", type="primary", use_container_width=True):
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

st.set_page_config(page_title="한국 주식 급등 예측", page_icon="🚀", layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
/* ── 뷰포트 ── */
@viewport { width: device-width; }

/* ── 기본 레이아웃 ── */
.main .block-container {
    padding: 0.5rem 0.5rem !important;
    max-width: 100% !important;
}
/* Streamlit 내부 여백 제거 */
.main > div:first-child {
    padding-left: 0 !important;
    padding-right: 0 !important;
}
section[data-testid="stSidebar"] {
    min-width: 240px !important;
    max-width: 260px !important;
}

/* ── 모바일: 사이드바 항상 표시 (숨기지 않음) ── */
@media (max-width: 768px) {
    .main .block-container { padding: 0.3rem 0.3rem !important; }
    h1 { font-size: 18px !important; }
    h3 { font-size: 14px !important; }
    .metric-card { padding: 8px 4px !important; margin: 2px !important; }
    .metric-card .val { font-size: 14px !important; }
    .metric-card .lbl { font-size: 10px !important; }
    .rank-card { padding: 8px 10px !important; }
    .stButton > button { font-size: 12px !important; padding: 6px 4px !important; }
    .stDataFrame { overflow-x: auto !important; -webkit-overflow-scrolling: touch !important; }
    .stDataFrame table { min-width: 600px !important; }
    .top-header { padding: 12px 14px !important; }
    /* 탭 버튼 모바일 줄바꿈 */
    div[data-testid="column"] > div > div > button {
        font-size: 11px !important;
        padding: 6px 2px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    /* 가격 레벨 박스 세로 배치 */
    .price-levels-wrap { flex-direction: column !important; }
}

/* ── 태블릿 (1024px 이하) ── */
@media (max-width: 1024px) and (min-width: 769px) {
    .metric-card .val { font-size: 18px !important; }
    .main .block-container { padding: 0.4rem 0.6rem !important; }
}

/* ── 공통 컴포넌트 ── */
.top-header{background:linear-gradient(135deg,#1a1f35,#0e1117);padding:24px 32px;
  border-radius:16px;margin-bottom:20px;border:1px solid #2d3555;}
.metric-card{background:linear-gradient(135deg,#1e2130,#262b3d);border:1px solid #3d4466;
  border-radius:12px;padding:16px;text-align:center;margin:4px;}
.metric-card .lbl{color:#8b92a5;font-size:12px;}
.metric-card .val{color:#fff;font-size:22px;font-weight:700;}
.rank-card{background:linear-gradient(135deg,#1a1f35,#1e2540);border-left:4px solid #4f8ef7;
  border-radius:10px;padding:14px 18px;margin:8px 0;}
.rank-card.gold{border-left-color:#ffd700;}
.rank-card.silver{border-left-color:#c0c0c0;}
.rank-card.bronze{border-left-color:#cd7f32;}
.bar-bg{background:#1e2130;border-radius:8px;height:8px;width:100%;}
.bar-fill{background:linear-gradient(90deg,#4f8ef7,#00d4aa);border-radius:8px;height:8px;}
.sec-title{font-size:clamp(15px,3vw,20px);font-weight:700;color:#e0e6f0;margin:20px 0 10px;
  padding-bottom:6px;border-bottom:2px solid #2d3555;}
.cond-box{background:#1a1f35;border:1px solid #2d3555;border-radius:10px;
  padding:12px 16px;margin-bottom:12px;font-size:13px;color:#8b92a5;}

/* 차트 영역 터치 스크롤 허용 */
.js-plotly-plot, .plotly, .plot-container {
    touch-action: pan-y !important;
}
.stPlotlyChart {
    touch-action: pan-y !important;
}
</style>""", unsafe_allow_html=True)

# 차트 터치 스크롤 허용 JS
st.markdown("""
<script>
(function() {
    function fixScroll() {
        // plotly 내부 SVG와 드래그 레이어에 touch-action 강제 적용
        document.querySelectorAll('.js-plotly-plot, .js-plotly-plot *, .plotly, .nsewdrag, .drag').forEach(el => {
            el.style.touchAction = 'pan-y';
        });
    }
    const obs = new MutationObserver(fixScroll);
    obs.observe(document.body, {childList: true, subtree: true});
    setInterval(fixScroll, 1000);
})();
</script>
""", unsafe_allow_html=True)

st.markdown("""<div class="top-header">
  <h1 style="color:#fff;margin:0;font-size:clamp(18px,4vw,30px);">🚀 한국 주식 급등 예측 시스템 v3.0</h1>
  <p style="color:#8b92a5;margin:6px 0 0;font-size:13px;">
    240일선 아래 충분한 조정 → 최근 돌파 → 현재 근처 → 급등 신호 복합 확인
  </p>
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
    return f'<svg width="{w}" height="{h}" style="display:inline-block;vertical-align:middle;"><polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.5"/></svg>'

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
    <div style='background:#1e2130;border:1px solid #2d3555;border-radius:10px;
         padding:10px 14px;text-align:center;'>
      <div style='color:#8b92a5;font-size:11px;'>{name}</div>
      <div style='color:#fff;font-size:18px;font-weight:700;'>{val:,.2f}</div>
      <div style='color:{color};font-size:13px;'>{arrow} {abs(chg):.2f}%</div>
    </div>""", unsafe_allow_html=True)

if fear_score is not None:
    cols_m[2].markdown(f"""
    <div style='background:#1e2130;border:1px solid #2d3555;border-radius:10px;
         padding:10px 14px;text-align:center;'>
      <div style='color:#8b92a5;font-size:11px;'>공포/탐욕 지수</div>
      <div style='color:{fear_color};font-size:18px;font-weight:700;'>{fear_score}</div>
      <div style='color:{fear_color};font-size:12px;'>{fear_label}</div>
    </div>""", unsafe_allow_html=True)

cols_m[3].markdown(f"""
    <div style='background:#1e2130;border:1px solid #2d3555;border-radius:10px;
         padding:10px 14px;text-align:right;'>
      <div style='color:#8b92a5;font-size:11px;'>기준시각 (1~2분 지연)</div>
      <div style='color:#e0e6f0;font-size:16px;font-weight:700;'>{now}</div>
    </div>""", unsafe_allow_html=True)

# ── 상단 메뉴 탭 ─────────────────────────────────────────────────
if "mode" not in st.session_state:
    st.session_state["mode"] = "🔍 급등 예고 종목 탐지"

tab_labels = ["🔍 급등 예고 종목 탐지", "🎯 최적 급등 타이밍", "📈 개별 종목 분석", "⭐ 즐겨찾기", "📊 백테스트"]
tab_cols = st.columns(5)
for i, (col, label) in enumerate(zip(tab_cols, tab_labels)):
    active = st.session_state["mode"] == label
    if col.button(label, key=f"tab_{i}", use_container_width=True,
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
    st.markdown("### ⚙️ 핵심 조건 설정")

    if "max_gap"   not in st.session_state: st.session_state["max_gap"]   = 15
    if "min_below" not in st.session_state: st.session_state["min_below"] = 120
    if "max_cross" not in st.session_state: st.session_state["max_cross"] = 120
    if "min_score" not in st.session_state: st.session_state["min_score"] = 10

    if st.button("⚡ 최적 셋팅", use_container_width=True):
        st.session_state["max_gap"]   = 15   # 240선 근처 15% 이내
        st.session_state["min_below"] = 120  # 최소 6개월 조정
        st.session_state["max_cross"] = 120  # 돌파 후 6개월 이내
        st.session_state["min_score"] = 10   # 종합점수 10점 이상
        st.rerun()

    max_gap   = st.slider("📍 240선 근처 범위 (%)", 1, 20, key="max_gap",
        help="현재가가 240일선 위 몇 % 이내인지 (작을수록 엄격)")
    min_below = st.slider("📉 최소 조정 기간 (일)", 60, 300, key="min_below",
        help="240일선 아래 최소 체류 일수 (120=6개월, 240=1년)")
    max_cross = st.slider("📈 돌파 후 최대 경과 (일)", 10, 180, key="max_cross",
        help="240일선 돌파 후 최대 경과 일수")
    min_score = st.slider("🎯 최소 종합점수", 0, 20, key="min_score",
        help="이 점수 이상인 종목만 표시 (0=전체, 높을수록 엄격)")
    st.markdown("---")
    st.markdown("""**📊 추가 점수 신호**
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
    """브라우저 localStorage에서 즐겨찾기 로드 (즐겨찾기 탭 진입 시 1회만 호출)"""
    try:
        val = st_javascript("JSON.parse(localStorage.getItem('hotstock_favs') || '{}')")
        if isinstance(val, dict) and val:
            # 기존 session_state와 병합
            existing = st.session_state.get("favorites", {})
            existing.update(val)
            st.session_state["favorites"] = existing
    except:
        pass

def ls_persist_to_browser():
    """즐겨찾기를 localStorage에 동기화 (즐겨찾기 탭에서 호출)"""
    try:
        import json
        favs = st.session_state.get("favorites", {})
        js_str = json.dumps(favs, ensure_ascii=False)
        st_javascript(f"localStorage.setItem('hotstock_favs', JSON.stringify({js_str}))")
    except:
        pass

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
        df = yf.Ticker(symbol).history(period=period)
        return df.dropna(subset=["Open","High","Low","Close"]) if df is not None and len(df) > 0 else None
    except: return None

def metric_card(col, label, value):
    col.markdown(f"""<div class="metric-card">
        <div class="lbl">{label}</div><div class="val">{value}</div>
    </div>""", unsafe_allow_html=True)


def calc_rsi_wilder(close, period=20):
    """Wilder's Smoothing RSI - 이베스트증권 표준 방식
    첫 period일 단순평균으로 시드값, 이후 Wilder smoothing 적용
    """
    d = close.diff()
    gain = d.where(d > 0, 0.0)
    loss = -d.where(d < 0, 0.0)

    avg_gain = gain.copy() * 0.0
    avg_loss = loss.copy() * 0.0

    # 첫 시드값: period일 단순평균
    avg_gain.iloc[period] = gain.iloc[1:period+1].mean()
    avg_loss.iloc[period] = loss.iloc[1:period+1].mean()

    # 이후 Wilder smoothing
    for i in range(period + 1, len(close)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period

    avg_gain.iloc[:period] = float('nan')
    avg_loss.iloc[:period] = float('nan')

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
      <div style='flex:1;background:rgba(100,160,255,0.08);border:1px solid #4a90d9;
           border-radius:10px;padding:12px;text-align:center;'>
        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>📍 매수가</div>
        <div style='color:#a0c4ff;font-size:18px;font-weight:700;margin:4px 0;'>₩{lv["current"]:,.0f}</div>
        <div style='color:#8b92a5;font-size:12px;'>시장가 진입</div>
        <div style='color:#4a5568;font-size:10px;margin-top:4px;'>현재가 기준</div>
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

        # ── 매수가: 현재가 (시장가 기준) ─────────────────────────
        entry = current

        # ── 손절가: Van Tharp 방식 ────────────────────────────────
        # 근거: 스윙 저점(20일) 아래 1.5 ATR = 진짜 추세 붕괴 신호
        # 단순 % 손절보다 변동성 기반이 훨씬 정교함
        swing_low_20 = float(low.tail(20).min())
        stop_atr     = swing_low_20 - atr * 1.5

        # 보조: MA20 아래 1 ATR (지지선 이탈 확인)
        ma20 = float(close.rolling(20).mean().dropna().iloc[-1])
        stop_ma  = ma20 - atr * 1.0

        # 두 손절 중 더 보수적인(높은) 값 선택 → 리스크 최소화
        stop = max(stop_atr, stop_ma)
        # 범위 제한: -4% ~ -12% (너무 타이트/루즈 방지)
        stop = max(stop, current * 0.88)
        stop = min(stop, current * 0.96)
        risk = max(current - stop, current * 0.01)

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
        rr_ratio = (target - current) / (current - stop + 1e-9)
        upside   = (target / current - 1) * 100
        downside = (stop / current - 1) * 100

        # 목표가 수평선 (초록)
        fig.add_hline(y=target, line=dict(color="#00ff88", width=2, dash="dash"))
        fig.add_hrect(y0=current, y1=target, fillcolor="rgba(0,255,136,0.08)", line_width=0)
        # 현재가 수평선 (흰색)
        fig.add_hline(y=current, line=dict(color="#ffffff", width=1.5, dash="dot"))
        # 손절가 수평선 (빨강)
        fig.add_hline(y=stop, line=dict(color="#ff3355", width=2, dash="dash"))
        fig.add_hrect(y0=stop, y1=current, fillcolor="rgba(255,51,85,0.08)", line_width=0)

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
    fig._price_levels = dict(target=target, current=current, entry=entry, stop=stop,
                             upside=upside, downside=downside, rr_ratio=rr_ratio) if show_levels else None
    return fig

# ── 급등 예고 종목 탐지 ──────────────────────────────────────────
if mode == "🔍 급등 예고 종목 탐지":

    # 현재 조건 표시
    st.markdown(f"""<div class="cond-box">
      <b style="color:#e0e6f0;">현재 탐지 조건</b><br>
      📉 240일선 아래 <b style="color:#ffd700;">{min_below}일({min_below//20}개월) 이상</b> 조정 →
      📈 최근 <b style="color:#00d4aa;">{max_cross}일 이내</b> 240일선 상향 돌파 →
      📍 현재 주가 240일선 위 <b style="color:#4f8ef7;">0~{max_gap}%</b> 이내
    </div>""", unsafe_allow_html=True)

    if st.button("🚀 스캔 시작", type="primary", use_container_width=True):
        det = KoreanStockSurgeDetector(max_gap, min_below, max_cross)
        symbols = det.all_symbols
        total = len(symbols)

        st.markdown("<div class='sec-title'>📡 스캔 진행 중...</div>", unsafe_allow_html=True)
        prog_bar  = st.progress(0)
        prog_text = st.empty()

        results = []
        for idx, symbol in enumerate(symbols):
            name_disp = det.all_symbols
            prog_text.markdown(
                f"<span style='color:#8b92a5;font-size:13px;'>"
                f"({idx+1}/{total}) {symbol} 분석 중...</span>",
                unsafe_allow_html=True
            )
            prog_bar.progress((idx + 1) / total)
            r = det.analyze_stock(symbol)
            if r:
                results.append(r)

        prog_bar.empty()
        prog_text.empty()
        results = sorted(results, key=lambda x: x["total_score"], reverse=True)
        results = [r for r in results if r["total_score"] >= min_score]

        # 스캔 결과 session_state에 저장 (즐겨찾기 버튼 클릭 후에도 유지)
        st.session_state["scan_results"] = results

        # DB 캐싱
        try:
            save_scan([{k: v for k, v in r.items() if k not in ("close_series", "rsi_series")} for r in results])
        except:
            pass

    # session_state에서 결과 로드
    results = st.session_state.get("scan_results", [])

    if "scan_results" not in st.session_state:
        pass  # 스캔 전 - 아무것도 표시 안 함
    elif not results:
        st.warning("현재 조건을 만족하는 종목이 없습니다.")
        st.info("💡 사이드바에서 조건을 완화해보세요:\n- '240선 근처 범위'를 늘리거나\n- '최소 조정 기간'을 줄이거나\n- '돌파 후 최대 경과'를 늘려보세요")
    else:
            st.success(f"✅ {len(results)}개 종목이 모든 핵심 조건을 충족합니다!")

            # 요약 카드
            c1,c2,c3,c4 = st.columns(4)
            metric_card(c1, "발견 종목", f"{len(results)}개")
            metric_card(c2, "평균 조정 기간", f"{int(sum(r['below_days'] for r in results)/len(results))}일")
            metric_card(c3, "평균 240선 이격", f"+{sum(r['ma240_gap'] for r in results)/len(results):.1f}%")
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
                    "240일선":    f"₩{r['ma240']:,.0f}",
                    "240선이격":  f"+{r['ma240_gap']:.1f}%",
                    "조정기간":   f"{r['below_days']}일({r['below_days']//20}개월)",
                    "돌파후":     f"{r['days_since_cross']}일",
                    "돌파강도":   f"{r.get('cross_gap_pct', 0):.1f}%",
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
                use_container_width=True, hide_index=True)

            # 차트
            if len(results) > 1:
                fig = px.bar(pd.DataFrame(results), x="name", y="total_score",
                    color="total_score", color_continuous_scale="Greens",
                    labels={"name":"종목명","total_score":"점수"}, title="종합 점수")
                fig.update_layout(paper_bgcolor="#0e1117",plot_bgcolor="#0e1117",
                    font=dict(color="#8b92a5"),xaxis_tickangle=30,
                    coloraxis_showscale=False,height=240,margin=dict(l=5,r=5,t=30,b=50))
                st.plotly_chart(fig, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, use_container_width=True, key="chart_score_bar")

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

                # 스파크라인 + 뉴스
                spark_prices = get_sparkline(r["symbol"])
                spark_svg = make_sparkline(spark_prices, color) if spark_prices else ""
                news = get_news_headline(r["symbol"])
                import html as _html
                news_safe = _html.escape(news) if news else ""
                below_months = r["below_days"] // 20
                # 실시간 가격
                rt_price = get_realtime_price(r["symbol"])
                display_price = rt_price if rt_price else r["current_price"]

                st.markdown(f"""<div class="rank-card {medal}">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                      <span style="font-size:20px;">{icon}</span>
                      <span style="color:#fff;font-size:clamp(14px,3vw,18px);font-weight:700;margin-left:6px;">{r["name"]}</span>
                      <span style="color:#8b92a5;font-size:13px;margin-left:8px;">{r["symbol"]}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:12px;">
                      {spark_svg}
                      <div style="text-align:right;">
                        <span style="color:#fff;font-size:clamp(14px,3vw,20px);font-weight:700;">₩{display_price:,.0f}</span>
                        <span style="color:{color};font-size:14px;margin-left:8px;">{arrow} {abs(r["price_change_1d"]):.2f}%</span>
                      </div>
                    </div>
                  </div>
                  <div style="margin-top:6px;color:#8b92a5;font-size:12px;">
                    240일선 ₩{r["ma240"]:,.0f} | 이격 +{r["ma240_gap"]:.1f}% |
                    조정 {r["below_days"]}일({below_months}개월) | 돌파 {r["days_since_cross"]}일 전 | 돌파강도 {r.get("cross_gap_pct",0):.1f}% |
                    수급 {"🔥기관+외국인" if r.get("both_buying") else ("✅수급있음" if r.get("smart_money_in") else "❌수급없음")} | 핵심신호 {r.get("core_signal_count",0)}개
                  </div>
                </div>""", unsafe_allow_html=True)
                # 즐겨찾기 버튼 (localStorage 기반 - 기기별 영구 저장)
                _fav_col, _news_col = st.columns([1, 5])
                _favs = ls_get_favorites()
                _is_fav = r["symbol"] in _favs
                _fav_label = "⭐ 즐겨찾기 해제" if _is_fav else "☆ 즐겨찾기"
                if _fav_col.button(_fav_label, key=f"fav_{r['symbol']}_{i}", use_container_width=True):
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
                    m2.metric("240선 이격", f"+{r['ma240_gap']:.1f}%")
                    m3.metric("조정 기간", f"{r['below_days']}일")
                    m4.metric("돌파 후", f"{r['days_since_cross']}일")
                    m5.metric("돌파강도", f"{r.get('cross_gap_pct',0):.1f}%")
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
                    if r["below_days"] >= 240:          active.append(f"⏳ 1년+ 충분한 조정 ({r['below_days']}일)")
                    if s.get("news_sentiment",0) > 0:   active.append(f"📰 긍정 뉴스 {s.get('pos_news',0)}건")
                    if s.get("has_disclosure"):         active.append(f"📋 호재 공시: {', '.join(s.get('disclosure_types',[]))}")

                    cols = st.columns(2)
                    for j, sig in enumerate(active):
                        cols[j%2].success(sig)
                    if not active:
                        st.info("추가 신호 없음 (핵심 조건만 충족)")

                    rsi_s = r["rsi_series"]
                    cd    = get_chart_data(r["symbol"], "2y")
                    if cd is not None:
                        cross_date = r["close_series"].index[-(r["days_since_cross"]+1)]
                        _c1 = make_candle(cd, f"{r['name']} ({r['symbol']})", cross_date=cross_date)
                        st.plotly_chart(_c1, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, use_container_width=True, key=f"candle_{r['symbol']}")
                        show_price_levels(_c1)

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
            det = KoreanStockSurgeDetector(max_gap, min_below, max_cross)
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
            metric_card(c2,"240선 이격",f"+{result['ma240_gap']:.1f}%")
            metric_card(c3,"조정 기간",f"{result['below_days']}일({result['below_days']//20}개월)")
            metric_card(c4,"돌파 후",f"{result['days_since_cross']}일")

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
                (result["below_days"] >= 240,    f"⏳ 1년+ 충분한 조정 ({result['below_days']}일)"),
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

            cross_date = result["close_series"].index[-(result["days_since_cross"]+1)]
            _c2 = make_candle(data, f"{name} ({symbol})", cross_date=cross_date)
            st.plotly_chart(_c2, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, use_container_width=True)
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
            st.plotly_chart(_c3, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, use_container_width=True, key="chart_candle_no_cond")
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

    if st.button("🔍 스캔 시작", type="primary", use_container_width=True):
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
                use_container_width=True, hide_index=True)

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
                        use_container_width=True, key=f"rsi_quality_{r['symbol']}")
                    _c4 = make_candle(r["df"], f"{r['name']} ({r['symbol']})")
                    st.plotly_chart(_c4, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, use_container_width=True, key=f"candle_quality_{r['symbol']}")
                    show_price_levels(_c4)


# ── 최적 급등 타이밍 탐지 ────────────────────────────────────────
elif mode == "🎯 최적 급등 타이밍":

    st.markdown("""
    <div style='background:linear-gradient(135deg,#1a1f35,#0e1117);
         padding:20px 24px;border-radius:12px;margin-bottom:16px;border:1px solid #2d3555;'>
      <h3 style='color:#fff;margin:0;'>🎯 최적 급등 타이밍 탐지 시스템</h3>
      <p style='color:#8b92a5;margin:8px 0 0;font-size:13px;'>
        8가지 핵심 조건이 동시에 겹치는 순간을 포착합니다.<br>
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
        """최적 급등 타이밍 종합 점수 계산"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="2y")
            if df is None or len(df) < 60:
                return None

            # ── 재무 필터 (급등 탐지와 동일 기준) ───────────────
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

            # ── 이동평균 ──────────────────────────────────────────
            ma5   = close.rolling(5).mean()
            ma20  = close.rolling(20).mean()
            ma60  = close.rolling(60).mean()
            ma120 = close.rolling(120).mean()
            ma240 = close.rolling(240).mean() if n >= 240 else None

            current = float(close.iloc[-1])
            prev    = float(close.iloc[-2])
            chg     = (current - prev) / prev * 100

            # ── [조건1] 충분한 조정 후 바닥 다지기 ──────────────
            # 최근 120일 저점 대비 현재 위치 + 저점에서 반등 중
            low_120  = float(close.tail(120).min())
            high_120 = float(close.tail(120).max())
            recovery = (current - low_120) / (high_120 - low_120 + 1e-9)
            # 저점에서 반등 중인 구간 (0~80%)
            signals["recovery_zone"] = 0.10 <= recovery <= 0.50
            signals["recovery_pct"]  = round(recovery * 100, 1)
            if 0.10 <= recovery <= 0.30: score += 4  # 초기 반등 (최적)
            elif 0.30 < recovery <= 0.50: score += 2  # 중간 반등

            # ── [조건2] 세력 매집 신호 ───────────────────────────
            # OBV 상승 + 최근 20일 가격 변화 < 거래량 변화 (매집 패턴)
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
            # OBV는 오르는데 가격은 횡보 = 매집
            signals["accumulation"] = obv_20_chg > 0.03 and abs(price_20_chg) < 0.08
            signals["obv_rising"]   = obv_20_chg > 0
            if signals["accumulation"]: score += 3
            elif signals["obv_rising"]: score += 1

            # ── [조건3] 볼린저밴드 수축 ──────────────────────────
            bb_std = close.rolling(20).std()
            bb_mid = close.rolling(20).mean()
            bb_w   = (4 * bb_std) / bb_mid.replace(0, np.nan)
            bb_w_min_60 = float(bb_w.tail(60).min())
            bb_w_now    = float(bb_w.iloc[-1])
            bb_w_prev5  = float(bb_w.iloc[-5])
            # 현재 BB폭이 60일 최저점 근처 (수축 중)
            signals["bb_squeeze"]    = bb_w_now <= bb_w_min_60 * 1.2
            # 수축 후 확장 시작
            signals["bb_expanding"]  = bb_w_now > bb_w_prev5 * 1.03
            signals["bb_width"]      = round(bb_w_now, 4)
            if signals["bb_squeeze"] and signals["bb_expanding"]: score += 3
            elif signals["bb_squeeze"]:                           score += 2

            # ── [조건4] RSI 바닥 사이클 ──────────────────────────
            rsi = calc_rsi_wilder(close, 20)
            cur_rsi = float(rsi.iloc[-1])
            signals["rsi"] = round(cur_rsi, 1)

            # RSI 30 이하 → 30 돌파 → 현재 40~60 (건강한 상승 초기)
            rsi_90 = rsi.tail(90).dropna()
            had_below30  = (rsi_90 < 30).any()
            crossed_30   = ((rsi_90.shift(1) <= 30) & (rsi_90 > 30)).any()
            rsi_healthy  = 40 <= cur_rsi <= 65
            signals["rsi_cycle"]   = had_below30 and crossed_30 and rsi_healthy
            signals["rsi_healthy"] = rsi_healthy
            if signals["rsi_cycle"]:   score += 3
            elif rsi_healthy:          score += 1

            # ── [조건5] 이평선 정배열 ────────────────────────────
            ma_align_full = (not pd.isna(ma60.iloc[-1]) and
                             float(ma5.iloc[-1]) > float(ma20.iloc[-1]) > float(ma60.iloc[-1]))
            ma_align_forming = (float(ma5.iloc[-1]) > float(ma20.iloc[-1]) and
                                float(ma20.iloc[-1]) > float(ma60.iloc[-1]) * 0.98)
            signals["ma_align"]         = ma_align_full
            signals["ma_align_forming"] = ma_align_forming
            if ma_align_full:    score += 3
            elif ma_align_forming: score += 1

            # ── [조건6] MACD 골든크로스 ──────────────────────────
            macd   = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
            macd_s = macd.ewm(span=9, adjust=False).mean()
            macd_hist = macd - macd_s
            # 히스토그램 0선 상향 돌파 or 직전 (음→양 전환)
            signals["macd_cross"]    = bool(macd_hist.iloc[-1] > 0 and macd_hist.iloc[-2] <= 0)
            signals["macd_positive"] = bool(macd_hist.iloc[-1] > 0)
            signals["macd_rising"]   = bool(macd_hist.iloc[-1] > macd_hist.iloc[-3])
            if signals["macd_cross"]:    score += 2
            elif signals["macd_rising"] and signals["macd_positive"]: score += 1

            # ── [조건7] 장대양봉 + 거래량 급증 ──────────────────
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

            # ── [조건8] 52주 신고가 돌파 직전 ───────────────────
            high_52w = float(high.tail(252).max())
            high_ratio = current / high_52w
            near_high  = high_ratio >= 0.92  # 52주 고점 8% 이내
            at_high    = high_ratio >= 0.98  # 돌파 직전
            signals["near_52w_high"] = near_high
            signals["high_ratio"]    = round(high_ratio * 100, 1)
            if at_high:   score += 3
            elif near_high: score += 2

            # ── 보너스: 240일선 돌파 후 근처 + 강화된 조건 ────────
            if ma240 is not None and not pd.isna(ma240.iloc[-1]):
                ma240_v = float(ma240.iloc[-1])
                ma240_gap = (current - ma240_v) / ma240_v * 100
                signals["ma240_gap"] = round(ma240_gap, 1)

                if 0 <= ma240_gap <= 10:
                    # 가짜 돌파 방지: 최근 3일 연속 240선 위 유지 확인
                    days_above = sum(1 for i in range(-3, 0) if float(close.iloc[i]) > float(ma240.iloc[i]))
                    signals["ma240_confirmed"] = days_above >= 3

                    # 240선 기울기: 수평 또는 상승 전환 중이어야 함
                    ma240_slope = (float(ma240.iloc[-1]) - float(ma240.iloc[-20])) / float(ma240.iloc[-20]) * 100 if n >= 20 else 0
                    signals["ma240_slope"] = round(ma240_slope, 2)
                    signals["ma240_healthy_slope"] = ma240_slope >= -1.5

                    # 돌파 후 240선 재이탈 없음 확인 (최근 60일 기준)
                    cross_found = False
                    broke_below = False
                    for i in range(n-2, max(n-61, 0), -1):
                        if float(close.iloc[i]) > float(ma240.iloc[i]) and float(close.iloc[i-1]) <= float(ma240.iloc[i-1]):
                            cross_found = True
                            # 돌파 이후 재이탈 체크
                            broke_below = any(float(close.iloc[j]) < float(ma240.iloc[j]) for j in range(i+1, n))
                            break
                    signals["ma240_no_rebreak"] = cross_found and not broke_below

                    if signals["ma240_confirmed"] and signals["ma240_healthy_slope"] and signals["ma240_no_rebreak"]:
                        score += 4  # 모든 조건 충족 = 강한 신호
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
                "max_score":     30,  # 만점 업데이트 (240선 보너스 4점 추가)
                "signals":       signals,
                "rsi":           cur_rsi,
                "rsi_series":    rsi,
                "df":            df,
            }
        except Exception:
            return None

    if st.button("🚀 최적 타이밍 스캔", type="primary", use_container_width=True):
        from stock_surge_detector import ALL_SYMBOLS as SCAN_SYMBOLS

        results = []
        prog      = st.progress(0)
        prog_text = st.empty()
        total     = len(SCAN_SYMBOLS)

        for idx, symbol in enumerate(SCAN_SYMBOLS):
            prog_text.markdown(f"<span style='color:#8b92a5;font-size:13px;'>({idx+1}/{total}) {symbol} 분석 중...</span>", unsafe_allow_html=True)
            prog.progress((idx + 1) / total)
            r = calc_surge_timing_score(symbol)
            if r and r["total_score"] >= 12:  # 기준 상향: 7 → 12점
                results.append(r)

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
                use_container_width=True, hide_index=True)

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
                    st.plotly_chart(_c5, config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}, use_container_width=True, key=f"candle_timing_{r['symbol']}")
                    show_price_levels(_c5)
                    st.plotly_chart(
                        make_rsi_chart(r["rsi_series"], cd),
                        config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True},
                        use_container_width=True, key=f"rsi_timing_{r['symbol']}")


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
                                    use_container_width=True, key=f"fav_chart_{sym}")
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
            use_container_width=True, hide_index=True)
    except:
        st.warning("백테스트 모듈을 불러올 수 없습니다.")

    st.markdown("---")
    st.markdown("#### 종목별 백테스트 실행")
    st.caption("선택 종목의 과거 신호 발생 시점 → 20일 후 평균 수익률 계산")

    bt_opts = [f"{v} ({k})" for k, v in sorted(STOCK_NAMES.items(), key=lambda x: x[1])]
    bt_sel  = st.selectbox("종목 선택", bt_opts, key="bt_symbol")
    bt_sym  = bt_sel.split("(")[1].replace(")", "").strip()
    bt_name = bt_sel.split("(")[0].strip()

    if st.button("🔬 백테스트 실행", type="primary"):
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
                    use_container_width=True, hide_index=True)

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
                st.dataframe(hist_df, use_container_width=True, hide_index=True)
    except:
        st.info("히스토리 기능을 사용하려면 먼저 스캔을 실행하세요.")

# ── 하단 면책조항 ─────────────────────────────────────────────────
st.markdown("---")

# 텔레그램 알림 사이드바 버튼
with st.sidebar:
    st.markdown("---")
    st.markdown("### 📲 텔레그램 알림")
    if st.button("🔔 지금 알림 전송", use_container_width=True):
        try:
            from telegram_alert import send_scan_alert, send_test_alert
            scan_res = st.session_state.get("scan_results", [])
            if scan_res:
                send_scan_alert(scan_res)
                st.success("✅ 텔레그램 전송 완료!")
            else:
                st.warning("스캔 결과가 없어요. 먼저 스캔을 실행하세요.")
        except Exception as e:
            st.error(f"전송 실패: {e}")
    if st.button("🧪 연결 테스트", use_container_width=True):
        try:
            from telegram_alert import send_test_alert
            ok = send_test_alert()
            st.success("✅ 연결 성공!" if ok else "❌ 전송 실패")
        except Exception as e:
            st.error(f"오류: {e}")
st.markdown("""
<div style='text-align:center;color:#555;font-size:11px;padding:10px 0 20px;'>
⚠️ 본 서비스는 투자 참고용 정보 제공 목적이며, 투자 권유가 아닙니다.<br>
주식 투자는 원금 손실 위험이 있으며, 모든 투자 결정과 책임은 투자자 본인에게 있습니다.
</div>
""", unsafe_allow_html=True)
