"""
미국 주식 급등 예고 탐지 - 웹 UI
국내 주식과 동일한 R-사이클 + 장기선 전략 (달러 단위)
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os

# _run_app이 us_stock/ 디렉토리에서 실행하므로 직접 import
_us_dir = os.path.dirname(os.path.abspath(__file__))
if _us_dir not in sys.path:
    sys.path.insert(0, _us_dir)
_root_dir = os.path.dirname(_us_dir)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

try:
    from symbols import ALL_SYMBOLS, get_symbols_by_category
    from us_stock_detector import USStockDetector
    from telegram_alert import calc_us_levels, send_us_scan_alert
except ImportError:
    from us_stock.symbols import ALL_SYMBOLS, get_symbols_by_category
    from us_stock.us_stock_detector import USStockDetector
    from us_stock.telegram_alert import calc_us_levels, send_us_scan_alert

# ── 로그인 체크 (main_app.py의 인증 세션 공유) ───────────────────
if not st.session_state.get("authenticated", False):
    try:
        PASSWORDS = list(st.secrets.get("PASSWORDS", ["comfreec"]))
    except Exception:
        PASSWORDS = ["comfreec"]

    st.markdown("""
    <style>
    @keyframes fadein { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }
    @keyframes radar_spin { 0%{transform:rotate(0deg)} 100%{transform:rotate(360deg)} }
    @keyframes radar_pulse {
        0%,100%{box-shadow:0 0 0 0 rgba(0,212,170,0.4),0 0 20px rgba(79,142,247,0.3);}
        50%{box-shadow:0 0 0 16px rgba(0,212,170,0),0 0 40px rgba(79,142,247,0.6);}
    }
    .login-box{animation:fadein 0.6s ease;}
    .radar-wrap{width:96px;height:96px;border-radius:50%;background:linear-gradient(135deg,#0d1528,#1a2540);
        border:2px solid #4f8ef7;display:flex;align-items:center;justify-content:center;
        margin:0 auto 16px;animation:radar_pulse 2s ease-in-out infinite;position:relative;overflow:hidden;}
    .radar-sweep{position:absolute;width:50%;height:50%;top:0;left:50%;transform-origin:bottom left;
        background:linear-gradient(135deg,rgba(0,212,170,0.6),transparent);
        animation:radar_spin 2s linear infinite;border-radius:100% 0 0 0;}
    .radar-icon{font-size:44px;z-index:1;position:relative;}
    </style>
    <div class='login-box' style='max-width:420px;margin:30px auto;'>
      <div style='background:linear-gradient(135deg,#1a1f35,#0e1117);
           padding:48px 40px;border-radius:20px;border:1px solid #2d3555;
           box-shadow:0 20px 60px rgba(0,0,0,0.5);text-align:center;'>
        <div class='radar-wrap'><div class='radar-sweep'></div><div class='radar-icon'>🇺🇸</div></div>
        <div style='display:inline-block;padding:8px 20px;border-radius:10px;
            background:linear-gradient(135deg,rgba(79,142,247,0.12),rgba(0,212,170,0.12));
            box-shadow:0 0 24px rgba(0,212,170,0.25),0 0 48px rgba(79,142,247,0.15);margin:8px auto 2px;'>
          <h2 style='margin:0;font-size:32px;font-weight:900;letter-spacing:8px;
              background:linear-gradient(90deg,#4f8ef7 0%,#00d4aa 50%,#4f8ef7 100%);
              -webkit-background-clip:text;-webkit-text-fill-color:transparent;'>J.A.R.V.I.S.</h2>
        </div>
        <p style='color:#6b7280;font-size:11px;margin:4px 0 4px;letter-spacing:5px;text-transform:uppercase;'>US SWING RADAR</p>
        <div style='width:40px;height:2px;background:linear-gradient(90deg,#4f8ef7,#00d4aa);margin:0 auto 28px;border-radius:2px;'></div>
        <p style='color:#8b92a5;font-size:13px;margin:0 0 24px;'>허가된 사용자만 접근 가능합니다</p>
      </div>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pw = st.text_input("", type="password", placeholder="🔑  비밀번호 입력", label_visibility="collapsed")
        if st.button("로그인", type="primary", use_container_width=True):
            if pw in PASSWORDS:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다")
    st.stop()

# ── 스타일 (국내 앱과 동일한 다크 테마) ─────────────────────────
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
    border: 1px solid rgba(79,142,247,0.25);
    box-shadow: 0 0 40px rgba(79,142,247,0.08), inset 0 1px 0 rgba(255,255,255,0.05);
    position: relative; overflow: hidden;
}
.top-header::before {
    content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
    background: radial-gradient(ellipse at 30% 50%, rgba(79,142,247,0.06) 0%, transparent 60%);
    pointer-events: none;
}
.metric-card {
    background: linear-gradient(135deg, #111827 0%, #1a2035 100%);
    border: 1px solid rgba(61,68,102,0.6); border-radius: 14px;
    padding: 18px 14px; text-align: center; margin: 4px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.3); position: relative; overflow: hidden;
}
.metric-card::after {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(79,142,247,0.4), transparent);
}
.metric-card .lbl { color: #6b7280; font-size: 11px; font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase; }
.metric-card .val { color: #f0f4ff; font-size: 24px; font-weight: 800; margin-top: 4px; letter-spacing: -0.5px; }

.rank-card {
    background: linear-gradient(135deg, #0f1623 0%, #131d2e 100%);
    border-left: 3px solid #4f8ef7;
    border-top: 1px solid rgba(255,255,255,0.05);
    border-right: 1px solid rgba(255,255,255,0.03);
    border-bottom: 1px solid rgba(255,255,255,0.03);
    border-radius: 14px; padding: 18px 20px; margin: 10px 0;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    position: relative; overflow: hidden;
}
.rank-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background: linear-gradient(135deg, rgba(79,142,247,0.03) 0%, transparent 60%);
    pointer-events: none;
}
.rank-card.gold  { border-left-color: #ffd700; background: linear-gradient(135deg, #141208 0%, #1a1a0f 100%); }
.rank-card.silver{ border-left-color: #c0c0c0; background: linear-gradient(135deg, #111318 0%, #181b22 100%); }
.rank-card.bronze{ border-left-color: #cd7f32; background: linear-gradient(135deg, #130f0a 0%, #1a1510 100%); }

.bar-bg  { background: rgba(30,33,48,0.8); border-radius: 10px; height: 6px; width: 100%; overflow: hidden; }
.bar-fill{ background: linear-gradient(90deg, #4f8ef7 0%, #00d4aa 100%); border-radius: 10px; height: 6px;
           box-shadow: 0 0 8px rgba(79,142,247,0.5); }

.sec-title {
    font-size: clamp(15px,3vw,19px); font-weight: 700; color: #e8edf8;
    margin: 24px 0 12px; padding-bottom: 8px;
    border-bottom: 1px solid rgba(45,53,85,0.8);
    letter-spacing: -0.3px; display: flex; align-items: center; gap: 8px;
}
.cond-box {
    background: linear-gradient(135deg, #0d1528, #111827);
    border: 1px solid rgba(45,53,85,0.7); border-radius: 12px;
    padding: 14px 18px; margin-bottom: 14px; font-size: 13px; color: #8b92a5;
}
.stButton > button {
    background: linear-gradient(135deg, #1e3a5f 0%, #1a3050 100%) !important;
    border: 1px solid rgba(79,142,247,0.3) !important; color: #7eb8f7 !important;
    border-radius: 10px !important; font-weight: 600 !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #254a7a 0%, #1e3d66 100%) !important;
    border-color: rgba(79,142,247,0.6) !important;
    box-shadow: 0 4px 16px rgba(79,142,247,0.2) !important;
    transform: translateY(-1px) !important;
}
button[kind="primary"] {
    background: linear-gradient(135deg, #1a56db 0%, #1e40af 100%) !important;
    border: 1px solid rgba(79,142,247,0.5) !important; color: #fff !important;
}
</style>""", unsafe_allow_html=True)

# ── 사이드바 ──────────────────────────────────────────────────────
with st.sidebar:
    # 미국 국기 아이콘
    st.markdown("""
    <style>
    @keyframes flag_wave {
        0%,100%{transform:rotate(-2deg) scale(1.0);}
        50%{transform:rotate(2deg) scale(1.05);}
    }
    .us-flag-wrap{text-align:center;padding:16px 0 8px;}
    .us-flag{font-size:72px;display:inline-block;animation:flag_wave 3s ease-in-out infinite;
             filter:drop-shadow(0 0 16px rgba(79,142,247,0.5));}
    </style>
    <div class='us-flag-wrap'><div class='us-flag'>🇺🇸</div></div>
    <div style='text-align:center;margin-bottom:8px;'>
      <span style='font-size:18px;font-weight:900;background:linear-gradient(90deg,#4f8ef7,#00d4aa);
        -webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:2px;'>
        US SWING RADAR
      </span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    category = st.selectbox("📂 종목 카테고리", ["전체", "나스닥100", "S&P500 대형주", "ETF"],
                            key="us_category")

    if st.button("⚡ 기본 셋팅", use_container_width=True, key="us_default"):
        st.session_state["us_max_gap"]   = 7
        st.session_state["us_ob_days"]   = 180
        st.session_state["us_min_below"] = 0
        st.session_state["us_min_score"] = 20
        st.rerun()

    if "us_max_gap"   not in st.session_state: st.session_state["us_max_gap"]   = 7
    if "us_ob_days"   not in st.session_state: st.session_state["us_ob_days"]   = 180
    if "us_min_below" not in st.session_state: st.session_state["us_min_below"] = 0
    if "us_min_score" not in st.session_state: st.session_state["us_min_score"] = 20

    max_gap   = st.slider("📏 장기선 근처 범위 (%)", 1, 15, key="us_max_gap")
    ob_days   = st.slider("📅 R-사이클 70 이탈 후 경과일", 30, 365, key="us_ob_days")
    min_below = st.slider("📉 최소 조정 기간 (일)", 0, 60, key="us_min_below")
    min_score = st.slider("⭐ 최소 종합점수", 5, 50, key="us_min_score")

    st.markdown("---")
    st.markdown("""**📋 탐지 전략**
> R-사이클 4단계 사이클 + 240일선 눌림목 진입

| 단계 | 조건 |
|------|------|
| 1️⃣ | RSI(20) 30 이하 과매도 |
| 2️⃣ | RSI 30 돌파 (과매도 탈출) |
| 3️⃣ | RSI 70 이상 도달 (과매수) |
| 4️⃣ | RSI 70 이탈 → 조정 시작 |
| 📍 | 현재가 240선 위 0~N% 이내 |
| 📉 | 현재 RSI 55 이하 (눌림목) |
| 🛑 | 손절가: RSI 저점 기준 |

**📊 가산점 신호**
| 신호 | 점수 |
|------|------|
| 🚀 거래량 폭발 (2배+) | 4점 |
| 📊 거래량 증가 (1.5배+) | 2점 |
| 📈 OBV 지속 상승 | 2점 |
| ⚡ 이평선 정배열 | 3점 |
| 💚 R-사이클 건강 구간 | 2점 |
| 📈 R-사이클 기울기 상승 | 3점 |
| ⚡ R-사이클 50 돌파 | 3점 |
| 🔥 BB 수축→확장 | 3점 |
| 📊 MACD 골든크로스 | 2점 |
| 🔼 240선 상승전환 | 3점 |
| 🎯 눌림목 반등 | 3점 |
| 🏆 52주 신고가 근처 | 2점 |
| 📅 주봉 RSI 강세 | 3점 |
| 📅 주봉 RSI 상승 | 2점 |
| 💪 S&P500 아웃퍼폼 | 최대 3점 |
| 🔥 섹터 ETF 강세 | 최대 3점 |
| 🕵️ 세력 매집 감지 | 3점 |
| 🔨 망치형 캔들 | 1점 |
| 🕯 장악형 캔들 | 2점 |
| ⏳ 조정 기간 가산 | 1~3점 |
| 📉 RSI 바닥 깊이 | 1~3점 |""")
    st.markdown("---")
    st.caption("⚠️ 투자 손실에 책임지지 않습니다")

# ── 헤더 ─────────────────────────────────────────────────────────
st.markdown("""
<div class='top-header'>
  <div style='position:relative;z-index:1;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;'>
    <div>
      <div style='display:flex;align-items:center;gap:12px;margin-bottom:8px;'>
        <span style='font-size:36px;filter:drop-shadow(0 0 12px rgba(79,142,247,0.6));'>🇺🇸</span>
        <div>
          <div style='color:#e0e6f0;font-size:clamp(20px,3vw,28px);font-weight:900;letter-spacing:-0.5px;'>
            미국 주식 스윙 레이더
          </div>
          <div style='color:#4f8ef7;font-size:11px;font-weight:700;letter-spacing:3px;margin-top:2px;'>
            US SWING RADAR · R-CYCLE + MA240
          </div>
        </div>
      </div>
      <div style='color:#6b7280;font-size:13px;'>
        나스닥100 · S&P500 · ETF | 달러($) 기준 | 매일 새벽 자동 스캔
      </div>
    </div>
    <div style='text-align:right;'>
      <div style='color:#8b92a5;font-size:11px;margin-bottom:4px;'>스캔 대상</div>
      <div style='color:#00d4aa;font-size:28px;font-weight:900;'>177+</div>
      <div style='color:#6b7280;font-size:11px;'>종목</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# 종목 선택
cats = get_symbols_by_category()
symbols = ALL_SYMBOLS if category == "전체" else cats.get(category, ALL_SYMBOLS)

# 조건 박스
st.markdown(f"""<div class='cond-box'>
  <b style='color:#e0e6f0;'>스캔 조건</b><br>
  카테고리: <b style='color:#ffd700;'>{category}</b> ({len(symbols)}개) &nbsp;|&nbsp;
  장기선 근처 <b style='color:#ffd700;'>{max_gap}%</b> 이내 &nbsp;|&nbsp;
  R-사이클 70 이탈 후 <b style='color:#ffd700;'>{ob_days}일</b> 이내 &nbsp;|&nbsp;
  최소 <b style='color:#ffd700;'>{min_score}점</b>
</div>""", unsafe_allow_html=True)

# ── 스캔 버튼 + 진행 게이지 (오른쪽 화면) ───────────────────────
btn_col1, btn_col2, btn_col3 = st.columns([2, 1, 1])
with btn_col1:
    scan_btn = st.button("🔍 스캔 시작", type="primary", use_container_width=True, key="us_scan")
with btn_col2:
    alert_btn = st.button("📡 텔레그램 전송", use_container_width=True, key="us_alert")
with btn_col3:
    if st.button("🗑️ 초기화", use_container_width=True, key="us_clear"):
        st.session_state.pop("us_results", None)
        st.rerun()

if scan_btn:
    det = USStockDetector(max_gap_pct=max_gap, ob_days=ob_days,
                          min_below_days=min_below, min_score=min_score)
    total_syms = len(symbols)
    progress_bar = st.progress(0, text=f"🇺🇸 0 / {total_syms}개 스캔 중...")
    status_text  = st.empty()
    _done_count  = [0]

    def _on_progress(done, total):
        _done_count[0] = done
        pct = done / total
        progress_bar.progress(pct, text=f"🇺🇸 {done} / {total}개 스캔 중... ({int(pct*100)}%)")

    results = det.analyze_all(symbols, progress_callback=_on_progress)
    progress_bar.progress(1.0, text=f"✅ 스캔 완료 — {total_syms}개 분석")
    st.session_state["us_results"] = results
    if results:
        status_text.success(f"✅ {len(results)}개 종목 발견")
    else:
        status_text.info("조건에 맞는 종목이 없습니다.")

if alert_btn:
    results = st.session_state.get("us_results", [])
    if results:
        with st.spinner("텔레그램 전송 중..."):
            send_us_scan_alert(results)
        st.success("텔레그램 전송 완료!")
    else:
        st.warning("먼저 스캔을 실행하세요.")

# ── 결과 표시 ─────────────────────────────────────────────────────
results = st.session_state.get("us_results", [])

if not results:
    st.markdown("""
    <div style='text-align:center;padding:80px 20px;'>
      <div style='font-size:64px;margin-bottom:16px;opacity:0.4;'>🇺🇸</div>
      <div style='color:#4a5568;font-size:16px;'>스캔 시작 버튼을 눌러주세요</div>
      <div style='color:#374151;font-size:13px;margin-top:8px;'>매일 새벽 6:30 KST 자동 스캔됩니다</div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"<div class='sec-title'>📊 스캔 결과 — {len(results)}개 종목</div>", unsafe_allow_html=True)

    for i, r in enumerate(results):
        score = r["total_score"]
        pct   = min(score / 65 * 100, 100)
        cur   = r["current_price"]
        s     = r.get("signals", {})

        card_class = "gold" if i == 0 else "silver" if i == 1 else "bronze" if i == 2 else ""
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."

        # 등락 표시 (전일 대비 없으므로 240선 대비)
        gap_color = "#00d4aa" if r["ma240_gap"] > 0 else "#ff4b6e"
        gap_arrow = "▲" if r["ma240_gap"] > 0 else "▼"

        st.markdown(f"""
        <div class='rank-card {card_class}'>
          <div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;'>
            <div>
              <span style='color:#fff;font-size:20px;font-weight:700;'>{medal} {r['name']}</span>
              <span style='color:#6b7280;font-size:13px;margin-left:8px;'>({r['symbol']})</span>
            </div>
            <div style='text-align:right;'>
              <span style='color:#fff;font-size:22px;font-weight:700;'>${cur:,.2f}</span>
              <span style='color:{gap_color};font-size:13px;margin-left:6px;'>{gap_arrow} 240선 +{r['ma240_gap']:.1f}%</span>
            </div>
          </div>
          <div style='margin-top:10px;'>
            <div style='color:#8b92a5;font-size:12px;margin-bottom:3px;'>종합점수 {score}점</div>
            <div class='bar-bg'><div class='bar-fill' style='width:{pct:.1f}%;'></div></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # 메트릭 카드
        m1, m2, m3, m4, m5 = st.columns(5)
        def mc(col, lbl, val):
            col.markdown(f"""<div class='metric-card'>
                <div class='lbl'>{lbl}</div><div class='val'>{val}</div>
            </div>""", unsafe_allow_html=True)

        mc(m1, "R-사이클(20)", f"{r['rsi']:.1f}")
        mc(m2, "240선 이격", f"+{r['ma240_gap']:.1f}%")
        mc(m3, "R-사이클 70이탈", f"{s.get('rsi_cycle_days_since', '-')}일 전")
        mc(m4, "240일선", f"${r['ma240']:,.2f}")
        stop_v = s.get("stop_price", r["ma240"] * 0.95)
        mc(m5, "손절가", f"${stop_v:,.2f}" if stop_v else "-")

        # 수급/신호 요약
        rs_str = f"S&P500 대비 {s.get('rs_vs_spy', 0):+.1f}%" if s.get("rs_vs_spy") is not None else ""
        sector_str = f"{s.get('sector_etf', '')} {s.get('sector_momentum', 0):+.1f}%" if s.get("sector_etf") else ""
        supply_label = f"💪 {rs_str}" if s.get("rs_strong") else (f"📈 {rs_str}" if s.get("rs_outperform") else "")
        st.caption(f"{supply_label}  {'|  ' + sector_str if sector_str else ''}  |  핵심신호: {score - 10}점  |  조정기간: {r['below_days']}일")

        # 신호 목록
        active = []
        if s.get("ma_align"):              active.append(f"⚡ 이평선 정배열")
        if s.get("bb_squeeze_expand"):     active.append("🔥 BB 수축→확장")
        if s.get("macd_cross"):            active.append("📊 MACD 골든크로스")
        if s.get("ma240_turning_up"):      active.append("🔼 240선 상승전환")
        if s.get("pullback_bounce"):       active.append(f"🎯 눌림목 반등 ({s.get('pullback_depth',0):.1f}%)")
        if s.get("near_52w_high"):         active.append(f"🏆 52주 신고가 근처 ({s.get('high_ratio',0):.1f}%)")
        if s.get("rsi_healthy"):           active.append(f"💚 R-사이클 건강 ({s.get('rsi',0):.1f})")
        if s.get("vol_strong"):            active.append(f"🚀 거래량 폭발 ({s.get('recent_vol_ratio',0):.1f}배)")
        elif s.get("recent_vol"):          active.append(f"📊 거래량 증가 ({s.get('recent_vol_ratio',0):.1f}배)")
        if s.get("obv_rising"):            active.append("📈 OBV 지속 상승")
        if s.get("rsi_slope_up"):          active.append("📈 R-사이클 기울기 상승")
        if s.get("rsi_cross50"):           active.append("⚡ R-사이클 50 돌파")
        if s.get("weekly_rsi_bull"):       active.append(f"📅 주봉 RSI 강세 ({s.get('weekly_rsi',50):.0f})")
        if s.get("weekly_rsi_rising"):     active.append("📅 주봉 RSI 상승 중")
        if s.get("rs_strong"):             active.append(f"💪 S&P500 아웃퍼폼 (+{s.get('rs_vs_spy',0):.1f}%)")
        if s.get("sector_momentum", 0) > 1: active.append(f"🔥 섹터 강세 ({s.get('sector_etf','')} +{s.get('sector_momentum',0):.1f}%)")
        if s.get("stealth_accumulation"):  active.append("🕵️ 세력 매집 감지")
        if s.get("hammer"):                active.append("🔨 망치형 캔들")
        if s.get("bullish_engulf"):        active.append("🕯 장악형 캔들")

        if active:
            cols = st.columns(2)
            for j, sig in enumerate(active):
                cols[j % 2].success(sig)
        else:
            st.info("추가 신호 없음 (핵심 조건만 충족)")

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

                cd = pd.DataFrame({"Open": os_, "High": hs, "Low": ls, "Close": cs})
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
                    fig.add_hrect(y0=lv["entry"], y1=lv["target"], fillcolor="rgba(0,255,136,0.08)", line_width=0)
                    if lv["entry"] < lv["current"]:
                        fig.add_hline(y=lv["entry"], line=dict(color="#ffd700", width=2, dash="dashdot"))
                        fig.add_hrect(y0=lv["stop"], y1=lv["entry"], fillcolor="rgba(255,51,85,0.08)", line_width=0)
                    fig.add_hline(y=lv["current"], line=dict(color="#ffffff", width=1.5, dash="dot"))
                    fig.add_hline(y=lv["stop"],    line=dict(color="#ff3355", width=2, dash="dash"))

                fig.update_layout(
                    title=dict(text=f"{r['name']} ({r['symbol']})", font=dict(color="#e0e6f0", size=13)),
                    paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                    font=dict(color="#8b92a5"),
                    yaxis=dict(gridcolor="#1e2540", fixedrange=True, side="right", showticklabels=True),
                    xaxis=dict(gridcolor="#1e2540", rangeslider_visible=False, fixedrange=True),
                    legend=dict(bgcolor="#1e2130", bordercolor="#2d3555", visible=False),
                    dragmode=False, height=500, margin=dict(l=0, r=50, t=30, b=0)
                )
                st.plotly_chart(fig, config={"scrollZoom": False, "displayModeBar": False, "staticPlot": True},
                                width='stretch', key=f"us_chart_{r['symbol']}_{i}")

                # 가격 레벨 카드
                if lv:
                    rr = lv["rr"]
                    rr_color = "#00ff88" if rr >= 3 else "#ffd700" if rr >= 2 else "#ff8c42"
                    rr_label = "우수" if rr >= 3 else "양호" if rr >= 2 else "주의"
                    st.markdown(f"""
                    <div style='display:flex;gap:8px;margin:-8px 0 4px;'>
                      <div style='flex:1.2;background:rgba(0,255,136,0.08);border:1px solid #00ff88;
                           border-radius:10px;padding:12px;text-align:center;'>
                        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>🎯 목표가</div>
                        <div style='color:#00ff88;font-size:18px;font-weight:700;margin:4px 0;'>${lv["target"]:,.2f}</div>
                        <div style='color:#00ff88;font-size:12px;'>+{lv["upside"]:.1f}%</div>
                        <div style='color:#4a5568;font-size:10px;margin-top:4px;'>Fib×ATR 가중평균</div>
                      </div>
                      <div style='flex:1;background:rgba(255,215,0,0.08);border:1px solid #ffd700;
                           border-radius:10px;padding:12px;text-align:center;'>
                        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>📍 매수가</div>
                        <div style='color:#ffd700;font-size:18px;font-weight:700;margin:4px 0;'>${lv["entry"]:,.2f}</div>
                        <div style='color:#ffd700;font-size:12px;'>{lv["entry_label"]} 기준</div>
                        <div style='color:#4a5568;font-size:10px;margin-top:4px;'>240선 근거 진입가</div>
                      </div>
                      <div style='flex:1;background:rgba(255,51,85,0.08);border:1px solid #ff3355;
                           border-radius:10px;padding:12px;text-align:center;'>
                        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>🛑 손절가</div>
                        <div style='color:#ff3355;font-size:18px;font-weight:700;margin:4px 0;'>${lv["stop"]:,.2f}</div>
                        <div style='color:#ff3355;font-size:12px;'>{lv["downside"]:.1f}%</div>
                        <div style='color:#4a5568;font-size:10px;margin-top:4px;'>추세이탈 기준</div>
                      </div>
                      <div style='flex:0.8;background:rgba(255,215,0,0.08);border:1px solid {rr_color};
                           border-radius:10px;padding:12px;text-align:center;'>
                        <div style='color:#8b92a5;font-size:10px;letter-spacing:1px;'>⚖️ 손익비</div>
                        <div style='color:{rr_color};font-size:22px;font-weight:700;margin:4px 0;'>{rr:.1f}:1</div>
                        <div style='color:{rr_color};font-size:11px;'>{rr_label}</div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
            except Exception as e:
                st.caption(f"차트 오류: {e}")

        st.markdown("<hr style='border:none;border-top:1px solid #1e2540;margin:16px 0;'>", unsafe_allow_html=True)
