import re

with open('crypto_surge/telegram_alert.py', encoding='utf-8') as f:
    content = f.read()

# _get_usd_krw 함수 교체 (업비트 기준이므로 환율 불필요)
new_get_usd_krw = '''def _get_usd_krw() -> float:
    """업비트 기반이므로 환율 변환 불필요 - 1 반환"""
    return 1.0'''

content = re.sub(
    r'def _get_usd_krw\(\).*?return 1450\.0',
    new_get_usd_krw,
    content,
    flags=re.DOTALL
)

# _fmt_krw 함수 교체 (원화 직접 포맷)
new_fmt_krw = '''def _fmt_krw(krw_val, rate=None) -> str:
    """원화 포맷 (업비트 기준이므로 변환 없음)"""
    if krw_val is None:
        return "-"
    return f"₩{int(krw_val):,}"'''

content = re.sub(
    r'def _fmt_krw\(.*?\n\n',
    new_fmt_krw + '\n\n',
    content,
    flags=re.DOTALL,
    count=1
)

with open('crypto_surge/telegram_alert.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
