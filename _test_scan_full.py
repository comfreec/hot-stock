import sys, time
sys.path.insert(0, '.')
time.sleep(3)
import yfinance as yf, pandas as pd, json
from concurrent.futures import ThreadPoolExecutor, as_completed

with open('combined_symbols.json', encoding='utf-8') as f:
    syms_dict = json.load(f)
syms = list(syms_dict.keys())

def rsi_calc(close, period=20):
    d = close.diff()
    gain = d.where(d > 0, 0.0)
    loss = -d.where(d < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    return 100 - (100 / (1 + rs))

fail = {"데이터부족":0,"거래대금":0,"gap":0,"oversold_exit없음":0,"cross없음":0,"overbought없음":0,"ob_exit없음":0,"rsi>55":0,"경과일>90":0}
passed = []

def check(sym):
    try:
        df = yf.Ticker(sym).history(period='2y', auto_adjust=False).dropna(subset=['Close'])
        if len(df) < 260: return 'data'
        close = df['Close']
        ma240 = close.rolling(240).mean()
        r = rsi_calc(close, 20).fillna(50)
        n = len(close)
        cur = float(close.iloc[-1])
        m240 = float(ma240.iloc[-1])
        gap = (cur - m240) / m240 * 100
        amt = float(close.tail(20).mean()) * float(df['Volume'].tail(20).mean())
        if amt < 2e9: return 'amt'
        if not (-5 <= gap <= 10): return 'gap'
        oversold_exit = None
        for i in range(1, n-30):
            if r.values[i-1] <= 30 and r.values[i] > 30:
                oversold_exit = i
        if oversold_exit is None: return 'no_oversold'
        cross_idx = None
        for i in range(oversold_exit, n-10):
            if pd.isna(ma240.iloc[i]) or pd.isna(ma240.iloc[i-1]): continue
            if close.iloc[i] > ma240.iloc[i] and close.iloc[i-1] <= ma240.iloc[i-1]:
                cross_idx = i; break
        if cross_idx is None: return 'no_cross'
        ob_idx = None
        for i in range(cross_idx, n-5):
            if r.values[i] >= 70: ob_idx = i; break
        if ob_idx is None: return 'no_ob'
        ob_exit = None
        for i in range(ob_idx, n-1):
            if r.values[i-1] >= 70 and r.values[i] < 70: ob_exit = i; break
        if ob_exit is None: return 'no_ob_exit'
        cur_rsi = float(r.values[-1])
        days_since = n - 1 - ob_exit
        if cur_rsi > 55: return 'rsi_high'
        if days_since > 90: return 'too_old'
        return ('pass', sym, syms_dict[sym], round(gap,1), round(cur_rsi,1), days_since)
    except: return 'error'

with ThreadPoolExecutor(max_workers=8) as ex:
    futures = {ex.submit(check, s): s for s in syms}
    for f in as_completed(futures):
        r = f.result()
        if isinstance(r, tuple) and r[0] == 'pass':
            passed.append(r)
        elif r == 'data': fail['데이터부족'] += 1
        elif r == 'amt': fail['거래대금'] += 1
        elif r == 'gap': fail['gap'] += 1
        elif r == 'no_oversold': fail['oversold_exit없음'] += 1
        elif r == 'no_cross': fail['cross없음'] += 1
        elif r == 'no_ob': fail['overbought없음'] += 1
        elif r == 'no_ob_exit': fail['ob_exit없음'] += 1
        elif r == 'rsi_high': fail['rsi>55'] += 1
        elif r == 'too_old': fail['경과일>90'] += 1

print(f'통과: {len(passed)} / {len(syms)}')
for p in passed:
    print(f'  {p[2]}({p[1]}) gap={p[3]}% rsi={p[4]} {p[5]}일전')
print()
print('탈락 이유:')
for k,v in sorted(fail.items(), key=lambda x:-x[1]):
    print(f'  {k}: {v}개')
