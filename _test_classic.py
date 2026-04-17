import sys, time
sys.path.insert(0, '.')
time.sleep(3)
from stock_surge_detector import KoreanStockSurgeDetector

det = KoreanStockSurgeDetector(max_gap_pct=7, min_below_days=60, max_cross_days=90)
det._today_price_cache = {}

for sym, name in [('185750.KS','종근당'), ('161000.KS','애경케미칼')]:
    r = det.analyze_stock_classic(sym)
    if r:
        print(f'통과: {name} score={r["total_score"]} gap={r["ma240_gap"]:.1f}% cross={r["days_since_cross"]}일전 below={r["below_days"]}일')
    else:
        # 단계별 디버깅
        import yfinance as yf, pandas as pd
        df = yf.Ticker(sym).history(period='2y', auto_adjust=False).dropna(subset=['Close'])
        close = df['Close']
        ma240 = close.rolling(240).mean()
        n = len(close)
        cur = float(close.iloc[-1])
        m240 = float(ma240.iloc[-1])
        gap = (cur - m240) / m240 * 100
        print(f'탈락: {name} gap={gap:.1f}% (0~7% 조건: {0 <= gap <= 7})')
        if 0 <= gap <= 7:
            # 돌파 찾기
            cross_idx = None
            for i in range(n-1, max(n-91, 240), -1):
                if close.iloc[i] > ma240.iloc[i] and close.iloc[i-1] <= ma240.iloc[i-1]:
                    cross_idx = i; break
            print(f'  cross_idx: {cross_idx}, days_since: {n-1-cross_idx if cross_idx else None}')
            if cross_idx:
                # 조정기간
                below = 0
                for i in range(cross_idx-1, -1, -1):
                    if not pd.isna(ma240.iloc[i]) and close.iloc[i] < ma240.iloc[i]: below += 1
                    else: break
                print(f'  below_days(연속): {below}, 조건(>=60): {below >= 60}')
