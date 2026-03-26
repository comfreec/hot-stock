content = open('app.py', encoding='utf-8').read()
content = content.replace(
    'make_rsi_chart(rsi_s, cd), config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True',
    'make_rsi_chart(rsi_s, cd), config={"scrollZoom":False,"displayModeBar":False}, use_container_width=False'
).replace(
    'make_rsi_chart(rsi_s, data), config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True',
    'make_rsi_chart(rsi_s, data), config={"scrollZoom":False,"displayModeBar":False}, use_container_width=False'
)
open('app.py', 'w', encoding='utf-8').write(content)
print('done')
