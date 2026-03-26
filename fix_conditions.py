content = open('app.py', encoding='utf-8').read()

# OBV 조건 완화
content = content.replace(
    'signals["accumulation"] = obv_20_chg > 0.05 and abs(price_20_chg) < 0.05\n            signals["obv_rising"]   = obv_20_chg > 0',
    'signals["accumulation"] = obv_20_chg > 0 and price_20_chg > -0.15\n            signals["obv_rising"]   = obv_20_chg > -0.05'
)

# BB 수축 조건 완화
content = content.replace(
    'signals["bb_squeeze"]    = bb_w_now <= bb_w_min_60 * 1.15\n            # 수축 후 확장 시작\n            signals["bb_expanding"]  = bb_w_now > bb_w_prev5 * 1.05',
    'signals["bb_squeeze"]    = bb_w_now <= bb_w_min_60 * 2.0\n            # 수축 후 확장 시작\n            signals["bb_expanding"]  = bb_w_now > bb_w_prev5 * 1.01'
)

# RSI 사이클 조건 완화 (60일 -> 120일, 30이하 없어도 40이하면 인정)
content = content.replace(
    'rsi_60 = rsi.tail(60).dropna()\n            had_below30  = (rsi_60 < 30).any()\n            crossed_30   = ((rsi_60.shift(1) <= 30) & (rsi_60 > 30)).any()\n            rsi_healthy  = 40 <= cur_rsi <= 65\n            signals["rsi_cycle"]   = had_below30 and crossed_30 and rsi_healthy',
    'rsi_120 = rsi.tail(120).dropna()\n            had_below40  = (rsi_120 < 40).any()\n            rsi_healthy  = 40 <= cur_rsi <= 70\n            signals["rsi_cycle"]   = had_below40 and rsi_healthy'
)

# 거래량 조건 완화
content = content.replace(
    'big_bull   = vol_ratio >= 2.0 and body_ratio >= 0.6 and chg > 0\n            vol_surge  = vol_ratio >= 1.5',
    'big_bull   = vol_ratio >= 1.5 and body_ratio >= 0.5 and chg > 0\n            vol_surge  = vol_ratio >= 1.2'
)

# 52주 고점 조건 완화
content = content.replace(
    'near_high  = high_ratio >= 0.95  # 52주 고점 5% 이내\n            at_high    = high_ratio >= 0.99  # 돌파 직전',
    'near_high  = high_ratio >= 0.85  # 52주 고점 15% 이내\n            at_high    = high_ratio >= 0.95  # 돌파 직전'
)

open('app.py', 'w', encoding='utf-8').write(content)
print('done')
