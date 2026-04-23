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
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "comfreec")

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
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 대시보드", "👥 유저 관리", "➕ 유저 등록", "📈 전체 통계", "🔄 Fly 동기화"])

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
        search = st.text_input("🔍 검색", placeholder="이름, Chat ID, 계좌번호, 연락처로 검색", key="user_search")
        filtered = []
        for row in rows:
            u = dict(row)
            kw = search.strip().lower()
            if not kw or any(kw in str(u.get(f, "")).lower()
                             for f in ("name", "chat_id", "account", "contact")):
                filtered.append(u)

        st.caption(f"총 {len(filtered)}명" + (" (검색 결과)" if search else ""))

        for u in filtered:
            status = "🟢 활성" if u["is_active"] else "🔴 중지"
            mode = "모의" if u["mock"] else "실전"
            label_name = u.get("name") or u["chat_id"]

            with st.expander(f"{status} {label_name} - {u['account']} [{mode}]"):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.write(f"**User ID:** {u['user_id']}")
                    st.write(f"**이름:** {u.get('name') or '-'}")
                    st.write(f"**Chat ID:** {u['chat_id']}")
                    st.write(f"**계좌번호:** {u['account']}")
                    st.write(f"**연락처:** {u.get('contact') or '-'}")
                    st.write(f"**등록일:** {u['created_at'][:10]}")
                    
                    # 설정 수정 폼
                    with st.form(f"edit_{u['user_id']}"):
                        st.write("**설정 수정**")
                        new_name    = st.text_input("이름", value=u.get("name") or "", key=f"name_{u['user_id']}")
                        new_contact = st.text_input("연락처", value=u.get("contact") or "", key=f"contact_{u['user_id']}")
                        new_account = st.text_input("계좌번호", value=u.get("account") or "", placeholder="50123456-01", key=f"account_{u['user_id']}")
                        new_mock    = st.selectbox("투자 모드", ["모의투자", "실전투자"], index=0 if u["mock"] else 1, key=f"mock_{u['user_id']}")

                        st.caption("🔑 KEY 변경 시에만 입력 (비워두면 기존 유지)")
                        new_app_key    = st.text_input("KIS APP KEY (변경 시)", type="password", placeholder="변경 시에만 입력", key=f"appkey_{u['user_id']}")
                        new_app_secret = st.text_input("KIS APP SECRET (변경 시)", type="password", placeholder="변경 시에만 입력", key=f"appsecret_{u['user_id']}")

                        new_budget  = st.number_input("종목당 예산", value=u["budget_per"], step=100000, key=f"budget_{u['user_id']}")
                        new_stocks  = st.number_input("최대 종목", value=u["max_stocks"], min_value=1, max_value=30, key=f"stocks_{u['user_id']}")
                        new_days    = st.number_input("만료일 (거래일)", value=u["max_days"], min_value=1, max_value=20, key=f"days_{u['user_id']}")
                        new_active  = st.checkbox("활성화", value=bool(u["is_active"]), key=f"active_{u['user_id']}")

                        if st.form_submit_button("💾 저장"):
                            import re
                            save_kwargs = dict(
                                name=new_name, contact=new_contact,
                                account=new_account.strip(),
                                mock=1 if new_mock == "모의투자" else 0,
                                budget_per=new_budget, max_stocks=new_stocks,
                                max_days=new_days,
                                is_active=1 if new_active else 0
                            )
                            # KEY 변경 시에만 업데이트
                            if new_app_key.strip() and new_app_secret.strip():
                                if len(new_app_key.strip()) < 20:
                                    st.error("APP KEY가 너무 짧습니다.")
                                elif len(new_app_secret.strip()) < 20:
                                    st.error("APP SECRET이 너무 짧습니다.")
                                else:
                                    # register_user로 KEY 업데이트 (암호화 포함)
                                    from auto_trader_multi import register_user as _reg
                                    _reg(u["chat_id"], new_app_key.strip(), new_app_secret.strip(),
                                         new_account.strip(), new_mock == "모의투자",
                                         new_contact.strip(), new_name.strip())
                                    update_user_settings(u["chat_id"], **save_kwargs)
                                    st.success("저장 완료! (KEY 변경됨)")
                                    # KIS 연결 재검증
                                    try:
                                        from auto_trader_multi import UserKISClient, get_all_users
                                        users_all = get_all_users()
                                        target = next((x for x in users_all if x["chat_id"] == u["chat_id"]), None)
                                        if target:
                                            client = UserKISClient(target)
                                            token = client._get_token()
                                            if token:
                                                bal = client.get_balance()
                                                st.success(f"✅ KIS 연결 확인! 예수금: ₩{bal.get('cash',0):,.0f}")
                                            else:
                                                st.error("❌ KIS 연결 실패 - KEY를 다시 확인하세요.")
                                    except Exception as ve:
                                        st.error(f"연결 확인 오류: {ve}")
                                    st.rerun()
                            else:
                                update_user_settings(u["chat_id"], **save_kwargs)
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

    # ── 발급 도움말 ──────────────────────────────────────────────
    with st.expander("📖 입력 정보 발급 방법 (클릭해서 펼치기)"):
        st.markdown("""
### 1️⃣ 텔레그램 Chat ID 확인
1. 텔레그램에서 **@userinfobot** 검색 후 `/start` 전송
2. 응답 메시지에서 **Id:** 뒤의 숫자가 Chat ID
3. 또는 **@getmyid_bot** 에서도 확인 가능
> 예시: `1663019049` (숫자만, 하이픈 없음)

---

### 2️⃣ KIS APP KEY / APP SECRET 발급
1. **한국투자증권 홈페이지** → [Open API](https://apiportal.koreainvestment.com) 접속
2. 로그인 후 **마이페이지 → API 신청** 클릭
3. **앱 등록** → 앱 이름 입력 (예: `자동매매`) → 등록
4. 등록 완료 후 **앱 상세** 페이지에서 `APP KEY` / `APP SECRET` 확인

> ⚠️ **모의투자 ↔ 실전투자 KEY는 완전히 별개입니다**
> - 모의투자 KEY로 실전 서버 접속 불가 (인증 오류)
> - 실전 전환 시 반드시 **실전투자 전용 KEY를 새로 발급**해야 합니다
> - Open API 페이지 → **실전투자 신청** 탭에서 별도 발급

---

### 3️⃣ 계좌번호 형식
- 한국투자증권 계좌번호: `8자리-2자리` 형식
- 예: `50123456-01`
- HTS/MTS 로그인 후 계좌 선택 화면에서 확인

---

### 4️⃣ 투자 모드
- **모의투자**: 실제 돈 없이 테스트 (모의투자 KEY 필요)
- **실전투자**: 실제 계좌로 자동매매 (실전 KEY 필요)
> ⚠️ 처음에는 반드시 **모의투자**로 먼저 테스트하세요!
        """)

    form_ver = st.session_state.get("reg_form_ver", 0)
    with st.form(f"register_user_{form_ver}"):
        chat_id = st.text_input(
            "텔레그램 Chat ID *",
            placeholder="예: 1663019049",
            help="@userinfobot 에서 확인 가능. 숫자만 입력",
            key=f"reg_chat_id_{form_ver}"
        )
        name = st.text_input("이름", placeholder="홍길동", help="유저 식별용 이름", key=f"reg_name_{form_ver}")
        app_key = st.text_input(
            "KIS APP KEY *",
            type="password",
            placeholder="한국투자증권 Open API 앱키 (36자)",
            help="apiportal.koreainvestment.com → 앱 등록 후 발급",
            key=f"reg_app_key_{form_ver}"
        )
        app_secret = st.text_input(
            "KIS APP SECRET *",
            type="password",
            placeholder="한국투자증권 Open API 시크릿",
            help="APP KEY와 함께 발급되는 시크릿 키",
            key=f"reg_app_secret_{form_ver}"
        )
        account = st.text_input(
            "계좌번호 *",
            placeholder="50123456-01",
            help="8자리-2자리 형식. HTS/MTS 계좌 선택 화면에서 확인",
            key=f"reg_account_{form_ver}"
        )
        contact = st.text_input("연락처", placeholder="010-1234-5678", help="관리자 연락용 (선택)", key=f"reg_contact_{form_ver}")

        col1, col2 = st.columns(2)
        with col1:
            mock = st.selectbox("투자 모드", ["모의투자", "실전투자"], help="처음에는 모의투자로 테스트 권장")
        with col2:
            budget = st.number_input("종목당 예산 (원)", value=1000000, step=100000, help="기본값 100만원")

        col3, col4 = st.columns(2)
        with col3:
            max_stocks = st.number_input("최대 보유 종목", value=20, min_value=1, max_value=30, help="기본값 20개")
        with col4:
            max_days = st.number_input("미체결 만료일 (거래일)", value=7, min_value=1, max_value=20)
        
        if st.form_submit_button("✅ 등록", type="primary"):
            import re
            errors = []

            if not chat_id:
                errors.append("Chat ID를 입력해주세요.")
            elif not re.fullmatch(r"-?\d+", chat_id.strip()):
                errors.append("Chat ID는 숫자만 입력하세요. (예: 1663019049)")

            if not app_key:
                errors.append("KIS APP KEY를 입력해주세요.")
            elif len(app_key.strip()) < 20:
                errors.append("APP KEY가 너무 짧습니다. KIS 발급 키를 확인하세요.")

            if not app_secret:
                errors.append("KIS APP SECRET을 입력해주세요.")
            elif len(app_secret.strip()) < 20:
                errors.append("APP SECRET이 너무 짧습니다. KIS 발급 시크릿을 확인하세요.")

            if not account:
                errors.append("계좌번호를 입력해주세요.")
            elif not re.fullmatch(r"\d{8}-\d{2}", account.strip()):
                errors.append("계좌번호 형식이 올바르지 않습니다. (예: 50123456-01)")

            if budget < 100000:
                errors.append("종목당 예산은 최소 100,000원 이상이어야 합니다.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                try:
                    result = register_user(chat_id.strip(), app_key.strip(), app_secret.strip(),
                                           account.strip(), mock == "모의투자",
                                           contact.strip(), name.strip())
                    update_user_settings(chat_id.strip(), budget_per=budget,
                                         max_stocks=max_stocks, max_days=max_days)
                    action = "업데이트" if result == "updated" else "등록"
                    st.success(f"✅ 유저 {action} 완료!")

                    # ── KIS API 연결 검증 ──────────────────────────
                    with st.spinner("KIS API 연결 확인 중..."):
                        try:
                            from auto_trader_multi import UserKISClient, get_all_users
                            users = get_all_users()
                            target = next((u for u in users if u["chat_id"] == chat_id.strip()), None)
                            if target:
                                client = UserKISClient(target)
                                token = client._get_token()
                                if token:
                                    balance = client.get_balance()
                                    cash = balance.get("cash", 0)
                                    mode_str = "모의투자" if mock == "모의투자" else "실전투자"
                                    st.success(f"✅ KIS API 연결 성공! [{mode_str}] 예수금: ₩{cash:,.0f}")
                                else:
                                    st.error("❌ KIS API 토큰 발급 실패 - APP KEY/SECRET을 확인하세요.")
                            else:
                                st.warning("유저 조회 실패 - 페이지를 새로고침 후 확인하세요.")
                        except Exception as ve:
                            st.error(f"❌ KIS API 연결 실패: {ve}\nAPP KEY/SECRET/계좌번호를 다시 확인하세요.")

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


# ── Fly 동기화 ────────────────────────────────────────────────────
with tab5:
    st.subheader("🔄 Fly.io 동기화")
    st.info("로컬에서 등록/수정한 유저 데이터와 스캔 전략 설정을 Fly.io 서버에 동기화합니다.")

    col_a, col_b = st.columns(2)

    # ── 유저 동기화 ──────────────────────────────────────────────
    with col_a:
        st.markdown("#### 👥 유저 동기화")
        local_users = get_active_users()
        st.write(f"로컬 유저: **{len(local_users)}명**")
        for u in local_users:
            mode = "모의" if u.get("mock") else "실전"
            st.write(f"  - {u.get('name') or u['chat_id']} [{mode}]")

        if st.button("🚀 유저 → Fly 동기화", type="primary", key="sync_fly_users"):
            with st.spinner("유저 동기화 중..."):
                try:
                    from _sync_users_to_fly import sync
                    import io, sys
                    old_stdout = sys.stdout
                    sys.stdout = buf = io.StringIO()
                    sync()
                    sys.stdout = old_stdout
                    st.success("✅ 유저 동기화 완료!")
                    st.code(buf.getvalue())
                except Exception as e:
                    st.error(f"❌ 실패: {e}")

    # ── 전략 설정 동기화 ─────────────────────────────────────────
    with col_b:
        st.markdown("#### 🎯 스캔 전략 동기화")
        try:
            from cache_db import load_app_setting, save_app_setting
            _mode_map = {
                "rcycle":     "🔄 R-cycle 스캔",
                "classic":    "📈 장기선 돌파 스캔",
                "both":       "🔀 둘 다 실행",
                "divergence": "📉 RSI 다이버전스 스캔",
            }
            _mode_map_rev = {v: k for k, v in _mode_map.items()}
            _cur = load_app_setting("scan_mode", "rcycle")
            st.write(f"현재 로컬 설정: **{_mode_map.get(_cur, _cur)}**")

            _sel = st.selectbox(
                "Fly에 적용할 전략",
                list(_mode_map.values()),
                index=list(_mode_map.keys()).index(_cur) if _cur in _mode_map else 0,
                key="admin_fly_strategy"
            )

            if st.button("💾 전략 → Fly 동기화", type="primary", key="sync_fly_strategy"):
                with st.spinner("전략 동기화 중..."):
                    try:
                        _val = _mode_map_rev.get(_sel, "rcycle")
                        # 로컬 저장
                        save_app_setting("scan_mode", _val)

                        # fly DB에 직접 저장
                        import subprocess, tempfile, os
                        script = f"""
import sqlite3
conn = sqlite3.connect('/data/scan_cache.db')
conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)")
conn.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('scan_mode', '{_val}', datetime('now'))")
conn.commit()
conn.close()
print('OK: scan_mode =', '{_val}')
"""
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                            f.write(script)
                            tmp_path = f.name

                        # fly sftp로 업로드 후 실행
                        r1 = subprocess.run(
                            ["flyctl", "ssh", "sftp", "put", tmp_path, "/app/_set_strategy.py", "--app", "hot-stock-app"],
                            capture_output=True, text=True
                        )
                        r2 = subprocess.run(
                            ["flyctl", "ssh", "console", "--app", "hot-stock-app", "-C", "python /app/_set_strategy.py"],
                            capture_output=True, text=True
                        )
                        os.unlink(tmp_path)

                        if "OK:" in r2.stdout:
                            st.success(f"✅ Fly 전략 저장 완료: {_sel}")
                        else:
                            st.warning(f"저장 시도됨 (확인 필요)\n{r2.stdout or r2.stderr}")
                    except Exception as e:
                        st.error(f"❌ 실패: {e}")
        except Exception as e:
            st.error(f"설정 로드 오류: {e}")

    # ── Fly DB 로컬 백업 ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 💾 Fly DB 로컬 백업")
    st.caption("fly 서버의 DB를 로컬로 다운로드합니다. 만약의 경우를 대비한 수동 백업입니다.")

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        if st.button("📥 Fly DB 다운로드", type="primary", key="dl_fly_db"):
            with st.spinner("fly DB 다운로드 중..."):
                try:
                    import subprocess, os
                    from datetime import datetime as _dt
                    fname = f"fly_backup_{_dt.now().strftime('%Y%m%d_%H%M%S')}.db"
                    r = subprocess.run(
                        ["flyctl", "ssh", "sftp", "get", "/data/scan_cache.db", fname, "--app", "hot-stock-app"],
                        capture_output=True, text=True, timeout=60
                    )
                    if os.path.exists(fname):
                        size_mb = os.path.getsize(fname) / 1024 / 1024
                        st.success(f"✅ 다운로드 완료: {fname} ({size_mb:.1f}MB)")
                        # 다운로드 버튼 제공
                        with open(fname, "rb") as f:
                            st.download_button(
                                label=f"💾 {fname} 저장",
                                data=f.read(),
                                file_name=fname,
                                mime="application/octet-stream"
                            )
                    else:
                        st.error(f"❌ 다운로드 실패: {r.stderr[:200]}")
                except Exception as e:
                    st.error(f"❌ 오류: {e}")

    with col_dl2:
        if st.button("📋 Fly 백업 목록 확인", key="check_fly_backup"):
            with st.spinner("확인 중..."):
                try:
                    import subprocess
                    r = subprocess.run(
                        ["flyctl", "ssh", "console", "--app", "hot-stock-app",
                         "-C", "ls -lh /data/backup/"],
                        capture_output=True, text=True, timeout=20
                    )
                    if r.stdout:
                        st.code(r.stdout)
                    else:
                        st.info("백업 파일 없음")
                except Exception as e:
                    st.error(f"❌ 오류: {e}")

    # ── Fly 환경변수 설정 ────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ⚙️ Fly 환경변수 설정")
    st.caption("KIS 자동매매 관련 환경변수를 직접 변경합니다. 저장 시 fly 서버가 자동 재시작됩니다.")

    with st.expander("📖 모의→실전 전환 방법", expanded=False):
        st.markdown("""
1. **실전 KIS APP KEY / APP SECRET** 발급 (apiportal.koreainvestment.com → 실전투자 탭)
2. **실전 계좌번호** 확인 (8자리-2자리)
3. 아래 폼에서 KEY/SECRET/계좌번호 입력 + **KIS_MOCK = 0** 으로 변경
4. 저장 버튼 클릭 → fly 자동 재시작 (~1분)
> ⚠️ 실전 전환 후에는 실제 돈으로 주문이 실행됩니다!
        """)

    with st.form("env_form"):
        st.markdown("**🔑 KIS API 설정**")
        col1, col2 = st.columns(2)
        with col1:
            new_app_key    = st.text_input("KIS APP KEY", type="password",
                placeholder="변경 시에만 입력 (비워두면 기존 유지)",
                help="한국투자증권 Open API 앱키")
            new_account    = st.text_input("계좌번호",
                value=os.environ.get("KIS_ACCOUNT", ""),
                placeholder="50123456-01",
                help="8자리-2자리 형식")
        with col2:
            new_app_secret = st.text_input("KIS APP SECRET", type="password",
                placeholder="변경 시에만 입력 (비워두면 기존 유지)",
                help="한국투자증권 Open API 시크릿")
            new_mock       = st.selectbox("투자 모드",
                ["1 (모의투자)", "0 (실전투자)"],
                index=0 if os.environ.get("KIS_MOCK", "1") == "1" else 1,
                help="1=모의투자, 0=실전투자")

        st.markdown("**💰 매매 설정**")
        col3, col4, col5 = st.columns(3)
        with col3:
            new_budget  = st.text_input("종목당 예산 (원)",
                value=os.environ.get("KIS_BUDGET_PER", "1000000"),
                help="1차 매수 시 종목당 예산")
        with col4:
            new_stocks  = st.text_input("최대 보유 종목",
                value=os.environ.get("KIS_MAX_STOCKS", "3"))
        with col5:
            new_days    = st.text_input("미체결 만료일 (거래일)",
                value=os.environ.get("KIS_MAX_DAYS", "5"))

        if st.form_submit_button("💾 Fly 환경변수 저장", type="primary"):
            import subprocess
            with st.spinner("저장 중... (fly 재시작 약 1분 소요)"):
                try:
                    args = ["flyctl", "secrets", "set", "--app", "hot-stock-app"]
                    if new_app_key.strip():
                        args.append(f"KIS_APP_KEY={new_app_key.strip()}")
                    if new_app_secret.strip():
                        args.append(f"KIS_APP_SECRET={new_app_secret.strip()}")
                    if new_account.strip():
                        args.append(f"KIS_ACCOUNT={new_account.strip()}")
                    args.append(f"KIS_MOCK={new_mock[0]}")
                    args.append(f"KIS_BUDGET_PER={new_budget.strip()}")
                    args.append(f"KIS_MAX_STOCKS={new_stocks.strip()}")
                    args.append(f"KIS_MAX_DAYS={new_days.strip()}")

                    r = subprocess.run(args, capture_output=True, text=True, timeout=90)
                    if r.returncode == 0:
                        mode_str = "실전투자" if new_mock[0] == "0" else "모의투자"
                        st.success(f"✅ 환경변수 저장 완료! [{mode_str}] fly 재시작 중...")
                        if new_mock[0] == "0":
                            st.warning("⚠️ 실전투자 모드로 전환됐습니다. 실제 주문이 실행됩니다!")
                    else:
                        st.error(f"❌ 실패: {r.stderr[:300]}")
                except Exception as e:
                    st.error(f"❌ 오류: {e}")
