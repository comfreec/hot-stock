"""
통합 진입점 - 주식 / 코인 선택
기존 app.py, crypto_surge/app.py 는 전혀 수정하지 않음
"""
import streamlit as st

# 서비스 선택값을 먼저 읽어서 아이콘 결정
_service_init = st.session_state.get("service_select", "📡 주식")
_icon = "🚀"
_title = "코인 급등 예측" if "코인" in _service_init else "주식 급등 예측"

st.set_page_config(
    page_title=_title,
    page_icon=_icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── 서비스 선택 ───────────────────────────────────────────────────
with st.sidebar:
    _is_crypto = "코인" in st.session_state.get("service_select", "")
    _sidebar_icon = """
    <style>
    @keyframes coin_spin {
        0%   { transform: rotateY(0deg) translateY(0px); }
        25%  { transform: rotateY(90deg) translateY(-8px); }
        50%  { transform: rotateY(180deg) translateY(0px); }
        75%  { transform: rotateY(270deg) translateY(-8px); }
        100% { transform: rotateY(360deg) translateY(0px); }
    }
    .sb-coin-wrap { display:inline-block; animation: coin_spin 2.5s linear infinite; }
    .sb-coin {
        width:96px; height:96px; border-radius:50%;
        background: radial-gradient(circle at 35% 35%, #ffe066, #f7a44f 60%, #c47a00);
        border: 3px solid #ffd700;
        box-shadow: 0 0 18px rgba(247,164,79,0.7);
        display:flex; align-items:center; justify-content:center;
        font-size:44px; font-weight:900; color:#7a4800; font-family:Arial,sans-serif;
    }
    </style>
    <div style='text-align:center;padding:16px 0 8px;'>
      <div class='sb-coin-wrap'><div class='sb-coin'>₿</div></div>
    </div>
    """ if _is_crypto else """
    <style>
    @keyframes radar_spin2 { 0%{transform:rotate(0deg)} 100%{transform:rotate(360deg)} }
    @keyframes radar_pulse2 {
        0%,100%{box-shadow:0 0 0 0 rgba(0,212,170,0.4),0 0 16px rgba(79,142,247,0.3);}
        50%{box-shadow:0 0 0 10px rgba(0,212,170,0),0 0 32px rgba(79,142,247,0.6);}
    }
    .sb-radar-wrap {
        width:96px;height:96px;border-radius:50%;
        background:linear-gradient(135deg,#0d1528,#1a2540);
        border:2px solid #4f8ef7;
        display:flex;align-items:center;justify-content:center;
        margin:0 auto;position:relative;overflow:hidden;
        animation:radar_pulse2 2s ease-in-out infinite;
    }
    .sb-radar-sweep {
        position:absolute;width:50%;height:50%;top:0;left:50%;
        transform-origin:bottom left;
        background:linear-gradient(135deg,rgba(0,212,170,0.6),transparent);
        animation:radar_spin2 2s linear infinite;
        border-radius:100% 0 0 0;
    }
    .sb-radar-icon{font-size:44px;z-index:1;position:relative;}
    </style>
    <div style='text-align:center;padding:16px 0 8px;'>
      <div class='sb-radar-wrap'>
        <div class='sb-radar-sweep'></div>
        <div class='sb-radar-icon'>📡</div>
      </div>
    </div>
    """
    st.markdown(_sidebar_icon, unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("""<style>
    div[data-testid="stRadio"] { display:none !important; }
    section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button p {
        font-size: 36px !important; line-height:1.4 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button {
        padding: 12px 0 !important;
    }
    </style>""", unsafe_allow_html=True)

    if "service_select" not in st.session_state:
        st.session_state["service_select"] = "📡 주식"

    service = st.session_state["service_select"]
    is_stock = service == "📡 주식"
    is_coin = service == "₿ 코인"
    is_admin = service == "🔐 관리자"

    col_s, col_c, col_a = st.columns(3)
    with col_s:
        if st.button("📡", key="btn_stock", use_container_width=True,
                     type="primary" if is_stock else "secondary"):
            st.session_state["service_select"] = "📡 주식"
            st.session_state["close_sidebar"] = True
            st.rerun()
    with col_c:
        if st.button("₿", key="btn_coin", use_container_width=True,
                     type="primary" if is_coin else "secondary"):
            st.session_state["service_select"] = "₿ 코인"
            st.session_state["close_sidebar"] = True
            st.rerun()
    with col_a:
        if st.button("🔐", key="btn_admin", use_container_width=True,
                     type="primary" if is_admin else "secondary"):
            st.session_state["service_select"] = "🔐 관리자"
            st.session_state["close_sidebar"] = True
            st.rerun()

    if st.session_state.pop("close_sidebar", False):
        st.markdown("""<script>
        setTimeout(function() {
            var btns = window.parent.document.querySelectorAll('button');
            for(var b of btns) {
                if(b.getAttribute('data-testid') === 'stSidebarCollapseButton' ||
                   b.closest('[data-testid="stSidebarCollapseButton"]')) {
                    b.click(); break;
                }
            }
            // fallback: aria-label로 찾기
            var close = window.parent.document.querySelector('button[aria-label="Close sidebar"]');
            if(close) close.click();
        }, 100);
        </script>""", unsafe_allow_html=True)

    st.markdown("---")

# ── 선택된 앱 실행 ────────────────────────────────────────────────
import sys, os, types

def _run_app(filepath: str, extra_syspath: str = None):
    """
    지정된 파일을 현재 Streamlit 컨텍스트에서 실행.
    set_page_config 호출은 이미 위에서 했으므로 해당 줄만 무력화.
    """
    if extra_syspath and extra_syspath not in sys.path:
        sys.path.insert(0, extra_syspath)

    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    # set_page_config 호출 제거 (이미 main_app.py에서 호출함)
    import re
    source = re.sub(
        r'st\.set_page_config\s*\([^)]*\)',
        '# set_page_config skipped by main_app',
        source,
        flags=re.DOTALL
    )

    # 모듈 네임스페이스 생성
    mod = types.ModuleType("__streamlit_app__")
    mod.__file__ = os.path.abspath(filepath)
    mod.__name__ = "__main__"

    # 작업 디렉토리를 앱 파일 위치로 변경 (상대 import 대응)
    orig_dir = os.getcwd()
    app_dir  = os.path.dirname(os.path.abspath(filepath))
    os.chdir(app_dir)

    try:
        exec(compile(source, filepath, "exec"), mod.__dict__)
    finally:
        os.chdir(orig_dir)
        if extra_syspath and extra_syspath in sys.path:
            sys.path.remove(extra_syspath)


if service == "📡 주식":
    crypto_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crypto_surge")
    while crypto_dir in sys.path:
        sys.path.remove(crypto_dir)
    for mod_name in list(sys.modules.keys()):
        if "crypto_surge" in mod_name or mod_name in ("cache_db", "telegram_alert", "crypto_surge_detector"):
            sys.modules.pop(mod_name, None)
    _run_app("app.py")
elif service == "₿ 코인":
    crypto_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crypto_surge")
    for mod_name in ["cache_db", "telegram_alert"]:
        sys.modules.pop(mod_name, None)
    _run_app(os.path.join(crypto_dir, "app.py"), extra_syspath=crypto_dir)
else:  # 🔐 관리자
    _run_app("admin_app.py")