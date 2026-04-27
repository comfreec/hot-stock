"""
alert_history의 active/pending 종목 중 손절가가 구 방식(240선 -5%)으로
저장된 것들을 RSI 저점 기준으로 재계산해서 업데이트
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import yfinance as yf
from cache_db import _get_conn

def round_to_tick(price):
    if price < 1000:      tick = 1
    elif price < 5000:    tick = 5
    elif price < 10000:   tick = 10
    elif price < 50000:   tick = 50
    elif price < 100000:  tick = 100
    elif price < 500000:  tick = 500
    else:                 tick = 1000
    return int(round(price / tick) * tick)

def calc_rsi_stop(symbol):
    """RSI(20) 30 돌파 직전 5일 저가 기준 손절가 계산"""
    try:
        df = yf.Ticker(symbol).history(period="5y", auto_adjust=False)
        df = df.dropna(subset=["Close","High","Low"])
        if len(df) < 30:
            return None
        close = df["Close"]
        low   = df["Low"]
        ma240_v = float(close.rolling(240).mean().iloc[-1])
        current = float(close.iloc[-1])
        entry = ma240_v if (ma240_v and ma240_v < current) else current

        _d = close.diff()
        _gain = _d.where(_d > 0, 0.0).ewm(alpha=1/20, min_periods=20, adjust=False).mean()
        _loss = (-_d.where(_d < 0, 0.0)).ewm(alpha=1/20, min_periods=20, adjust=False).mean()
        _rsi = (100 - 100 / (1 + _gain / _loss.replace(0, float('nan')))).fillna(50)
        _rsi_vals = _rsi.values
        _oversold_exit = None
        for _i in range(1, len(_rsi_vals)):
            if _rsi_vals[_i-1] <= 30 and _rsi_vals[_i] > 30:
                _oversold_exit = _i
        if _oversold_exit is not None:
            _lb = max(0, _oversold_exit - 5)
            stop = float(low.iloc[_lb:_oversold_exit].min())
        else:
            stop = ma240_v * 0.95 if (ma240_v and ma240_v < entry) else entry * 0.95

        return round_to_tick(stop)
    except Exception as e:
        print(f"  [{symbol}] 계산 오류: {e}")
        return None

conn = _get_conn()
rows = conn.execute("""
    SELECT id, symbol, name, entry_price, stop_price
    FROM alert_history
    WHERE status IN ('pending','active')
    ORDER BY id
""").fetchall()

print(f"활성 종목 {len(rows)}개 확인 중...")
updated = 0
for rid, sym, name, entry, old_stop in rows:
    if not entry or not old_stop:
        continue
    # 구 손절가 패턴 감지: entry * 0.94 ~ entry * 0.96 범위 (240선 -5% 근사)
    expected_old = entry * 0.95
    is_old_style = abs(old_stop - expected_old) / entry < 0.02  # ±2% 이내면 구 방식으로 판단

    new_stop = calc_rsi_stop(sym)
    if new_stop is None:
        print(f"  [{sym}] {name}: 계산 실패, 스킵")
        continue

    if is_old_style:
        print(f"  [{sym}] {name}: 구 손절가 {old_stop:,.0f} → RSI저점 {new_stop:,.0f} (업데이트)")
        conn.execute("UPDATE alert_history SET stop_price=? WHERE id=?", (new_stop, rid))
        updated += 1
    else:
        print(f"  [{sym}] {name}: 손절가 {old_stop:,.0f} (RSI저점 {new_stop:,.0f}) - 이미 정상")

conn.commit()
conn.close()
print(f"\n완료: {updated}개 업데이트됨")
