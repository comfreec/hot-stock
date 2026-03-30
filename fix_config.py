import re

with open('app.py', encoding='utf-8') as f:
    src = f.read()

cfg = 'config={"scrollZoom":False,"displayModeBar":False}, '

# width='stretch' 앞에 config 없는 경우만 추가
pattern = r'st\.plotly_chart\(([^)]+?),\s*width=\'stretch\''

def add_config(m):
    inner = m.group(1)
    if 'config=' in inner:
        return m.group(0)  # 이미 있으면 그대로
    return f"st.plotly_chart({inner}, {cfg}width='stretch'"

src = re.sub(pattern, add_config, src)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(src)
print('완료')
