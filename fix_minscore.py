content = open('app.py', encoding='utf-8').read()
content = content.replace(
    'if "min_score" not in st.session_state: st.session_state["min_score"] = 8',
    'if "min_score" not in st.session_state: st.session_state["min_score"] = 12'
)
content = content.replace(
    'st.session_state["min_score"] = 8',
    'st.session_state["min_score"] = 12'
)
open('app.py', 'w', encoding='utf-8').write(content)
print('done')
