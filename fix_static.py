content = open('app.py', encoding='utf-8').read()
content = content.replace(
    'config={"scrollZoom":False,"displayModeBar":False}',
    'config={"scrollZoom":False,"displayModeBar":False,"staticPlot":True}'
)
open('app.py', 'w', encoding='utf-8').write(content)
print('done', content.count('staticPlot'))
