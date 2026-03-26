content = open('app.py', encoding='utf-8').read()

# RSI 차트 전체 너비로
content = content.replace(
    'use_container_width=False, key=f"rsi_main_{r[\'symbol\']}")',
    'use_container_width=True, key=f"rsi_main_{r[\'symbol\']}")'
)
content = content.replace(
    'use_container_width=False, key=f"rsi_detail_{r[\'symbol\']}")',
    'use_container_width=True, key=f"rsi_detail_{r[\'symbol\']}")'
)
content = content.replace(
    'use_container_width=False, key="chart_rsi_individual")',
    'use_container_width=True, key="chart_rsi_individual")'
)
content = content.replace(
    'use_container_width=False, key="chart_rsi_no_cond")',
    'use_container_width=True, key="chart_rsi_no_cond")'
)
content = content.replace(
    'use_container_width=False, key=f"rsi_quality_{r[\'symbol\']}")',
    'use_container_width=True, key=f"rsi_quality_{r[\'symbol\']}")'
)
content = content.replace(
    'use_container_width=False, key=f"rsi_timing_{r[\'symbol\']}")',
    'use_container_width=True, key=f"rsi_timing_{r[\'symbol\']}")'
)

open('app.py', 'w', encoding='utf-8').write(content)
print('done')
