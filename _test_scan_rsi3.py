import sys, time
sys.path.insert(0, '.')
time.sleep(3)
import yfinance as yf, pandas as pd, json

with open('combined_symbols.json', encoding='utf-8') as f:
    syms = list(json.load(f).keys())[:10]

def rsi_calc(close, period=20):
    d = close.diff()
    gain = d.where(d > 0, 0.0)
    loss = -d.where(d < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    return 100 - (100 / (1 + rs))

for sym in syms:
    try:
        df = yf.Ticker(sym).history(period='2y', auto_adjust=False).dropna(subset=['Close'])
        if len(df) < 260:
            print(sym, '데이터부족', len(df)); continue
        close = df['Close']
        ma240 = close.rolling(240).mean()
        r = rsi_calc(close, 20).fillna(50)
        n = len(close)
        cur = float(close.iloc[-1])
        m240 = float(ma240.iloc[-1])
        gap = (cur - m240) / m240 * 100
        cur_rsi = float(r.iloc[-1])

        # 거래대금
        amt = float(close.tail(20).mean()) * float(df['Volume'].tail(20).mean())

        print(sym, f'gap={gap:.1f}% rsi={cur_rsi:.1f} amt={amt/1e8:.0f}억')

        if amt < 2e9:
            print('  -> 거래대금 탈락'); continue
        if not (-5 <= gap <= 10):
            print('  -> gap 탈락'); continue

        # rsi 30 탈출
        oversold_exit = None
        for i in range(1, n-30):
            if r.values[i-1] <= 30 and r.values[i] > 30:
                oversold_exit = i
        if oversold_exit is None:
            print('  -> oversold_exit 없음'); continue

        # 240선 돌파
        cross_idx = None
        for i in range(oversold_exit, n-10):
            if pd.isna(ma240.iloc[i]) or pd.isna(ma240.iloc[i-1]): continue
            if close.iloc[i] > ma240.iloc[i] and close.iloc[i-1] <= ma240.iloc[i-1]:
                cross_idx = i; break
        if cross_idx is None:
            print('  -> cross_idx 없음'); continue

        # rsi 70 도달
        ob_idx = None
        for i in range(cross_idx, n-5):
            if r.values[i] >= 70:
                ob_idx = i; break
        if ob_idx is None:
            print('  -> overbought 없음'); continue

        # rsi 70 이탈
        ob_exit = None
        for i in range(ob_idx, n-1):
            if r.values[i-1] >= 70 and r.values[i] < 70:
                ob_exit = i; break
        if ob_exit is None:
            print('  -> overbought_exit 없음'); continue

        days_since = n - 1 - ob_exit
        if cur_rsi > 55:
            print(f'  -> rsi {cur_rsi:.1f} > 55 탈락'); continue
        if days_since > 90:
            print(f'  -> {days_since}일 경과 > 90 탈락'); continue

        print(f'  -> 통과! ob_exit={days_since}일전 rsi={cur_rsi:.1f}')
    except Exception as e:
        print(sym, '오류:', e)
