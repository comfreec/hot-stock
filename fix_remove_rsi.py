import re
content = open('app.py', encoding='utf-8').read()

# RSI 차트 plotly_chart 호출 라인들 제거
patterns = [
    r'\s*st\.plotly_chart\(make_rsi_chart\([^)]+\)[^)]*\)[^\n]*\n',
    r'\s*st\.plotly_chart\(make_rsi_chart\(rsi_s[^)]*\)[^)]*\)[^\n]*\n',
]
for p in patterns:
    content = re.sub(p, '\n', content)

# 주석도 제거
content = content.replace('                        # RSI 차트 (주가 차트와 x축 동일)\n', '')
content = content.replace('                # RSI 차트 (주가 차트와 x축 동일하게)\n', '')
content = content.replace('                # 조건 미충족이어도 RSI 차트 표시\n', '')

open('app.py', 'w', encoding='utf-8').write(content)
print('done')
