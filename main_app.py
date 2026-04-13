"""
통합 진입점 - 주식 / 코인 선택
기존 app.py, crypto_surge/app.py 는 전혀 수정하지 않음
"""
import streamlit as st

# 서비스 선택값을 먼저 읽어서 아이콘 결정
_service_init = st.session_state.get("service_select", "📈 주식 급등 예측")
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
        width:44px; height:44px; border-radius:50%;
        background: radial-gradient(circle at 35% 35%, #ffe066, #f7a44f 60%, #c47a00);
        border: 3px solid #ffd700;
        box-shadow: 0 0 14px rgba(247,164,79,0.6), inset 0 2px 4px rgba(255,255,255,0.4);
        display:flex; align-items:center; justify-content:center;
        font-size:20px; font-weight:900; color:#7a4800; font-family:Arial,sans-serif;
    }
    </style>
    <div style='text-align:center;padding:16px 0 8px;'>
      <div class='sb-coin-wrap'><div class='sb-coin'>₿</div></div>
      <div style='color:#f0f4ff;font-size:16px;font-weight:800;margin-top:6px;'>급등 예측 시스템</div>
    </div>
    """ if _is_crypto else """
    <div style='text-align:center;padding:16px 0 8px;'>
      <div style='font-size:32px;'>🚀</div>
      <div style='color:#f0f4ff;font-size:16px;font-weight:800;margin-top:6px;'>급등 예측 시스템</div>
    </div>
    """
    st.markdown(_sidebar_icon, unsafe_allow_html=True)
    st.markdown("---")

    service = st.radio(
        "서비스 선택",
        ["📈 주식 급등 예측", "₿ 코인 급등 예측"],
        key="service_select",
        label_visibility="collapsed"
    )
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


if service == "📈 주식 급등 예측":
    crypto_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crypto_surge")
    # crypto_surge 경로 완전 제거
    while crypto_dir in sys.path:
        sys.path.remove(crypto_dir)
    # 코인 모듈 캐시 제거
    for mod_name in list(sys.modules.keys()):
        if "crypto_surge" in mod_name or mod_name in ("cache_db", "telegram_alert", "crypto_surge_detector"):
            sys.modules.pop(mod_name, None)
    _run_app("app.py")
else:
    crypto_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crypto_surge")
    # 주식 cache_db/telegram_alert 캐시만 제거 (symbols, crypto_surge_detector는 유지)
    for mod_name in ["cache_db", "telegram_alert"]:
        sys.modules.pop(mod_name, None)
    _run_app(os.path.join(crypto_dir, "app.py"), extra_syspath=crypto_dir)
