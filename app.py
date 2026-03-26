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
    padding: 0.5rem 0.8rem !important;
    max-width: 100% !important;
}
section[data-testid="stSidebar"] {
    min-width: 240px !important;
    max-width: 260px !important;
}

/* ── 모바일 (768px 이하) ── */
@media (max-width: 768px) {
    /* 사이드바 숨김 → 상단 햄버거로 접근 */
    section[data-testid="stSidebar"] { display: none !important; }
    .main .block-container { padding: 0.3rem 0.3rem !important; }

    /* 폰트 크기 */
    h1 { font-size: 18px !important; }
    h3 { font-size: 14px !important; }
    p, span, div { font-size: 13px !important; }

    /* 카드 */
    .metric-card { padding: 10px 6px !important; margin: 2px !important; }
    .metric-card .val { font-size: 15px !important; }
    .metric-card .lbl { font-size: 10px !important; }
    .rank-card { padding: 8px 10px !important; }

    /* 버튼 */
    .stButton > button { font-size: 14px !important; padding: 8px !important; }

    /* 데이터프레임 스크롤 */
    .stDataFrame { overflow-x: auto !important; }

    /* 상단 헤더 */
    .top-header { padding: 14px 16px !important; }
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
</style>""", unsafe_allow_html=True)

st.markdown("""<div class="top-header">
  <h1 style="color:#fff;margin:0;font-size:clamp(18px,4vw,30px);">🚀 한국 주식 급등 예측 시스템 v3.0</h1>
  <p style="color:#8b92a5;margin:6px 0 0;font-size:13px;">
    240일선 아래 충분한 조정 → 최근 돌파 → 현재 근처 → 급등 신호 복합 확인
  </p>
</div>""", unsafe_allow_html=True)

# ── 사이드바: 조건 설정 ──────────────────────────────────────────
with st.sidebar:
    mode = st.selectbox("화면", ["🎯 최적 급등 타이밍", "🔍 급등 예고 종목 탐지", "📈 개별 종목 분석"],
                        label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### ⚙️ 핵심 조건 설정")
    max_gap = st.slider("📍 240선 근처 범위 (%)", 1, 20, 15,
        help="현재가가 240일선 위 몇 % 이내인지 (작을수록 엄격)")
    min_below = st.slider("📉 최소 조정 기간 (일)", 60, 300, 90,
        help="240일선 아래 최소 체류 일수 (120=6개월, 240=1년)")
    max_cross = st.slider("📈 돌파 후 최대 경과 (일)", 10, 180, 180,
        help="240일선 돌파 후 최대 경과 일수")
    st.markdown("---")
    st.markdown("""**📊 추가 점수 신호**
| 신호 | 점수 |
|------|------|
| 📦 돌파 시 거래량 급증 | 3점 |
| 📊 최근 거래량 증가 | 2점 |
| 📈 OBV 지속 상승 | 2점 |
| ⚡ 이평선 정배열 | 3점 |
| 🔄 눌림목 후 재상승 | 2점 |
| 💚 RSI 건강 구간 | 2점 |
| 🔥 BB수축→확장 | 3점 |
| 📊 MACD 크로스 | 2점 |
| 🔼 240선 상승 전환 | 3점 |
| 🕯 캔들 패턴 | 1~2점 |
| ⏳ 조정 기간 가산 | 1~3점 |
| 📰 긍정 뉴스 | 1~2점 |
| 📋 호재 공시 | 2점 |""")
    st.markdown("---")
    st.caption("⚠️ 투자 손실에 책임지지 않습니다")

# ── 캐시 함수 ────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_chart_data(symbol, period="2y"):
    try: return yf.Ticker(symbol).history(period=period)
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
    fig.add_trace(go.Candlestick(
        x=data.index, open=data["Open"], high=data["High"],
        low=data["Low"], close=data["Close"], name="주가",
        increasing_line_color="#00d4aa", decreasing_line_color="#ff4b6e"))
    fig.add_trace(go.Bar(x=data.index, y=data["Volume"], name="거래량",
        yaxis="y2", opacity=0.2, marker_color="#4f8ef7"))
    for w,c,nm in [(20,"#ffd700","MA20"),(60,"#ff8c42","MA60"),(240,"#ff4b6e","MA240")]:
        ma = data["Close"].rolling(w).mean()
        fig.add_trace(go.Scatter(x=data.index, y=ma, name=nm,
            line=dict(color=c, width=2 if w==240 else 1.2)))
    if cross_date is not None:
        try:
            cd_ts = pd.Timestamp(cross_date).timestamp() * 1000
            fig.add_vline(x=cd_ts,
                line=dict(color="#00d4aa", dash="dot", width=2),
                annotation_text="240선 돌파", annotation_font_color="#00d4aa")
        except:
            pass

    if show_levels:
        current  = float(data["Close"].iloc[-1])
        ma20_now = float(data["Close"].rolling(20).mean().iloc[-1])

        # 목표가: 52주 고점
        target   = float(data["High"].tail(252).max())
        # 손절가: 최근 10일 저점 vs MA20 중 낮은 값, 단 현재가 -3% 이상
        raw_stop = min(float(data["Low"].tail(10).min()), ma20_now)
        stop     = min(raw_stop, current * 0.97)
        rr_ratio = (target - current) / (current - stop + 1e-9)

        upside   = (target / current - 1) * 100
        downside = (stop / current - 1) * 100

        # ── 목표가 (굵은 초록 실선 + 배경) ──
        fig.add_hline(y=target,
            line=dict(color="#00ff88", width=3),
            annotation=dict(
                text=f"  🎯 목표가  ₩{target:,.0f}  (+{upside:.1f}%)",
                font=dict(color="#00ff88", size=13, family="Arial Black"),
                bgcolor="rgba(0,255,136,0.15)",
                bordercolor="#00ff88", borderwidth=1,
                xanchor="left", x=0.01
            ))
        fig.add_hrect(y0=current, y1=target,
            fillcolor="rgba(0,255,136,0.08)", line_width=0)

        # ── 현재가 (흰색 굵은 점선) ──
        fig.add_hline(y=current,
            line=dict(color="#ffffff", width=2, dash="dot"),
            annotation=dict(
                text=f"  📍 진입가  ₩{current:,.0f}",
                font=dict(color="#ffffff", size=12, family="Arial Black"),
                bgcolor="rgba(255,255,255,0.12)",
                bordercolor="#ffffff", borderwidth=1,
                xanchor="left", x=0.01
            ))

        # ── 손절가 (굵은 빨간 실선 + 배경) ──
        fig.add_hline(y=stop,
            line=dict(color="#ff3355", width=3),
            annotation=dict(
                text=f"  🛑 손절가  ₩{stop:,.0f}  ({downside:.1f}%)  |  손익비 {rr_ratio:.1f}:1",
                font=dict(color="#ff3355", size=13, family="Arial Black"),
                bgcolor="rgba(255,51,85,0.15)",
                bordercolor="#ff3355", borderwidth=1,
                xanchor="left", x=0.01
            ))
        fig.add_hrect(y0=stop, y1=current,
            fillcolor="rgba(255,51,85,0.08)", line_width=0)

        # ── 차트 우측에 정보 박스 (annotation) ──
        fig.add_annotation(
            xref="paper", yref="paper",
            x=1.01, y=1.0,
            xanchor="left", yanchor="top",
            text=(
                f"<b style='color:#00ff88'>🎯 목표가</b><br>"
                f"<b style='color:#00ff88'>₩{target:,.0f}</b><br>"
                f"<span style='color:#00ff88'>(+{upside:.1f}%)</span><br>"
                f"<br>"
                f"<b style='color:#ffffff'>📍 현재가</b><br>"
                f"<b style='color:#ffffff'>₩{current:,.0f}</b><br>"
                f"<br>"
                f"<b style='color:#ff3355'>🛑 손절가</b><br>"
                f"<b style='color:#ff3355'>₩{stop:,.0f}</b><br>"
                f"<span style='color:#ff3355'>({downside:.1f}%)</span><br>"
                f"<br>"
                f"<span style='color:#ffd700'>손익비</span><br>"
                f"<b style='color:#ffd700'>{rr_ratio:.1f} : 1</b>"
            ),
            showarrow=False,
            font=dict(size=12),
            align="left",
            bgcolor="rgba(20,25,45,0.92)",
            bordercolor="#3d4466",
            borderwidth=1.5,
            borderpad=10,
        )

    fig.update_layout(
        title=dict(text=title, font=dict(color="#e0e6f0", size=13)),
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font=dict(color="#8b92a5"),
        yaxis=dict(gridcolor="#1e2540", fixedrange=True),
        yaxis2=dict(overlaying="y", side="right", gridcolor="#1e2540", fixedrange=True),
        xaxis=dict(gridcolor="#1e2540", rangeslider_visible=False, fixedrange=True),
        legend=dict(bgcolor="#1e2130", bordercolor="#2d3555"),
        dragmode=False,
        height=420, margin=dict(l=0,r=130,t=40,b=0))
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
            name_disp = det.all_symbols  # 진행 표시용
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

        if not results:
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
                    "등락률":     f"{'🔺' if r['price_change_1d']>0 else '🔻'}{r['price_change_1d']:.2f}%",
                    "240일선":    f"₩{r['ma240']:,.0f}",
                    "240선이격":  f"+{r['ma240_gap']:.1f}%",
                    "조정기간":   f"{r['below_days']}일({r['below_days']//20}개월)",
                    "돌파후":     f"{r['days_since_cross']}일",
                    "RSI":        r["rsi"],
                    "종합점수":   r["total_score"],
                    "거래량":     "✅" if s.get("vol_at_cross") or s.get("recent_vol") else "❌",
                    "OBV":        "✅" if s.get("obv_rising") else "❌",
                    "정배열":     "✅" if s.get("ma_align") else "❌",
                    "BB수축":     "✅" if s.get("bb_squeeze_expand") else "❌",
                    "MACD":       "✅" if s.get("macd_cross") else "❌",
                    "240전환":    "✅" if s.get("ma240_turning_up") else "❌",
                })
            df = pd.DataFrame(rows)
            st.dataframe(df,
                column_config={"종합점수": st.column_config.ProgressColumn(
                    "종합점수", min_value=0, max_value=28, format="%d점"),
                    "RSI": st.column_config.ProgressColumn(
                    "RSI", min_value=0, max_value=100, format="%.1f")},
                use_container_width=True, hide_index=True)

            # 차트
            if len(results) > 1:
                col_a, col_b = st.columns(2)
                with col_a:
                    fig = px.bar(pd.DataFrame(results), x="name", y="total_score",
                        color="total_score", color_continuous_scale="Greens",
                        labels={"name":"종목명","total_score":"점수"}, title="종합 점수")
                    fig.update_layout(paper_bgcolor="#0e1117",plot_bgcolor="#0e1117",
                        font=dict(color="#8b92a5"),xaxis_tickangle=30,
                        coloraxis_showscale=False,height=240,margin=dict(l=5,r=5,t=30,b=50))
                    st.plotly_chart(fig, config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key="chart_score_bar")
                with col_b:
                    fig2 = px.scatter(pd.DataFrame(results), x="ma240_gap", y="below_days",
                        size="total_score", color="total_score", hover_data=["name"],
                        color_continuous_scale="RdYlGn",
                        labels={"ma240_gap":"240선 이격(%)","below_days":"조정기간(일)"},
                        title="이격 vs 조정기간 (크기=점수)")
                    fig2.update_layout(paper_bgcolor="#0e1117",plot_bgcolor="#0e1117",
                        font=dict(color="#8b92a5"),height=240,margin=dict(l=5,r=5,t=30,b=5))
                    st.plotly_chart(fig2, config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key="chart_scatter")

            # 상세 카드
            st.markdown("<div class='sec-title'>🎯 종목별 상세 분석</div>", unsafe_allow_html=True)
            medals = ["gold","silver","bronze"]
            icons  = ["🥇","🥈","🥉"]

            for i, r in enumerate(results):
                medal = medals[i] if i < 3 else "rank-card"
                icon  = icons[i]  if i < 3 else f"{i+1}."
                pct   = r["total_score"] / 28 * 100
                color = "#00d4aa" if r["price_change_1d"] > 0 else "#ff4b6e"
                arrow = "▲" if r["price_change_1d"] > 0 else "▼"

                st.markdown(f"""<div class="rank-card {medal}">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                      <span style="font-size:20px;">{icon}</span>
                      <span style="color:#fff;font-size:clamp(14px,3vw,18px);font-weight:700;margin-left:6px;">{r["name"]}</span>
                      <span style="color:#8b92a5;font-size:13px;margin-left:8px;">{r["symbol"]}</span>
                    </div>
                    <div style="text-align:right;">
                      <span style="color:#fff;font-size:clamp(14px,3vw,20px);font-weight:700;">₩{r["current_price"]:,.0f}</span>
                      <span style="color:{color};font-size:14px;margin-left:8px;">{arrow} {abs(r["price_change_1d"]):.2f}%</span>
                    </div>
                  </div>
                  <div style="margin-top:6px;color:#8b92a5;font-size:12px;">
                    240일선 ₩{r["ma240"]:,.0f} | 이격 +{r["ma240_gap"]:.1f}% |
                    조정 {r["below_days"]}일({r["below_days"]//20}개월) | 돌파 {r["days_since_cross"]}일 전
                  </div>
                  <div style="margin-top:8px;">
                    <div style="color:#8b92a5;font-size:11px;margin-bottom:3px;">종합점수 {r["total_score"]}점</div>
                    <div class="bar-bg"><div class="bar-fill" style="width:{pct}%;"></div></div>
                  </div>
                </div>""", unsafe_allow_html=True)

                with st.expander(f"🔍 {r['name']} 상세 신호 + 주가 차트"):
                    m1,m2,m3,m4 = st.columns(4)
                    m1.metric("RSI(20)", f"{r['rsi']:.1f}")
                    m2.metric("240선 이격", f"+{r['ma240_gap']:.1f}%")
                    m3.metric("조정 기간", f"{r['below_days']}일")
                    m4.metric("돌파 후", f"{r['days_since_cross']}일")

                    s = r["signals"]
                    active = []
                    if s.get("vol_at_cross"):           active.append(f"📦 돌파 시 거래량 급증 ({s['cross_vol_ratio']:.1f}배)")
                    if s.get("recent_vol"):             active.append(f"📊 최근 거래량 증가 ({s['recent_vol_ratio']:.1f}배)")
                    if s.get("obv_rising"):             active.append("📈 OBV 지속 상승 (매집 진행 중)")
                    if s.get("ma_align"):               active.append("⚡ 이평선 정배열 (MA5>MA20>MA60)")
                    if s.get("pullback_recovery"):      active.append("🔄 눌림목 후 재상승")
                    if s.get("rsi_healthy"):            active.append(f"💚 RSI 건강 구간 ({s['rsi']:.1f})")
                    if s.get("bb_squeeze_expand"):      active.append("🔥 볼린저밴드 수축→확장 (폭발 직전)")
                    if s.get("macd_cross"):             active.append("📊 MACD 골든크로스")
                    if s.get("ma240_turning_up"):       active.append("🔼 240일선 하락→상승 전환")
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
                        st.plotly_chart(
                            make_candle(cd, f"{r['name']} ({r['symbol']}) — 2년 차트", cross_date=cross_date),
                            config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key=f"candle_{r['symbol']}")
                        # RSI 차트 (주가 차트와 x축 동일)
                        st.plotly_chart(make_rsi_chart(rsi_s, cd), config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key=f"rsi_detail_{r['symbol']}")

# ── 개별 종목 분석 ───────────────────────────────────────────────
elif mode == "📈 개별 종목 분석":
    st.markdown("<div class='sec-title'>📈 개별 종목 분석</div>", unsafe_allow_html=True)
    opts = [f"{v} ({k})" for k,v in sorted(STOCK_NAMES.items(), key=lambda x:x[1])]
    col1,col2 = st.columns([3,1])
    with col1: sel = st.selectbox("종목 선택", opts)
    with col2: period = st.selectbox("기간", ["6mo","1y","2y"])
    symbol = sel.split("(")[1].replace(")","").strip()
    name   = sel.split("(")[0].strip()

    if st.button("분석", type="primary"):
        with st.spinner(f"{name} 분석 중..."):
            det = KoreanStockSurgeDetector(max_gap, min_below, max_cross)
            result = det.analyze_stock(symbol)
            data = get_chart_data(symbol, period)

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

                # 핵심 지표 카드
                c1,c2,c3,c4 = st.columns(4)
                metric_card(c1,"RSI(20)",f"{result['rsi']:.1f}")
                metric_card(c2,"240선 이격",f"+{result['ma240_gap']:.1f}%")
                metric_card(c3,"조정 기간",f"{result['below_days']}일({result['below_days']//20}개월)")
                metric_card(c4,"돌파 후",f"{result['days_since_cross']}일")

                # 신호 분석
                st.markdown("<div class='sec-title'>📊 신호 분석</div>", unsafe_allow_html=True)
                s = result["signals"]
                active, inactive = [], []
                checks = [
                    (s.get("vol_at_cross"),          f"📦 돌파 시 거래량 급증 ({s.get('cross_vol_ratio',0):.1f}배)"),
                    (s.get("recent_vol"),             f"📊 최근 거래량 증가 ({s.get('recent_vol_ratio',0):.1f}배)"),
                    (s.get("obv_rising"),             "📈 OBV 지속 상승 (매집 진행 중)"),
                    (s.get("ma_align"),               "⚡ 이평선 정배열 (MA5>MA20>MA60)"),
                    (s.get("pullback_recovery"),      "🔄 눌림목 후 재상승"),
                    (s.get("rsi_healthy"),            f"💚 RSI 건강 구간 ({s.get('rsi',0):.1f})"),
                    (s.get("bb_squeeze_expand"),      "🔥 볼린저밴드 수축→확장 (폭발 직전)"),
                    (s.get("macd_cross"),             "📊 MACD 골든크로스"),
                    (s.get("ma240_turning_up"),       "🔼 240일선 하락→상승 전환"),
                    (s.get("hammer"),                 "🔨 망치형 캔들"),
                    (s.get("bullish_engulf"),         "🕯 장악형 캔들"),
                    (result["below_days"] >= 240,     f"⏳ 1년+ 충분한 조정 ({result['below_days']}일)"),
                    (s.get("news_sentiment",0) > 0,   f"📰 긍정 뉴스 {s.get('pos_news',0)}건"),
                    (s.get("has_disclosure"),         f"📋 호재 공시: {', '.join(s.get('disclosure_types',[]))}"),
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

                # 주가 + 240일선 차트
                cross_date = result["close_series"].index[-(result["days_since_cross"]+1)]
                st.plotly_chart(
                    make_candle(data, f"{name} ({symbol}) — {period} 차트", cross_date=cross_date),
                    config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True)

                # RSI 차트 (주가 차트와 x축 동일하게)
                rsi_s  = result["rsi_series"]
                st.plotly_chart(make_rsi_chart(rsi_s, data), config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key="chart_rsi_individual")

            else:
                # 핵심 조건 미충족 — 그래도 차트와 기본 정보는 보여줌
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

                # 미충족 이유 상세 표시
                ma240_now = float(data["Close"].rolling(240).mean().iloc[-1]) if len(data) >= 240 else None
                if ma240_now:
                    gap = (current - ma240_now) / ma240_now * 100
                    c1,c2 = st.columns(2)
                    metric_card(c1,"현재 240선 이격",f"{gap:+.1f}%")
                    metric_card(c2,"240일선",f"₩{ma240_now:,.0f}")
                    if gap < 0:
                        st.warning(f"📉 현재 주가가 240일선 아래 ({gap:.1f}%) — 아직 조정 중")
                    elif gap > max_gap:
                        st.warning(f"📈 240일선 위 {gap:.1f}% — 이미 많이 올라 근처 범위({max_gap}%) 초과")
                    else:
                        st.warning("📊 240일선 돌파 이력 또는 조정 기간 조건 미충족")

                st.plotly_chart(make_candle(data, f"{name} ({symbol}) — {period} 차트"),
                                config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key="chart_candle_no_cond")
                # 조건 미충족이어도 RSI 차트 표시
                rsi_s  = calc_rsi_wilder(data["Close"], period=20)
                st.plotly_chart(make_rsi_chart(rsi_s, data), config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key="chart_rsi_no_cond")


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
                "등락률":    f"{'🔺' if r['price_change_1d']>0 else '🔻'}{r['price_change_1d']:.2f}%",
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
                    st.plotly_chart(
                        make_candle(r["df"], f"{r['name']} ({r['symbol']})"),
                        config={"scrollZoom": False, "displayModeBar": False},
                        use_container_width=True, key=f"candle_quality_{r['symbol']}")


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

    with st.expander("📖 8가지 핵심 조건 설명", expanded=False):
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
        """)

    def calc_surge_timing_score(symbol):
        """최적 급등 타이밍 종합 점수 계산"""
        try:
            df = yf.Ticker(symbol).history(period="2y")
            if df is None or len(df) < 60:
                return None

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

            # ── 보너스: 240일선 돌파 후 근처 ────────────────────
            if ma240 is not None and not pd.isna(ma240.iloc[-1]):
                ma240_v = float(ma240.iloc[-1])
                ma240_gap = (current - ma240_v) / ma240_v * 100
                signals["ma240_gap"] = round(ma240_gap, 1)
                if 0 <= ma240_gap <= 10: score += 2
            else:
                signals["ma240_gap"] = None

            return {
                "symbol":        symbol,
                "name":          STOCK_NAMES.get(symbol, symbol),
                "current_price": current,
                "price_change_1d": round(chg, 2),
                "total_score":   score,
                "max_score":     26,
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
            if r and r["total_score"] >= 7:
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
            metric_card(c4, "만점", "26점")

            st.markdown("<div class='sec-title'>🏆 최적 급등 타이밍 TOP 종목</div>", unsafe_allow_html=True)

            rows = []
            for r in results:
                s = r["signals"]
                rows.append({
                    "종목명":   r["name"],
                    "현재가":   f"₩{r['current_price']:,.0f}",
                    "등락률":   f"{'🔺' if r['price_change_1d']>0 else '🔻'}{r['price_change_1d']:.2f}%",
                    "종합점수": r["total_score"],
                    "RSI":      round(r["rsi"], 1),
                    "거래량비": f"{s.get('vol_ratio',0):.1f}배",
                    "반등위치": f"{s.get('recovery_pct',0):.0f}%",
                    "52주고점": f"{s.get('high_ratio',0):.1f}%",
                    "매집":     "✅" if s.get("accumulation") else "❌",
                    "BB수축":   "✅" if s.get("bb_squeeze") else "❌",
                    "RSI사이클":"✅" if s.get("rsi_cycle") else "❌",
                    "정배열":   "✅" if s.get("ma_align") else "❌",
                    "MACD":     "✅" if s.get("macd_cross") or s.get("macd_positive") else "❌",
                    "장대양봉": "✅" if s.get("big_bull_candle") else "❌",
                })
            df_tbl = pd.DataFrame(rows)
            st.dataframe(df_tbl,
                column_config={"종합점수": st.column_config.ProgressColumn(
                    "종합점수", min_value=0, max_value=26, format="%d점")},
                use_container_width=True, hide_index=True)

            # 상위 종목 상세
            st.markdown("<div class='sec-title'>🔍 상위 종목 상세 분석</div>", unsafe_allow_html=True)
            medals = ["gold","silver","bronze"]
            icons  = ["🥇","🥈","🥉"]

            for i, r in enumerate(results[:10]):
                medal = medals[i] if i < 3 else ""
                icon  = icons[i]  if i < 3 else f"{i+1}."
                s     = r["signals"]
                pct   = r["total_score"] / 26 * 100
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
                    <div style="color:#8b92a5;font-size:11px;margin-bottom:3px;">종합점수 {r["total_score"]}점 / 26점</div>
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
                        (s.get("ma240_gap") is not None and 0 <= s.get("ma240_gap",999) <= 10,
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
                    st.plotly_chart(
                        make_candle(cd, f"{r['name']} ({r['symbol']})", show_levels=True),
                        config={"scrollZoom":False,"displayModeBar":False},
                        use_container_width=True, key=f"candle_timing_{r['symbol']}")
                    st.plotly_chart(
                        make_rsi_chart(r["rsi_series"], cd),
                        config={"scrollZoom":False,"displayModeBar":False},
                        use_container_width=True, key=f"rsi_timing_{r['symbol']}")
