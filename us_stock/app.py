"""
미국 주식 급등 예고 탐지 - 웹 UI
국내 주식과 동일한 R-사이클 + 장기선 전략
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from us_stock.symbols import ALL_SYMBOLS, get_symbols_by_category
from us_stock.us_stock_detector import USStockDetector
from us_stock.telegram_alert import calc_us_levels, send_us_scan_alert

# ── 스타일 ────────────────────────────────────────────────────────
st.markdown("""<style>
.stApp { background: #080c14 !important; }
.metric-card { background: linear-gradient(135deg,#111827,#1a2035); border:1px solid rgba(61,68,102,.6);
  border-radius:14px; padding:18px 14px; text-align:center; margin:4px; }
.metric-card .lbl { color:#6b7280; font-size:11px; font-weight:500; text-transform:uppercase; }
.metric-card .val { color:#f0f4ff; font-size:22px; font-weight:800; margin-top:4px; }
.rank-card { background:linear-gradient(135deg,#0f1623,#131d2e); border-left:3px solid #4f8ef7;
  border-radius:14px; padding:18px 20px; margin:10px 0; }
.bar-bg { background:rgba(30,33,48,.8); border-radius:10px; height:6px; width:100%; overflow:hidden; }
.bar-fill { background:linear-gradient(90deg,#4f8ef7,#00d4aa); border-radius:10px; height:6px; }
</style>""", unsafe_allow_html=True)

# ── 사이드바 ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🇺🇸 미국 주식 스캔")
    st.markdown("---")

    category = st.selectbox("종목 카테고리", ["전체", "나스닥100", "S&P500 대형주", "ETF"])
    max_gap  = st.slider("장기선 근처 범위 (%)", 1, 15, 7)
    ob_days  = st.slider("R-사이클 이탈 후 경과일", 30, 365, 180)
    min_below = st.slider("최소 조정 기간 (일)", 0, 60, 0)
    min_score = st.slider("최소 종합점수", 5, 50, 30)

    st.markdown("---")
    scan_btn = st.button("🔍 스캔 시작", type="primary", use_container_width=True)
    alert_btn = st.button("📡 텔레그램 전송", use_container_width=True)

# ── 메인 ─────────────────────────────────────────────────────────
st.markdown("""
<div style='background:linear-gradient(135deg,#0d1528,#111827);padding:24px 32px;border-radius:20px;
margin-bottom:20px;border:1px solid rgba(79,142,247,.25);'>
  <div style='display:flex;align-items:center;gap:16px;'>
    <span style='font-size:48px;'>🇺🇸</span>
    <div>
      <div style='color:#e0e6f0;font-size:24px;font-weight:900;'>미국 주식 스윙 레이더</div>
      <div style='color:#6b7280;font-size:13px;margin-top:4px;'>R-사이클 + 240일선 전략 · 달러 기준</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# 종목 선택
cats = get_symbols_by_category()
if category == "전체":
    symbols = ALL_SYMBOLS
else:
    symbols = cats.get(category, ALL_SYMBOLS)

st.caption(f"스캔 대상: {len(symbols)}개 종목 | 장기선 근처 {max_gap}% 이내 | 최소 점수 {min_score}점")

# 스캔 실행
if scan_btn:
    det = USStockDetector(max_gap_pct=max_gap, ob_days=ob_days,
                          min_below_days=min_below, min_score=min_score)
    with st.spinner(f"🇺🇸 {len(symbols)}개 종목 스캔 중..."):
        results = det.analyze_all(symbols)
    st.session_state["us_results"] = results
    if results:
        st.success(f"✅ {len(results)}개 종목 발견")
    else:
        st.info("조건에 맞는 종목이 없습니다.")

# 텔레그램 전송
if alert_btn:
    results = st.session_state.get("us_results", [])
    if results:
        with st.spinner("텔레그램 전송 중..."):
            send_us_scan_alert(results)
        st.success("텔레그램 전송 완료!")
    else:
        st.warning("먼저 스캔을 실행하세요.")

# 결과 표시
results = st.session_state.get("us_results", [])
if results:
    st.markdown(f"### 📊 스캔 결과 ({len(results)}개)")

    for i, r in enumerate(results):
        score = r["total_score"]
        pct = min(score / 28 * 100, 100)
        cur = r["current_price"]
        s = r.get("signals", {})

        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."

        with st.expander(f"{medal} {r['name']} ({r['symbol']}) — {score}점 | ${cur:,.2f} | 240선 +{r['ma240_gap']:.1f}%", expanded=(i < 3)):
            # 메트릭
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("R-사이클(20)", f"{r['rsi']:.1f}")
            c2.metric("240선 이격", f"+{r['ma240_gap']:.1f}%")
            c3.metric("R-사이클 이탈", f"{s.get('rsi_cycle_days_since', '-')}일 전")
            c4.metric("240일선", f"${r['ma240']:,.2f}")
            stop_v = s.get("stop_price", r["ma240"] * 0.95)
            c5.metric("손절가", f"${stop_v:,.2f}" if stop_v else "-")

            # 점수 바
            st.markdown(f"""<div style='padding:4px 0 8px;'>
              <div style='color:#8b92a5;font-size:11px;margin-bottom:3px;'>종합점수 {score}점</div>
              <div class='bar-bg'><div class='bar-fill' style='width:{pct:.1f}%;'></div></div>
            </div>""", unsafe_allow_html=True)

            # 신호
            active = []
            if s.get("ma_align"):              active.append("⚡ 이평선 정배열")
            if s.get("bb_squeeze_expand"):     active.append("🔥 BB 수축→확장")
            if s.get("macd_cross"):            active.append("📊 MACD 골든크로스")
            if s.get("ma240_turning_up"):      active.append("🔼 240선 상승전환")
            if s.get("pullback_bounce"):       active.append(f"🎯 눌림목 반등 ({s.get('pullback_depth',0):.1f}%)")
            if s.get("near_52w_high"):         active.append(f"🏆 52주 신고가 근처 ({s.get('high_ratio',0):.1f}%)")
            if s.get("rsi_healthy"):           active.append(f"💚 R-사이클 건강 ({s.get('rsi',0):.1f})")
            if s.get("recent_vol"):            active.append(f"📊 거래량 증가 ({s.get('recent_vol_ratio',0):.1f}배)")
            if s.get("vol_strong"):            active.append(f"🚀 거래량 폭발 ({s.get('recent_vol_ratio',0):.1f}배)")
            if s.get("obv_rising"):            active.append("📈 OBV 지속 상승")
            if s.get("rsi_slope_up"):          active.append("📈 R-사이클 기울기 상승")
            if s.get("rsi_cross50"):           active.append("⚡ R-사이클 50 돌파")
            if s.get("weekly_rsi_bull"):       active.append(f"📅 주봉 RSI 강세 ({s.get('weekly_rsi',50):.0f})")
            if s.get("weekly_rsi_rising"):     active.append("📅 주봉 RSI 상승 중")
            if s.get("rs_strong"):             active.append(f"💪 S&P500 대비 강세 (+{s.get('rs_vs_spy',0):.1f}%)")
            if s.get("rs_outperform"):         active.append(f"📈 S&P500 아웃퍼폼 ({s.get('rs_vs_spy',0):.1f}%)")
            if s.get("sector_momentum", 0) > 1: active.append(f"🔥 섹터 강세 ({s.get('sector_etf','')} +{s.get('sector_momentum',0):.1f}%)")
            if s.get("stealth_accumulation"):  active.append("🕵️ 세력 매집 감지")
            if s.get("hammer"):                active.append("🔨 망치형 캔들")
            if s.get("bullish_engulf"):        active.append("🕯 장악형 캔들")

            if active:
                cols = st.columns(2)
                for j, sig in enumerate(active):
                    cols[j % 2].success(sig)

            # 차트
            close_s = r.get("close_series")
            if close_s is not None and len(close_s) > 20:
                try:
                    def to_s(v):
                        if v is None: return None
                        if hasattr(v, 'rolling'): return v
                        return pd.Series(list(v))

                    cs = to_s(close_s)
                    hs = to_s(r.get("high_series", close_s))
                    ls = to_s(r.get("low_series", close_s))
                    os_ = to_s(r.get("open_series", close_s))

                    lv = calc_us_levels(cs, hs, ls)

                    cd = pd.DataFrame({
                        "Open": os_, "High": hs, "Low": ls, "Close": cs
                    })
                    fig = go.Figure()
                    fig.add_trace(go.Ohlc(
                        x=cd.index, open=cd["Open"], high=cd["High"],
                        low=cd["Low"], close=cd["Close"], name="주가",
                        increasing_line_color="#ff3355", decreasing_line_color="#4f8ef7"
                    ))
                    for w, c, nm in [(20,"#ffd700","MA20"),(60,"#ff8c42","MA60"),(240,"#ff4b6e","MA240")]:
                        ma = cs.rolling(w).mean()
                        fig.add_trace(go.Scatter(x=cd.index, y=ma, name=nm,
                            line=dict(color=c, width=3 if w==240 else 1.2)))

                    if lv:
                        fig.add_hline(y=lv["target"], line=dict(color="#00ff88", width=2, dash="dash"))
                        fig.add_hline(y=lv["stop"],   line=dict(color="#ff3355", width=2, dash="dash"))
                        fig.add_hline(y=lv["entry"],  line=dict(color="#ffd700", width=1.5, dash="dashdot"))
                        fig.add_hline(y=lv["current"],line=dict(color="#ffffff", width=1, dash="dot"))

                    fig.update_layout(
                        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                        font=dict(color="#8b92a5"),
                        yaxis=dict(gridcolor="#1e2540", fixedrange=True, side="right"),
                        xaxis=dict(gridcolor="#1e2540", rangeslider_visible=False, fixedrange=True),
                        legend=dict(bgcolor="#1e2130", visible=False),
                        dragmode=False, height=400,
                        margin=dict(l=0, r=50, t=20, b=0)
                    )
                    st.plotly_chart(fig, config={"scrollZoom": False, "displayModeBar": False, "staticPlot": True},
                                    width='stretch', key=f"us_chart_{r['symbol']}_{i}")

                    # 가격 레벨 카드
                    if lv:
                        rr = lv["rr"]
                        rr_color = "#00ff88" if rr >= 3 else "#ffd700" if rr >= 2 else "#ff8c42"
                        st.markdown(f"""
                        <div style='display:flex;gap:8px;margin:4px 0;'>
                          <div style='flex:1.2;background:rgba(0,255,136,.08);border:1px solid #00ff88;border-radius:10px;padding:12px;text-align:center;'>
                            <div style='color:#8b92a5;font-size:10px;'>🎯 목표가</div>
                            <div style='color:#00ff88;font-size:18px;font-weight:700;'>${lv["target"]:,.2f}</div>
                            <div style='color:#00ff88;font-size:12px;'>+{lv["upside"]:.1f}%</div>
                          </div>
                          <div style='flex:1;background:rgba(255,215,0,.08);border:1px solid #ffd700;border-radius:10px;padding:12px;text-align:center;'>
                            <div style='color:#8b92a5;font-size:10px;'>📍 매수가</div>
                            <div style='color:#ffd700;font-size:18px;font-weight:700;'>${lv["entry"]:,.2f}</div>
                            <div style='color:#ffd700;font-size:12px;'>{lv["entry_label"]} 기준</div>
                          </div>
                          <div style='flex:1;background:rgba(255,51,85,.08);border:1px solid #ff3355;border-radius:10px;padding:12px;text-align:center;'>
                            <div style='color:#8b92a5;font-size:10px;'>🛑 손절가</div>
                            <div style='color:#ff3355;font-size:18px;font-weight:700;'>${lv["stop"]:,.2f}</div>
                            <div style='color:#ff3355;font-size:12px;'>{lv["downside"]:.1f}%</div>
                            <div style='color:#4a5568;font-size:10px;margin-top:4px;'>추세이탈 기준</div>
                          </div>
                          <div style='flex:.8;background:rgba(255,215,0,.08);border:1px solid {rr_color};border-radius:10px;padding:12px;text-align:center;'>
                            <div style='color:#8b92a5;font-size:10px;'>⚖️ 손익비</div>
                            <div style='color:{rr_color};font-size:22px;font-weight:700;'>{rr:.1f}:1</div>
                          </div>
                        </div>
                        """, unsafe_allow_html=True)
                except Exception as e:
                    st.caption(f"차트 오류: {e}")
