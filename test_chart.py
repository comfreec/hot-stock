import requests
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf

code = '005930'
res = requests.get(f'https://finance.naver.com/item/main.naver?code={code}',
                   headers={'User-Agent':'Mozilla/5.0'}, timeout=5)
soup = BeautifulSoup(res.text, 'html.parser')
tag = soup.select_one('.no_today .blind')
price = float(tag.get_text().replace(',','')) if tag else None
print(f'네이버 종가: {price}')

df = yf.Ticker('005930.KS').history(period='2y')
last_close = df['Close'].iloc[-1]
last_date = df.index[-1]
print(f'마지막 날짜: {last_date}, Close: {last_close}')

if pd.isna(last_close) and price:
    df.loc[df.index[-1], ['Open','High','Low','Close']] = price
    df2 = df.dropna(subset=['Open','High','Low','Close'])
    print(f'보완 후 마지막: {df2.index[-1]}, Close: {df2["Close"].iloc[-1]}')
    print(f'총 행수: {len(df2)}')
