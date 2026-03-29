content = open('app.py', encoding='utf-8').read()
# 등락률 이모지 변경: 상승=빨간 삼각형, 하락=파란 삼각형
content = content.replace(
    "f\"{'🔺' if r['price_change_1d']>0 else '🔻'}{r['price_change_1d']:.2f}%\"",
    "f\"{'🔺' if r['price_change_1d']>0 else '🔽'}{r['price_change_1d']:.2f}%\""
)
open('app.py', 'w', encoding='utf-8').write(content)
print('done', content.count('🔽'))
