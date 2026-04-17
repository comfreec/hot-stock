with open('crypto_surge/app.py', encoding='utf-8') as f:
    content = f.read()

# show_price_levels 달러 → 원화
content = content.replace(
    "${lv[\"target\"]:,.4f}",
    "{int(lv[\"target\"] * _get_usd_krw()):,}원"
)
content = content.replace(
    "${lv[\"entry\"]:,.4f}",
    "{int(lv[\"entry\"] * _get_usd_krw()):,}원"
)
content = content.replace(
    "${lv[\"stop\"]:,.4f}",
    "{int(lv[\"stop\"] * _get_usd_krw()):,}원"
)

with open('crypto_surge/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
