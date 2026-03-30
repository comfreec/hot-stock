with open('app.py', encoding='utf-8') as f:
    src = f.read()

# scrollZoom:False,"displayModeBar":False} -> staticPlot:True 추가
src = src.replace(
    'config={"scrollZoom":False,"displayModeBar":False},',
    'config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True},'
)
src = src.replace(
    'config={"scrollZoom":False,"displayModeBar":False})',
    'config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True})'
)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(src)

count = src.count('staticPlot')
print(f'staticPlot 적용: {count}개')
