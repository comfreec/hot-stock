content = open('app.py', encoding='utf-8').read()
content = content.replace('with st.expander(f"🔍 {r[\'name\']} 상세 신호 + 주가 차트"):', 
                          'with st.expander(f"🔍 {r[\'name\']} 상세 신호 + 주가 차트", expanded=True):')
open('app.py', 'w', encoding='utf-8').write(content)
print('done')
