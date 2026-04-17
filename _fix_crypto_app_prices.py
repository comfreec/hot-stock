"""crypto_surge/app.py의 달러 가격 표시를 원화로 변환"""
with open('crypto_surge/app.py', encoding='utf-8') as f:
    content = f.read()

rate_func = "get_usd_krw()"

# 헬퍼 함수 - 원화 포맷
def_krw = """
def _krw(usd_val, rate=None):
    \"\"\"USD 값을 원화 문자열로 변환\"\"\"
    if rate is None:
        rate = get_usd_krw()
    krw = usd_val * rate
    return f"₩{int(krw):,}"
"""

replacements = [
    # 시장 현황 카드 (BTC/ETH 등 현재가 - 달러 유지, 변경 안 함)
    # 스캔 결과 테이블
    ('"현재가":    f"${r[\'current_price\']:,.4f}"',
     '"현재가":    _krw(r[\'current_price\'])'),
    ('"200일선":   f"${r[\'ma200\']:,.4f}"',
     '"200일선":   _krw(r[\'ma200\'])'),
    # 랭크 카드 현재가
    ('${r["current_price"]:,.4f}</span>\n                  <span style="color:#f7a44f',
     '{_krw(r["current_price"])}</span>\n                  <span style="color:#f7a44f'),
    # 랭크 카드 200일선
    ('200일선 ${r["ma200"]:,.4f}',
     '200일선 {_krw(r["ma200"])}'),
    # 최적 타이밍 탭 현재가
    ('${r["current_price"]:,.4f}</span>\n                  <span style="color:{color}',
     '{_krw(r["current_price"])}</span>\n                  <span style="color:{color}'),
    # 개별 분석 현재가 (두 곳)
    ('${current:,.4f}</span>\n                  <span style="color:{color};font-size:15px',
     '{_krw(current)}</span>\n                  <span style="color:{color};font-size:15px'),
    # 200일선 metric
    ('f"${ma200_now:,.4f}"',
     'f"{_krw(ma200_now)}"'),
    # 즐겨찾기 탭 현재가
    ('${cur_f:,.4f}</span>',
     '{_krw(cur_f)}</span>'),
    # 히스토리 탭 현재가
    ('"현재가":    f"${r.get(\'current_price\', 0):,.4f}"',
     '"현재가":    _krw(r.get(\'current_price\', 0))'),
    # 성과추적 테이블
    ('"매수가": f"${r[4]:,.4f}" if r[4] else "-"',
     '"매수가": _krw(r[4]) if r[4] else "-"'),
    ('"목표가": f"${r[5]:,.4f}" if r[5] else "-"',
     '"목표가": _krw(r[5]) if r[5] else "-"'),
    ('"손절가": f"${r[6]:,.4f}" if r[6] else "-"',
     '"손절가": _krw(r[6]) if r[6] else "-"'),
    ('"청산가": f"${r[9]:,.4f}" if r[9] else "-"',
     '"청산가": _krw(r[9]) if r[9] else "-"'),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f"✓ 교체: {old[:50]}...")
    else:
        print(f"✗ 못찾음: {old[:50]}...")

with open('crypto_surge/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("\nDone")
