import sys
sys.path.insert(0, 'us_stock')
# 캐시 제거
for k in list(sys.modules.keys()):
    if 'symbols' in k:
        del sys.modules[k]

import symbols as m
print(f'S&P500 동적: {len(m._SP500_DYNAMIC)}개')
print(f'SP500_LARGE: {len(m.SP500_LARGE)}개')
print(f'ALL_SYMBOLS: {len(m.ALL_SYMBOLS)}개')
