content = open('app.py', encoding='utf-8').read()

# [조건1] 반등 위치 - 타이트하게 (15~45% 구간만)
content = content.replace(
    "signals[\"recovery_zone\"] = recovery <= 0.75\n            signals[\"recovery_pct\"]  = round(recovery * 100, 1)\n            if recovery <= 0.35:   score += 4  # 초기 반등 (최적)\n            elif recovery <= 0.55: score += 3  # 중간 반등\n            elif recovery <= 0.75: score += 1  # 후반 반등",
    "signals[\"recovery_zone\"] = 0.10 <= recovery <= 0.50\n            signals[\"recovery_pct\"]  = round(recovery * 100, 1)\n            if 0.10 <= recovery <= 0.30: score += 4  # 초기 반등 (최적)\n            elif 0.30 < recovery <= 0.50: score += 2  # 중간 반등"
)

# [조건2] OBV 매집 - 타이트하게
content = content.replace(
    "signals[\"accumulation\"] = obv_20_chg > 0 and price_20_chg > -0.15\n            signals[\"obv_rising\"]   = obv_20_chg > -0.05",
    "signals[\"accumulation\"] = obv_20_chg > 0.03 and abs(price_20_chg) < 0.08\n            signals[\"obv_rising\"]   = obv_20_chg > 0"
)

# [조건3] BB 수축 - 타이트하게
content = content.replace(
    "signals[\"bb_squeeze\"]    = bb_w_now <= bb_w_min_60 * 2.0\n            # 수축 후 확장 시작\n            signals[\"bb_expanding\"]  = bb_w_now > bb_w_prev5 * 1.01",
    "signals[\"bb_squeeze\"]    = bb_w_now <= bb_w_min_60 * 1.2\n            # 수축 후 확장 시작\n            signals[\"bb_expanding\"]  = bb_w_now > bb_w_prev5 * 1.03"
)

# [조건4] RSI 사이클 - 타이트하게 (30 이하 필수)
content = content.replace(
    "rsi_120 = rsi.tail(120).dropna()\n            had_below40  = (rsi_120 < 40).any()\n            rsi_healthy  = 40 <= cur_rsi <= 70\n            signals[\"rsi_cycle\"]   = had_below40 and rsi_healthy",
    "rsi_90 = rsi.tail(90).dropna()\n            had_below30  = (rsi_90 < 30).any()\n            crossed_30   = ((rsi_90.shift(1) <= 30) & (rsi_90 > 30)).any()\n            rsi_healthy  = 40 <= cur_rsi <= 65\n            signals[\"rsi_cycle\"]   = had_below30 and crossed_30 and rsi_healthy"
)

# [조건7] 거래량 - 타이트하게
content = content.replace(
    "big_bull   = vol_ratio >= 1.5 and body_ratio >= 0.5 and chg > 0\n            vol_surge  = vol_ratio >= 1.2",
    "big_bull   = vol_ratio >= 2.0 and body_ratio >= 0.6 and chg > 0\n            vol_surge  = vol_ratio >= 1.5"
)

# [조건8] 52주 고점 - 타이트하게
content = content.replace(
    "near_high  = high_ratio >= 0.85  # 52주 고점 15% 이내\n            at_high    = high_ratio >= 0.95  # 돌파 직전",
    "near_high  = high_ratio >= 0.92  # 52주 고점 8% 이내\n            at_high    = high_ratio >= 0.98  # 돌파 직전"
)

# 최소 점수 7점으로 올리기
content = content.replace(
    'if r and r["total_score"] >= 1:',
    'if r and r["total_score"] >= 7:'
)

open('app.py', 'w', encoding='utf-8').write(content)
print('done')
