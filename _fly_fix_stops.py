"""
Fly 서버에서 직접 실행: alert_history 활성 종목 손절가를 RSI 저점 기준으로 재계산
"""
import sqlite3, os
import pandas as pd
import yfinance as yf

DB_PATH = os.environ.get("DB_PATH", "/data/scan_cache.db")

def round_to_tick(price):
    if price < 2000:      tick = 1
    elif price < 5000:    tick = 5
    elif price < 20000:   tick = 10
    elif price < 50000:   tick = 50
    elif price < 200000:  tick = 100
    elif price < 500000:  tick = 500
    else:                 tick = 1000
    return int(round(price / tick) * tick)

def calc_rsi_stop(symbol):
    try:
        df = yf.Ticker(symbol).history(period="5y", auto_adjust=False)
        df = df.dropna(subset=["Close","Low"])
        if len(df) < 30:
            return None
        close, low = df["Close"], df["Low"]
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

conn = sqlite3.connect(DB_PATH)
rows = conn.execute("""
    SELECT id, symbol, name, entry_price, stop_price
    FROM alert_history WHERE status IN ('pending','active')
    ORDER BY id
""").fetchall()

print(f"활성 종목 {len(rows)}개 손절가 재계산 중...")
updated = 0
for rid, sym, name, entry, old_stop in rows:
    if not entry or not old_stop:
        continue
    new_stop = calc_rsi_stop(sym)
    if new_stop is None:
        print(f"  [{sym}] {name}: 계산 실패, 스킵")
        continue
    if new_stop != int(old_stop):
        print(f"  [{sym}] {name}: {old_stop:,.0f} → {new_stop:,.0f}")
        conn.execute("UPDATE alert_history SET stop_price=? WHERE id=?", (new_stop, rid))
        updated += 1
    else:
        print(f"  [{sym}] {name}: {old_stop:,.0f} (변경 없음)")

conn.commit()

# trade_orders도 동기화
try:
    to_rows = conn.execute("""
        SELECT symbol, stop_price FROM trade_orders
        WHERE status IN ('active','pending')
    """).fetchall()
    for sym, to_stop in to_rows:
        ah_row = conn.execute(
            "SELECT stop_price FROM alert_history WHERE symbol=? AND status IN ('pending','active') ORDER BY id DESC LIMIT 1",
            (sym,)
        ).fetchone()
        if ah_row and ah_row[0] and ah_row[0] != to_stop:
            conn.execute("UPDATE trade_orders SET stop_price=? WHERE symbol=? AND status IN ('active','pending')",
                        (ah_row[0], sym))
            print(f"  trade_orders [{sym}] stop: {to_stop} → {ah_row[0]}")
    conn.commit()
except Exception as e:
    print(f"trade_orders 동기화 오류: {e}")

conn.close()
print(f"\n완료: {updated}개 업데이트됨")
