src = open('app.py', encoding='utf-8').read()

# 모든 st.plotly_chart 호출에 config 추가
# 이미 config가 있는 건 건너뜀
old = 'use_container_width=True, key='
new = 'config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key='

src = src.replace(old, new)

# config 없는 나머지 호출도 처리
old2 = 'use_container_width=True)'
new2 = 'config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True)'
src = src.replace(old2, new2)

import ast
ast.parse(src)
print('문법 OK')
open('app.py', 'w', encoding='utf-8').write(src)
print('완료')
