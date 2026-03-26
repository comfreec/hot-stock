src = open('app.py', encoding='utf-8').read()

# 1. 모든 st.plotly_chart에 config 추가 (줌/툴바 비활성화)
src = src.replace(
    'use_container_width=True, key=',
    'config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key='
)
src = src.replace(
    'use_container_width=True)',
    'config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True)'
)

# 2. 모바일 최적화 CSS 교체
old_css = 'st.markdown("""<style>\n.top-header{'
new_css = '''st.markdown("""<style>
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

.top-header{'''

if old_css in src:
    src = src.replace(old_css, new_css)
    print("CSS 교체 완료")
else:
    print("WARNING: CSS 시작점 못찾음")

# 3. 차트 높이 모바일 대응 (height 고정값 → 반응형)
# 캔들 차트 높이 450 → 380
src = src.replace('height=450, margin=dict(l=10,r=10,t=40,b=10))', 'height=380, margin=dict(l=0,r=0,t=30,b=0))')
# RSI 차트 높이 200 → 160
src = src.replace('height=200, margin=dict(l=60,r=10,t=30,b=10),', 'height=160, margin=dict(l=40,r=5,t=25,b=5),')
# 요약 차트 높이 300 → 240
src = src.replace('coloraxis_showscale=False,height=300,margin=dict(l=10,r=10,t=40,b=60))',
                  'coloraxis_showscale=False,height=240,margin=dict(l=5,r=5,t=30,b=50))')
src = src.replace('font=dict(color="#8b92a5"),height=300,margin=dict(l=10,r=10,t=40,b=10))',
                  'font=dict(color="#8b92a5"),height=240,margin=dict(l=5,r=5,t=30,b=5))')

# 4. 헤더 폰트 크기 모바일 대응
src = src.replace(
    '<h1 style="color:#fff;margin:0;font-size:30px;">🚀 한국 주식 급등 예측 시스템 v3.0</h1>',
    '<h1 style="color:#fff;margin:0;font-size:clamp(18px,4vw,30px);">🚀 한국 주식 급등 예측 시스템 v3.0</h1>'
)

# 5. 종목 카드 폰트 모바일 대응
src = src.replace(
    'font-size:18px;font-weight:700;margin-left:8px;">{r["name"]}</span>',
    'font-size:clamp(14px,3vw,18px);font-weight:700;margin-left:6px;">{r["name"]}</span>'
)
src = src.replace(
    'font-size:20px;font-weight:700;">₩{r["current_price"]:,.0f}</span>',
    'font-size:clamp(14px,3vw,20px);font-weight:700;">₩{r["current_price"]:,.0f}</span>'
)

# 6. set_page_config에 모바일 뷰포트 메타 추가
src = src.replace(
    'st.set_page_config(page_title="한국 주식 급등 예측", page_icon="🚀", layout="wide")',
    'st.set_page_config(page_title="한국 주식 급등 예측", page_icon="🚀", layout="wide", initial_sidebar_state="collapsed")'
)

import ast
ast.parse(src)
print("문법 OK")
open('app.py', 'w', encoding='utf-8').write(src)
print("완료")
