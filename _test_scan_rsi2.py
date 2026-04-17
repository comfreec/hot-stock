import sys, time
sys.path.insert(0, '.')
time.sleep(3)
import yfinance as yf, pandas as pd, json

with open('combined_symbols.json', encoding='utf-8') as f:
    syms = list(json.load(f).keys())[:20]

def rsi(close, period=20):
    d = close.diff()
    gain = d.where(d > 0, 0.0)
    loss = -d.where(d < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    return 100 - (100 / (1 + rs))

for sym in syms[:5]:
    try:
        df = yf.Ticker(sym).history(period='2y', auto_adjust=False).dropna(subset=['Close'])
        close = df['Close']
        ma240 = close.rolling(240).mean()
        r = rsi(close, 20).fillna(50)
        n = len(close)
        cur = float(close.iloc[-1])
        m240 = float(ma240.iloc[-1])
        gap = (cur - m240) / m240 * 100
        cur_rsi = float(r.iloc[-1])

        print(sym, 'gap='+str(round(gap,1))+'%', 'rsi='+str(round(cur_rsi,1)))

        # step1: rsi 30 탈출
        oversold_exit = None
        for i in range(1, n-30):
            if r.values[i-1] <= 30 and r.values[i] > 30:
                oversold_exit = i
        print('  oversold_exit:', oversold_exit)
        if oversold_exit is None: continue

        # step2: 240선 돌파
        cross_idx = None
        for i in range(oversold_exit, n-10):
            if pd.isna(ma240.iloc[i]) or pd.isna(ma240.iloc[i-1]): continue
            if close.iloc[i] > ma240.iloc[i] and close.iloc[i-1] <= ma240.iloc[i-1]:
                cross_idx = i; break
        print('  cross_idx:', cross_idx)
        if cross_idx is None: continue

        # step3: rsi 70 도달
        ob_idx = None
        for i in range(cross_idx, n-5):
            if r.values[i] >= 70:
                ob_idx = i; break
        print('  overbought_idx:', ob_idx)
        if ob_idx is None: continue

        # step4: rsi 70 이탈
        ob_exit = None
        for i in range(ob_idx, n-1):
            if r.values[i-1] >= 70 and r.values[i] < 70:
                ob_exit = i; break
        print('  overbought_exit:', ob_exit)
        if ob_exit is None: continue

        print('  cur_rsi:', round(cur_rsi,1), '55이하:', cur_rsi <= 55)
        print('  gap:', round(gap,1), '0~10%:', 0 <= gap <= 10)
        print('  -> 통과!' if (cur_rsi <= 55 and 0 <= gap <= 10) else '  -> 탈락')
    except Exception as e:
        print(sym, '오류:', e)
