import pandas as pd
import yfinance as yf
from datetime import date

df = yf.Ticker('005930.KS').history(period='5d')
df = df.dropna(subset=['Open','High','Low','Close'])

print(f'dropna 후 마지막: {df.index[-1]}')
print(f'tz: {df.index.tz}')

today_str = date.today().isoformat()
last_date = str(df.index[-1])[:10]
print(f'today_str: {today_str}, last_date: {last_date}')
print(f'조건 last_date < today_str: {last_date < today_str}')

if last_date < today_str:
    cur_p = 176300.0
    new_idx = pd.Timestamp(today_str, tz=df.index.tz)
    print(f'new_idx: {new_idx}')
    df.loc[new_idx] = [cur_p, cur_p, cur_p, cur_p, 0]
    print(f'추가 후 마지막: {df.index[-1]}, Close: {df["Close"].iloc[-1]}')
