"""
자동매매 관리자 페이지
- 유저 등록/수정/삭제
- 유저별 포트폴리오 조회
- 전체 통계
"""
import streamlit as st
import os
import pandas as pd

# 로컬 .env 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from datetime import datetime, date
from auto_trader_multi import (
    get_active_users, get_user, register_user, update_user_settings,
    delete_user, _get_conn, UserKISClient, _get_pending_orders
)

st.title("🔐 자동매매 관리자")

# ── 인증 ─────────────────────────────────────────────────────────
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

if "admin_auth" not in st.session_state:
    st.session_state["admin_auth"] = False

if not st.session_state["admin_auth"]:
    with st.form("admin_login"):
        pw = st.text_input("관리자 비밀번호", type="password")
        if st.form_submit_button("로그인"):
            if pw == ADMIN_PASSWORD:
                st.session_state["admin_auth"] = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
    st.stop()

# ── 탭 구성 ──────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📊 대시보드", "👥 유저 관리", "➕ 유저 등록", "📈 전체 통계"])

# ── 대시보드 ─────────────────────────────────────────────────────
with tab1:
    st.subheader("활성 유저 현황")
    users = get_active_users()
    
    if not users:
        st.info("등록된 유저가 없습니다.")
    else:
        cols = st.columns(4)
        cols[0].metric("총 유저", len(users))
        mock_count = sum(1 for u in users if u.get("mock"))
        cols[1].metric("모의투자", mock_count)
        cols[2].metric("실전투자", len(users) - mock_count)
        
        # 전체 보유 종목 수
        total_positions = 0
        for u in users:
            orders = _get_pending_orders(u["user_id"])
            total_positions += len([o for o in orders if o["status"] == "active"])
        cols[3].metric("전체 보유 종목", total_positions)
        
        st.markdown("---")
        
        # 유저별 간단 현황
        for u in users:
            with st.expander(f"📌 {u['chat_id']} ({u['account']})"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**모드:** {'모의' if u.get('mock') else '실전'}투자")
                    st.write(f"**예산:** ₩{u.get('budget_per', 0):,} / 종목")
                    st.write(f"**최대 종목:** {u.get('max_stocks', 3)}개")
                
                with col2:
                    orders = _get_pending_orders(u["user_id"])
                    active = [o for o in orders if o["status"] == "active"]
                    pending = [o for o in orders if o["status"] == "pending"]
                    st.write(f"**보유 중:** {len(active)}종목")
                    st.write(f"**매수 대기:** {len(pending)}종목")
                    
                    # 간단 잔고 조회
                    try:
                        client = UserKISClient(u)
                        balance = client.get_balance()
                        st.write(f"**예수금:** ₩{balance.get('cash', 0):,.0f}")
                    except:
                        st.write("**예수금:** 조회 실패")

# ── 유저 관리 ─────────────────────────────────────────────────────
with tab2:
    st.subheader("유저 목록")
    
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM trader_users ORDER BY created_at DESC").fetchall()
    conn.close()
    
    if not rows:
        st.info("등록된 유저가 없습니다.")
    else:
        for row in rows:
            u = dict(row)
            status = "🟢 활성" if u["is_active"] else "🔴 중지"
            mode = "모의" if u["mock"] else "실전"
            
            with st.expander(f"{status} {u['chat_id']} - {u['account']} [{mode}]"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**User ID:** {u['user_id']}")
                    st.write(f"**Chat ID:** {u['chat_id']}")
                    st.write(f"**계좌번호:** {u['account']}")
                    st.write(f"**등록일:** {u['created_at'][:10]}")
                    
                    # 설정 수정 폼
                    with st.form(f"edit_{u['user_id']}"):
                        st.write("**설정 수정**")
                        new_budget = st.number_input("종목당 예산", value=u["budget_per"], step=10000, key=f"budget_{u['user_id']}")
                        new_stocks = st.number_input("최대 종목", value=u["max_stocks"], min_value=1, max_value=10, key=f"stocks_{u['user_id']}")
                        new_days = st.number_input("만료일", value=u["max_days"], min_value=1, max_value=20, key=f"days_{u['user_id']}")
                        new_mock = st.selectbox("모드", ["모의투자", "실전투자"], index=0 if u["mock"] else 1, key=f"mock_{u['user_id']}")
                        new_active = st.checkbox("활성화", value=bool(u["is_active"]), key=f"active_{u['user_id']}")
                        
                        if st.form_submit_button("💾 저장"):
                            update_user_settings(
                                u["chat_id"],
                                budget_per=new_budget,
                                max_stocks=new_stocks,
                                max_days=new_days,
                                mock=1 if new_mock == "모의투자" else 0,
                                is_active=1 if new_active else 0
                            )
                            st.success("저장 완료!")
                            st.rerun()
                
                with col2:
                    st.write("")
                    st.write("")
                    # 삭제 확인 단계
                    confirm_key = f"confirm_del_{u['user_id']}"
                    if st.session_state.get(confirm_key):
                        st.warning("정말 삭제?")
                        c1, c2 = st.columns(2)
                        if c1.button("✅ 확인", key=f"yes_{u['user_id']}", type="primary"):
                            conn2 = _get_conn()
                            conn2.execute("DELETE FROM trader_users WHERE chat_id=?", (u["chat_id"],))
                            conn2.execute("DELETE FROM trade_orders_multi WHERE user_id=?", (u["user_id"],))
                            conn2.commit()
                            conn2.close()
                            st.session_state.pop(confirm_key, None)
                            st.success("삭제 완료!")
                            st.rerun()
                        if c2.button("❌ 취소", key=f"no_{u['user_id']}"):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                    else:
                        if st.button("🗑 삭제", key=f"del_{u['user_id']}", type="secondary"):
                            st.session_state[confirm_key] = True
                            st.rerun()
                
                # 보유 종목 상세
                orders = _get_pending_orders(u["user_id"])
                if orders:
                    st.write("**보유/대기 종목:**")
                    for o in orders:
                        status_icon = "🟢" if o["status"] == "active" else "⏳"
                        step_icon = "🔵" * o.get("split_step", 1) + "⚪" * (3 - o.get("split_step", 1))
                        st.write(f"{status_icon} {o['name']} {step_icon} - ₩{o.get('avg_price', o['entry_price']):,.0f} × {o['qty']}주")

# ── 유저 등록 ─────────────────────────────────────────────────────
with tab3:
    col_title, col_clear = st.columns([4, 1])
    col_title.subheader("신규 유저 등록")
    if col_clear.button("🔄 초기화", key="clear_form"):
        st.session_state["reg_form_ver"] = st.session_state.get("reg_form_ver", 0) + 1
        st.rerun()

    form_ver = st.session_state.get("reg_form_ver", 0)
    with st.form(f"register_user_{form_ver}"):
        chat_id = st.text_input("텔레그램 Chat ID", help="숫자만 입력 (예: 1663019049) - 봇에서 /start 후 확인", key=f"reg_chat_id_{form_ver}")
        app_key = st.text_input("KIS APP KEY", type="password", help="한국투자증권 Open API 앱키 (영숫자 36자)", key=f"reg_app_key_{form_ver}")
        app_secret = st.text_input("KIS APP SECRET", type="password", help="한국투자증권 Open API 시크릿 (영숫자+특수문자)", key=f"reg_app_secret_{form_ver}")
        account = st.text_input("계좌번호", placeholder="50123456-01", help="8자리-2자리 형식 (예: 50123456-01)", key=f"reg_account_{form_ver}")        
        col1, col2 = st.columns(2)
        with col1:
            mock = st.selectbox("투자 모드", ["모의투자", "실전투자"])
        with col2:
            budget = st.number_input("종목당 예산 (원)", value=300000, step=10000)
        
        col3, col4 = st.columns(2)
        with col3:
            max_stocks = st.number_input("최대 보유 종목", value=3, min_value=1, max_value=10)
        with col4:
            max_days = st.number_input("미체결 만료일", value=5, min_value=1, max_value=20)
        
        if st.form_submit_button("✅ 등록", type="primary"):
            import re
            errors = []

            # Chat ID: 숫자만 (텔레그램 ID는 정수)
            if not chat_id:
                errors.append("Chat ID를 입력해주세요.")
            elif not re.fullmatch(r"-?\d+", chat_id.strip()):
                errors.append("Chat ID는 숫자만 입력하세요. (예: 1663019049)")

            # APP KEY: 영숫자 40자 이상
            if not app_key:
                errors.append("KIS APP KEY를 입력해주세요.")
            elif len(app_key.strip()) < 20:
                errors.append("APP KEY가 너무 짧습니다. KIS 발급 키를 확인하세요.")

            # APP SECRET: 영숫자 특수문자 포함 충분한 길이
            if not app_secret:
                errors.append("KIS APP SECRET을 입력해주세요.")
            elif len(app_secret.strip()) < 20:
                errors.append("APP SECRET이 너무 짧습니다. KIS 발급 시크릿을 확인하세요.")

            # 계좌번호: 8자리-2자리 형식
            if not account:
                errors.append("계좌번호를 입력해주세요.")
            elif not re.fullmatch(r"\d{8}-\d{2}", account.strip()):
                errors.append("계좌번호 형식이 올바르지 않습니다. (예: 50123456-01)")

            # 예산: 최소 10만원 이상
            if budget < 100000:
                errors.append("종목당 예산은 최소 100,000원 이상이어야 합니다.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                try:
                    result = register_user(chat_id.strip(), app_key.strip(), app_secret.strip(),
                                           account.strip(), mock == "모의투자")
                    update_user_settings(chat_id.strip(), budget_per=budget,
                                         max_stocks=max_stocks, max_days=max_days)
                    action = "업데이트" if result == "updated" else "등록"
                    st.success(f"✅ 유저 {action} 완료!")
                    st.balloons()
                except Exception as e:
                    st.error(f"등록 실패: {e}")

# ── 전체 통계 ─────────────────────────────────────────────────────
with tab4:
    st.subheader("전체 거래 통계")
    
    conn = _get_conn()
    
    # 전체 청산 내역
    closed = conn.execute("""
        SELECT name, symbol, return_pct, status, exit_date, user_id
        FROM trade_orders_multi
        WHERE status IN ('hit_target', 'hit_stop') AND return_pct IS NOT NULL
        ORDER BY exit_date DESC
        LIMIT 50
    """).fetchall()
    
    if closed:
        df = pd.DataFrame(closed, columns=["종목명", "심볼", "수익률(%)", "상태", "청산일", "유저ID"])
        df["수익률(%)"] = df["수익률(%)"].round(2)
        df["상태"] = df["상태"].map({"hit_target": "✅ 목표가", "hit_stop": "🛑 손절"})
        
        col1, col2, col3, col4 = st.columns(4)
        avg_ret = df["수익률(%)"].mean()
        win_rate = (df["수익률(%)"] > 0).sum() / len(df) * 100
        total_trades = len(df)
        best_ret = df["수익률(%)"].max()
        
        col1.metric("평균 수익률", f"{avg_ret:.2f}%")
        col2.metric("승률", f"{win_rate:.1f}%")
        col3.metric("총 거래", f"{total_trades}건")
        col4.metric("최고 수익", f"+{best_ret:.1f}%")
        
        st.markdown("---")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("청산 내역이 없습니다.")
    
    conn.close()

# ── 로그아웃 ─────────────────────────────────────────────────────
st.sidebar.markdown("---")
if st.sidebar.button("🚪 로그아웃"):
    st.session_state["admin_auth"] = False
    st.rerun()
