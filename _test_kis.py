from auto_trader import KISClient
c = KISClient()
p = c.get_price("005930")
print("삼성전자:", p)
b = c.get_balance()
print("예수금:", b.get("cash"))
print("보유종목:", b.get("holdings"))
