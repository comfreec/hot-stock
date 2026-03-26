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
}

st.set_page_config(page_title="한국 주식 급등 예측", page_icon="🚀", layout="wide")

st.markdown("""
<style>
body, .main { background-color: #0e1117; color: #e0e6f0; }
.top-header {
    background: linear-gradient(135deg,#1a1f35,#0e1117);
    padding: 28px 32px; border-radius: 16px; margin-bottom: 20px;
    border: 1px solid #2d3555;
}
.metric-card {
    background: linear-gradient(135deg,#1e2130,#262b3d);
    border: 1px solid #3d4466; border-radius: 12px;
    padding: 16px; text-align: center; margin: 4px;
}
.metric-card .lbl { color:#8b92a5; font-size:12px; }
.metric-card .val { color:#fff; font-size:22px; font-weight:700; }
.rank-card {
    background: linear-gradient(135deg,#1a1f35,#1e2540);
    border-left: 4px solid #4f8ef7; border-radius: 10px;
    padding: 14px 18px; margin: 8px 0;
}
.rank-card.gold   { border-left-color: #ffd700; }
.rank-card.silver { border-left-color: #c0c0c0; }
.rank-card.bronze { border-left-color: #cd7f32; }
.bar-bg   { background:#1e2130; border-radius:8px; height:8px; width:100%; }
.bar-fill { background:linear-gradient(90deg,#4f8ef7,#00d4aa); border-radius:8px; height:8px; }
.sec-title {
    font-size:20px; font-weight:700; color:#e0e6f0;
    margin:20px 0 10px; padding-bottom:6px; border-bottom:2px solid #2d3555;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="top-header">
  <h1 style="color:#fff;margin:0;font-size:32px;">🚀 한국 주식 급등 예측 시스템</h1>
  <p style="color:#8b92a5;margin:6px 0 0;font-size:14px;">
    거래량 매집 탐지 · OBV 다이버전스 · 볼린저밴드 수축 · 뉴스 감성 · 공시 분석
  </p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ⚙️ 분석 설정")
    mode = st.selectbox("분석 유형", ["🔍 급등 예정 종목 탐지","📈 개별 종목 분석","📊 RSI 전략 (30돌파→70이탈)"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("""**📊 점수 기준**
| 신호 | 점수 |
|------|------|
| 📦 거래량 매집 | 3점 |
| 📈 OBV 다이버전스 | 3점 |
| 🔥 볼린저밴드 수축 | 3점 |
| ⚡ 골든크로스 직전 | 2점 |
| 🏔 52주 신고가 직전 | 2점 |
| 📊 MACD 크로스 | 2점 |
| 🕯 캔들 패턴 | 최대 2점 |
| 📰 긍정 뉴스 | 2점 |
| 📋 호재 공시 | 2점 |""")
    st.markdown("---")
    st.caption("⚠️ 투자 손실에 책임지지 않습니다")

REQUIRED = {
    "vol_accumulation":False,"obv_divergence":False,"bb_squeeze":False,
    "near_52w_high":False,"golden_cross_imminent":False,"macd_cross":False,
    "news_sentiment":0,"pos_news":0,"neg_news":0,"has_disclosure":False,
    "disclosure_types":[],"vol_ratio":0,"disparity":0,"rsi":0,
    "high_ratio":0,"total_score":0,"current_price":0,"price_change_1d":0,
    "squeeze_ratio":0,"disparity_signal":False,
    "candle_patterns":{"bullish_engulf":False,"morning_star":False,"hammer":False,"inv_hammer":False}
}

@st.cache_data(ttl=300)
def run_detection():
    det = KoreanStockSurgeDetector()
    raw = det.analyze_all_stocks()
    out = []
    for r in raw:
        if r is None: continue
        for k,v in REQUIRED.items(): r.setdefault(k,v)
        r["name"] = STOCK_NAMES.get(r["symbol"], r["symbol"])
        out.append(r)
    return out

@st.cache_data(ttl=300)
def get_chart_data(symbol, period="3mo"):
    try: return yf.Ticker(symbol).history(period=period)
    except: return None

def make_candle(data, title):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=data.index, open=data["Open"], high=data["High"],
        low=data["Low"], close=data["Close"], name="주가",
        increasing_line_color="#00d4aa", decreasing_line_color="#ff4b6e"))
    fig.add_trace(go.Bar(x=data.index, y=data["Volume"], name="거래량",
        yaxis="y2", opacity=0.25, marker_color="#4f8ef7"))
    for w,c,n in [(5,"#ffd700","MA5"),(20,"#ff8c42","MA20"),(60,"#a78bfa","MA60")]:
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"].rolling(w).mean(),
            name=n, line=dict(color=c,width=1.2)))
    fig.update_layout(
        title=dict(text=title, font=dict(color="#e0e6f0",size=14)),
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font=dict(color="#8b92a5"),
        yaxis=dict(gridcolor="#1e2540"),
        yaxis2=dict(overlaying="y",side="right",gridcolor="#1e2540"),
        xaxis=dict(gridcolor="#1e2540",rangeslider_visible=False),
        legend=dict(bgcolor="#1e2130",bordercolor="#2d3555"),
        height=420, margin=dict(l=10,r=10,t=40,b=10))
    return fig

def metric_card(col, label, value):
    col.markdown(f"""<div class="metric-card">
        <div class="lbl">{label}</div>
        <div class="val">{value}</div>
    </div>""", unsafe_allow_html=True)

def rank_card(row, medal, icon, idx):
    pct = row["total_score"]/20*100
    color = "#00d4aa" if row["price_change_1d"]>0 else "#ff4b6e"
    arrow = "▲" if row["price_change_1d"]>0 else "▼"
    st.markdown(f"""
    <div class="rank-card {medal}">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div>
          <span style="font-size:22px;">{icon}</span>
          <span style="color:#fff;font-size:18px;font-weight:700;margin-left:8px;">{row["name"]}</span>
          <span style="color:#8b92a5;font-size:13px;margin-left:8px;">{row["symbol"]}</span>
        </div>
        <div style="text-align:right;">
          <span style="color:#fff;font-size:20px;font-weight:700;">₩{row["current_price"]:,.0f}</span>
          <span style="color:{color};font-size:14px;margin-left:8px;">{arrow} {abs(row["price_change_1d"]):.2f}%</span>
        </div>
      </div>
      <div style="margin-top:10px;">
        <div style="color:#8b92a5;font-size:12px;margin-bottom:4px;">종합점수 {row["total_score"]}점 / 20점</div>
        <div class="bar-bg"><div class="bar-fill" style="width:{pct}%;"></div></div>
      </div>
    </div>""", unsafe_allow_html=True)

if mode == "🔍 급등 예정 종목 탐지":
    if st.button("🚀 전종목 분석 시작", type="primary", use_container_width=True):
        with st.spinner("📡 실시간 데이터 수집 및 분석 중..."):
            results = run_detection()
        if not results:
            st.error("분석 결과 없음"); st.stop()
        df = pd.DataFrame(results)

        c1,c2,c3,c4 = st.columns(4)
        metric_card(c1,"분석 종목 수",f"{len(df)}개")
        metric_card(c2,"최고 점수",f"{df['total_score'].max()}점")
        metric_card(c3,"매집 신호",f"{df['vol_accumulation'].sum()}개")
        metric_card(c4,"BB수축 종목",f"{df['bb_squeeze'].sum()}개")

        st.markdown("<div class='sec-title'>🏆 급등 예정 TOP 10</div>", unsafe_allow_html=True)
        disp = df.head(10).copy()
        disp["종목명"]  = disp["name"]
        disp["종목코드"] = disp["symbol"]
        disp["현재가"]  = disp["current_price"].apply(lambda x: f"₩{x:,.0f}")
        disp["등락률"]  = disp["price_change_1d"].apply(lambda x: f"🔺{x:.2f}%" if x>0 else f"🔻{x:.2f}%")
        disp["RSI"]    = disp["rsi"].apply(lambda x: f"{x:.1f}")
        disp["거래량비"] = disp["vol_ratio"].apply(lambda x: f"{x:.1f}배")
        disp["매집"]   = disp["vol_accumulation"].map({True:"✅",False:"❌"})
        disp["BB수축"] = disp["bb_squeeze"].map({True:"✅",False:"❌"})
        disp["52주"]   = disp["near_52w_high"].map({True:"✅",False:"❌"})
        disp["GC직전"] = disp["golden_cross_imminent"].map({True:"✅",False:"❌"})
        disp["뉴스"]   = disp["news_sentiment"].apply(lambda x: f"{x:+.2f}")
        st.dataframe(
            disp[["종목명","종목코드","현재가","등락률","total_score","RSI","거래량비","매집","BB수축","52주","GC직전","뉴스"]],
            column_config={"total_score": st.column_config.ProgressColumn("종합점수",min_value=0,max_value=20,format="%d점")},
            use_container_width=True, hide_index=True)

        col_a, col_b = st.columns(2)
        with col_a:
            fig = px.bar(df.head(10), x="name", y="total_score",
                color="total_score", color_continuous_scale="Blues",
                labels={"name":"종목명","total_score":"점수"}, title="종합 급등 예측 점수")
            fig.update_layout(paper_bgcolor="#0e1117",plot_bgcolor="#0e1117",
                font=dict(color="#8b92a5"),xaxis_tickangle=30,
                coloraxis_showscale=False,height=320,margin=dict(l=10,r=10,t=40,b=60))
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            t = df.iloc[0]
            cats = ["거래량매집","OBV","BB수축","52주고점","GC직전","뉴스"]
            vals = [3 if t["vol_accumulation"] else 0, 3 if t["obv_divergence"] else 0,
                    3 if t["bb_squeeze"] else 0, 2 if t["near_52w_high"] else 0,
                    2 if t["golden_cross_imminent"] else 0, int(t["pos_news"])]
            fig2 = go.Figure(go.Scatterpolar(r=vals+[vals[0]], theta=cats+[cats[0]],
                fill="toself", fillcolor="rgba(79,142,247,0.2)",
                line=dict(color="#4f8ef7",width=2), name=t["name"]))
            fig2.update_layout(
                polar=dict(bgcolor="#1e2130",
                    radialaxis=dict(visible=True,range=[0,3],gridcolor="#2d3555"),
                    angularaxis=dict(gridcolor="#2d3555")),
                paper_bgcolor="#0e1117", font=dict(color="#8b92a5"),
                title=dict(text=f"1위 {t['name']} 신호 레이더",font=dict(color="#e0e6f0")),
                height=320, margin=dict(l=20,r=20,t=50,b=20))
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("<div class='sec-title'>🎯 TOP 3 상세 분석</div>", unsafe_allow_html=True)
        for i, (_, row) in enumerate(df.head(3).iterrows()):
            rank_card(row, ["gold","silver","bronze"][i], ["🥇","🥈","🥉"][i], i)
            with st.expander(f"  {row['name']} 상세 신호 보기"):
                m1,m2,m3,m4 = st.columns(4)
                m1.metric("RSI",f"{row['rsi']:.1f}")
                m2.metric("이격도",f"{row['disparity']:.1f}%")
                m3.metric("거래량비",f"{row['vol_ratio']:.1f}배")
                m4.metric("뉴스감성",f"{row['news_sentiment']:+.2f}")
                active = []
                if row["vol_accumulation"]:      active.append("📦 거래량 매집 감지")
                if row["obv_divergence"]:        active.append("📈 OBV 다이버전스")
                if row["bb_squeeze"]:            active.append(f"🔥 볼린저밴드 수축 ({row['squeeze_ratio']:.2f}배)")
                if row["near_52w_high"]:         active.append(f"🏔 52주 신고가 {row['high_ratio']*100:.1f}%")
                if row["golden_cross_imminent"]: active.append("⚡ 골든크로스 직전")
                if row["macd_cross"]:            active.append("📊 MACD 골든크로스")
                if row["candle_patterns"]["bullish_engulf"]: active.append("🕯 장악형 캔들")
                if row["candle_patterns"]["morning_star"]:   active.append("🌟 샛별형 캔들")
                if row["candle_patterns"]["hammer"]:         active.append("🔨 망치형 캔들")
                if row["news_sentiment"]>0:      active.append(f"📰 긍정 뉴스 {row['pos_news']}건")
                if row["has_disclosure"]:        active.append(f"📋 공시: {', '.join(row['disclosure_types'])}")
                cols = st.columns(2)
                for j,s in enumerate(active): cols[j%2].success(s)
                if not active: st.info("활성 신호 없음")
                cd = get_chart_data(row["symbol"])
                if cd is not None:
                    st.plotly_chart(make_candle(cd, f"{row['name']} ({row['symbol']})"), use_container_width=True)

elif mode == "📈 개별 종목 분석":
    st.markdown("<div class='sec-title'>📈 개별 종목 분석</div>", unsafe_allow_html=True)
    opts = [f"{v} ({k})" for k,v in sorted(STOCK_NAMES.items(), key=lambda x:x[1])]
    col1,col2 = st.columns([3,1])
    with col1: sel = st.selectbox("종목 선택", opts)
    with col2: period = st.selectbox("기간", ["1mo","3mo","6mo","1y"])
    symbol = sel.split("(")[1].replace(")","").strip()
    name   = sel.split("(")[0].strip()

    if st.button("분석", type="primary"):
        with st.spinner(f"{name} 분석 중..."):
            det = KoreanStockSurgeDetector()
            result = det.analyze_stock(symbol)
            data = get_chart_data(symbol, period)
        if result and data is not None:
            for k,v in REQUIRED.items(): result.setdefault(k,v)
            pct = result["total_score"]/20*100
            color = "#00d4aa" if result["price_change_1d"]>0 else "#ff4b6e"
            arrow = "▲" if result["price_change_1d"]>0 else "▼"
            st.markdown(f"""
            <div class="rank-card gold" style="margin-bottom:16px;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <span style="color:#fff;font-size:24px;font-weight:700;">{name}</span>
                  <span style="color:#8b92a5;font-size:14px;margin-left:10px;">{symbol}</span>
                </div>
                <div style="text-align:right;">
                  <span style="color:#fff;font-size:26px;font-weight:700;">₩{result["current_price"]:,.0f}</span>
                  <span style="color:{color};font-size:16px;margin-left:10px;">{arrow} {abs(result["price_change_1d"]):.2f}%</span>
                </div>
              </div>
              <div style="margin-top:12px;">
                <div style="color:#8b92a5;font-size:12px;margin-bottom:4px;">종합점수 {result["total_score"]}점 / 20점</div>
                <div class="bar-bg"><div class="bar-fill" style="width:{pct}%;"></div></div>
              </div>
            </div>""", unsafe_allow_html=True)
            c1,c2,c3,c4 = st.columns(4)
            metric_card(c1,"RSI",f"{result['rsi']:.1f}")
            metric_card(c2,"이격도",f"{result['disparity']:.1f}%")
            metric_card(c3,"거래량비",f"{result['vol_ratio']:.1f}배")
            metric_card(c4,"뉴스감성",f"{result['news_sentiment']:+.2f}")
            st.plotly_chart(make_candle(data, f"{name} ({symbol})"), use_container_width=True)
            st.markdown("<div class='sec-title'>📊 신호 분석</div>", unsafe_allow_html=True)
            checks = [
                (result.get("vol_accumulation"),     "📦 거래량 매집"),
                (result.get("obv_divergence"),        "📈 OBV 다이버전스"),
                (result.get("bb_squeeze"),            "🔥 볼린저밴드 수축"),
                (result.get("near_52w_high"),         "🏔 52주 신고가 직전"),
                (result.get("golden_cross_imminent"), "⚡ 골든크로스 직전"),
                (result.get("macd_cross"),            "📊 MACD 크로스"),
                (result["candle_patterns"]["hammer"], "🔨 망치형 캔들"),
                (result["candle_patterns"]["bullish_engulf"], "🕯 장악형 캔들"),
                (result.get("news_sentiment",0)>0,   f"📰 긍정 뉴스 {result.get('pos_news',0)}건"),
                (result.get("has_disclosure"),        "📋 호재 공시"),
            ]
            on  = [l for a,l in checks if a]
            off = [l for a,l in checks if not a]
            ca,cb = st.columns(2)
            with ca:
                st.write("**✅ 활성 신호**")
                for s in on: st.success(s)
                if not on: st.info("활성 신호 없음")
            with cb:
                st.write("**❌ 미충족 신호**")
                for s in off: st.error(s)


elif mode == "📊 RSI 전략 (30돌파→70이탈)":
    st.markdown("""
    <div style='background:linear-gradient(135deg,#1a1f35,#0e1117);
         padding:20px 24px;border-radius:12px;margin-bottom:16px;
         border:1px solid #2d3555;'>
      <h3 style='color:#fff;margin:0;'>📊 RSI(20) 전략 스캐너</h3>
      <p style='color:#8b92a5;margin:8px 0 0;font-size:13px;'>
        ① RSI 30 이하 (과매도) → ② RSI 30 돌파 (반등 시작) → 
        ③ RSI 70 이상 도달 (과매수) → ④ RSI 70 이탈 (최근)<br>
        <b style='color:#ffd700;'>→ 한 사이클 완성 후 다음 매수 타이밍 준비 종목</b>
      </p>
    </div>
    """, unsafe_allow_html=True)

    col_info1, col_info2, col_info3 = st.columns(3)
    col_info1.info("📉 RSI 30 이하: 과매도 구간 (바닥)")
    col_info2.success("📈 RSI 30 돌파: 반등 시작 신호")
    col_info3.warning("📊 RSI 70 이탈: 고점 확인 후 조정")

    if st.button("🔍 RSI 패턴 스캔 시작", type="primary", use_container_width=True):
        with st.spinner("RSI(20) 패턴 분석 중..."):
            from rsi_strategy import find_rsi_pattern, ALL_SYMBOLS, calc_rsi
            import yfinance as yf

            results = []
            prog = st.progress(0)
            for idx, symbol in enumerate(ALL_SYMBOLS):
                r = find_rsi_pattern(symbol)
                if r:
                    results.append(r)
                prog.progress((idx+1)/len(ALL_SYMBOLS))
            prog.empty()

        if not results:
            st.warning("현재 해당 패턴을 만족하는 종목이 없습니다.")
        else:
            st.success(f"✅ {len(results)}개 종목 발견!")

            # 요약 카드
            c1,c2,c3 = st.columns(3)
            metric_card(c1, "패턴 완성 종목", f"{len(results)}개")
            metric_card(c2, "평균 현재 RSI", f"{sum(r['current_rsi'] for r in results)/len(results):.1f}")
            metric_card(c3, "최근 70이탈", f"{min(r['days_since_70_cross'] for r in results)}일 전")

            st.markdown("<div class='sec-title'>🎯 RSI 패턴 완성 종목</div>", unsafe_allow_html=True)

            # 테이블
            df_rsi = pd.DataFrame([{
                "종목명": r["name"],
                "종목코드": r["symbol"],
                "현재가": f"₩{r['current_price']:,.0f}",
                "등락률": f"{'🔺' if r['price_change_1d']>0 else '🔻'}{r['price_change_1d']:.2f}%",
                "현재RSI": r["current_rsi"],
                "바닥RSI": r["bottom_rsi"],
                "고점RSI": r["peak_rsi"],
                "30돌파일": r["cross_above_30_date"],
                "70이탈일": r["cross_below_70_date"],
                "이탈후경과": f"{r['days_since_70_cross']}일",
            } for r in results])

            st.dataframe(
                df_rsi,
                column_config={
                    "현재RSI": st.column_config.ProgressColumn(
                        "현재RSI", min_value=0, max_value=100, format="%.1f"
                    ),
                },
                use_container_width=True, hide_index=True
            )

            # 개별 RSI 차트
            st.markdown("<div class='sec-title'>📈 종목별 RSI 차트</div>", unsafe_allow_html=True)
            for r in results:
                with st.expander(f"📊 {r['name']} ({r['symbol']}) — 현재 RSI: {r['current_rsi']}"):
                    rsi_s = r["rsi_series"]
                    price_s = r["price_series"]

                    fig = go.Figure()

                    # RSI 라인
                    fig.add_trace(go.Scatter(
                        x=rsi_s.index, y=rsi_s.values,
                        name="RSI(20)", line=dict(color="#4f8ef7", width=2)
                    ))
                    # 30선
                    fig.add_hline(y=30, line=dict(color="#00d4aa", dash="dash", width=1.5),
                                  annotation_text="RSI 30 (과매도)", annotation_font_color="#00d4aa")
                    # 70선
                    fig.add_hline(y=70, line=dict(color="#ff4b6e", dash="dash", width=1.5),
                                  annotation_text="RSI 70 (과매수)", annotation_font_color="#ff4b6e")
                    # 30 돌파 시점 마킹
                    fig.add_vline(x=r["cross_above_30_date"],
                                  line=dict(color="#00d4aa", dash="dot", width=1.5),
                                  annotation_text="30 돌파", annotation_font_color="#00d4aa")
                    # 70 이탈 시점 마킹
                    fig.add_vline(x=r["cross_below_70_date"],
                                  line=dict(color="#ff4b6e", dash="dot", width=1.5),
                                  annotation_text="70 이탈", annotation_font_color="#ff4b6e")
                    # 과매도/과매수 영역 색칠
                    fig.add_hrect(y0=0, y1=30, fillcolor="rgba(0,212,170,0.08)", line_width=0)
                    fig.add_hrect(y0=70, y1=100, fillcolor="rgba(255,75,110,0.08)", line_width=0)

                    fig.update_layout(
                        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                        font=dict(color="#8b92a5"),
                        yaxis=dict(range=[0,100], gridcolor="#1e2540", title="RSI"),
                        xaxis=dict(gridcolor="#1e2540"),
                        height=300, margin=dict(l=10,r=10,t=30,b=10),
                        title=dict(text=f"{r['name']} RSI(20)", font=dict(color="#e0e6f0"))
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # 주가 차트
                    cd = get_chart_data(r["symbol"])
                    if cd is not None:
                        st.plotly_chart(make_candle(cd, f"{r['name']} 주가"), use_container_width=True)

                    # 요약
                    m1,m2,m3,m4 = st.columns(4)
                    m1.metric("바닥 RSI", f"{r['bottom_rsi']:.1f}", help="과매도 구간 최저점")
                    m2.metric("고점 RSI", f"{r['peak_rsi']:.1f}", help="과매수 구간 최고점")
                    m3.metric("현재 RSI", f"{r['current_rsi']:.1f}")
                    m4.metric("70이탈 후", f"{r['days_since_70_cross']}일 경과")

