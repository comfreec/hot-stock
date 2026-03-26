import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from datetime import datetime
from stock_surge_detector import KoreanStockSurgeDetector

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

st.set_page_config(page_title="한국 주식 급등 예측", page_icon="🚀", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""<style>
/* 모바일 뷰포트 */
meta[name="viewport"] { content: "width=device-width, initial-scale=1.0"; }

/* 기본 레이아웃 */
.main .block-container {
    padding: 0.5rem 0.8rem !important;
    max-width: 100% !important;
}
section[data-testid="stSidebar"] {
    min-width: 260px !important;
    max-width: 280px !important;
}
/* 모바일에서 사이드바 숨김 처리 */
@media (max-width: 768px) {
    section[data-testid="stSidebar"] { display: none !important; }
    .main .block-container { padding: 0.3rem 0.4rem !important; }
    h1 { font-size: 20px !important; }
    h3 { font-size: 16px !important; }
    .metric-card .val { font-size: 16px !important; }
    .rank-card { padding: 10px 12px !important; }
}

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
.sec-title{font-size:20px;font-weight:700;color:#e0e6f0;margin:20px 0 10px;
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
    mode = st.selectbox("화면", ["🔍 급등 예고 종목 탐지", "📈 개별 종목 분석"],
                        label_visibility="collapsed")
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
    """Wilder's Smoothing RSI - 증권사 표준 방식"""
    d = close.diff()
    gain = d.where(d > 0, 0.0)
    loss = -d.where(d < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    return 100 - (100 / (1 + rs))

def make_rsi_chart(rsi_s, chart_data=None):
    """RSI 차트 - chart_data 인덱스에 맞춰 길이 동기화"""
    if chart_data is not None:
        try:
            import pandas as pd
            # 타임존 제거 후 날짜만으로 비교
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
        name="RSI(20)", line=dict(color="#4f8ef7", width=2),
        fill="tozeroy", fillcolor="rgba(79,142,247,0.05)"
    ))
    fig.add_hline(y=30, line=dict(color="#00d4aa", dash="dash", width=1.5),
                  annotation_text="과매도 30", annotation_font_color="#00d4aa",
                  annotation_position="left")
    fig.add_hline(y=70, line=dict(color="#ff4b6e", dash="dash", width=1.5),
                  annotation_text="과매수 70", annotation_font_color="#ff4b6e",
                  annotation_position="left")
    fig.add_hrect(y0=0,  y1=30,  fillcolor="rgba(0,212,170,0.06)",  line_width=0)
    fig.add_hrect(y0=70, y1=100, fillcolor="rgba(255,75,110,0.06)", line_width=0)
    fig.update_layout(
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font=dict(color="#8b92a5"),
        yaxis=dict(range=[0,100], gridcolor="#1e2540", title="RSI"),
        xaxis=dict(gridcolor="#1e2540", rangeslider_visible=False),
        height=160, margin=dict(l=40,r=5,t=25,b=5),
        title=dict(text="RSI(20)", font=dict(color="#e0e6f0", size=13)),
        showlegend=False
    )
    return fig

def make_candle(data, title, ma240_series=None, cross_date=None):
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
            import pandas as pd
            cd_ts = pd.Timestamp(cross_date).timestamp() * 1000
            fig.add_vline(x=cd_ts,
                line=dict(color="#00d4aa", dash="dot", width=2),
                annotation_text="240선 돌파", annotation_font_color="#00d4aa")
        except:
            pass
    fig.update_layout(
        title=dict(text=title, font=dict(color="#e0e6f0", size=14)),
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font=dict(color="#8b92a5"),
        yaxis=dict(gridcolor="#1e2540"),
        yaxis2=dict(overlaying="y", side="right", gridcolor="#1e2540"),
        xaxis=dict(gridcolor="#1e2540", rangeslider_visible=False),
        legend=dict(bgcolor="#1e2130", bordercolor="#2d3555"),
        height=380, margin=dict(l=0,r=0,t=30,b=0))
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

    if st.button("🚀 스캔 시작", type="primary", config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True):
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

                # ── RSI 차트: expander 기본 열림 (종목명 바로 아래) ──
                rsi_s  = r["rsi_series"]
                cd     = get_chart_data(r["symbol"], "2y")
                with st.expander(f"📊 {r['name']} RSI(20) 차트", expanded=True):
                    st.plotly_chart(make_rsi_chart(rsi_s, cd), config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key=f"rsi_main_{r['symbol']}")

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