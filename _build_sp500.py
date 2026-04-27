"""S&P500 목록을 하드코딩으로 symbols.py에 저장"""
import sys
sys.path.insert(0, 'us_stock')
import symbols as m

sp500 = m._SP500_DYNAMIC
print(f"S&P500 {len(sp500)}개 가져옴")

# 파이썬 dict 형태로 출력
lines = ["SP500_LARGE = {\n"]
for sym, name in sorted(sp500.items()):
    # 특수문자 이스케이프
    name_clean = name.replace("'", "\\'").replace('"', '\\"')
    lines.append(f'    "{sym}": "{name_clean}",\n')
lines.append("}\n")

with open("_sp500_hardcoded.txt", "w", encoding="utf-8") as f:
    f.writelines(lines)
print("_sp500_hardcoded.txt 저장 완료")
