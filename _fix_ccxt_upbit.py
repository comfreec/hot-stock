with open('crypto_surge/telegram_alert.py', encoding='utf-8') as f:
    content = f.read()
content = content.replace('ccxt.binance({"enableRateLimit": True})', 'ccxt.upbit({"enableRateLimit": True})')
with open('crypto_surge/telegram_alert.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
