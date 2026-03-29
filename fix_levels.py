content = open('app.py', encoding='utf-8').read()

# 모든 make_candle 차트 plotly_chart 호출 뒤에 show_price_levels 추가
import re

# candle chart plotly_chart 패턴 찾아서 뒤에 show_price_levels 추가
def add_levels(m):
    s = m.group(0)
    varname = re.search(r'make_candle\(([^,)]+)', s)
    if not varname:
        return s
    # 이미 show_price_levels 있으면 스킵
    return s

# 간단하게 특정 패턴만 교체
replacements = [
    (
        'st.plotly_chart(\n                            make_candle(cd, f"{r[\'name\']} ({r[\'symbol\']}) — 2년 차트", cross_date=cross_date),\n                            config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key=f"candle_{r[\'symbol\']}")',
        '_fig_candle = make_candle(cd, f"{r[\'name\']} ({r[\'symbol\']}) — 6개월 차트", cross_date=cross_date)\n                        st.plotly_chart(_fig_candle, config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key=f"candle_{r[\'symbol\']}")\n                        show_price_levels(_fig_candle)'
    ),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f"replaced: {old[:50]}")

open('app.py', 'w', encoding='utf-8').write(content)
print('done')
