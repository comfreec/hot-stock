import re
with open('app.py', encoding='utf-8') as f:
    content = f.read()

new = content.replace('use_container_width=True', "width='stretch'")
new = new.replace('use_container_width=False', "width='content'")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(new)

count = content.count('use_container_width=True') + content.count('use_container_width=False')
print(f'변경: {count}개')
