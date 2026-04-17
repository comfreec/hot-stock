import sys, time
sys.path.insert(0, '.')
time.sleep(3)
from stock_surge_detector import KoreanStockSurgeDetector
import json

with open('combined_symbols.json', encoding='utf-8') as f:
    syms = list(json.load(f).keys())[:40]

det = KoreanStockSurgeDetector(max_gap_pct=10, min_below_days=60, max_cross_days=90)
det._today_price_cache = {}
passed = []
for sym in syms:
    r = det.analyze_stock(sym)
    if r:
        passed.append(r['name'] + '(' + sym + ') score=' + str(r['total_score']))

print('통과:', len(passed), '/', len(syms))
for p in passed:
    print(' ', p)
