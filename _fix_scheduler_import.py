content = open('app.py', encoding='utf-8').read()

# start_scheduler 호출 블록 제거
old = '    # 스케줄러 시작 (앱 최초 로드 시 1회)\n    if "scheduler_started" not in st.session_state:\n        start_scheduler()\n        st.session_state["scheduler_started"] = True\n'
content = content.replace(old, '')

# import에서 start_scheduler 제거
content = content.replace(', start_scheduler', '')

open('app.py', 'w', encoding='utf-8').write(content)
print('완료')
