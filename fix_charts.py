import re

with open('app.py', encoding='utf-8') as f:
    content = f.read()

cfg = 'config={"scrollZoom":False,"displayModeBar":False}, '

# already has config - skip; add config to those without
def add_config(m):
    inner = m.group(1)
    if 'config=' in inner:
        return m.group(0)
    return f'st.plotly_chart({inner}, {cfg}use_container_width=True'

content = re.sub(r'st\.plotly_chart\((.+?),\s*use_container_width=True', add_config, content)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('done')
