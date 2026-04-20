"""
수동으로 스캔 결과 + alert_history에 종목 주입
코스모화학(003070.KS), 카카오페이(377300.KS) → 내일 09:05 자동매매 1차 매수
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
from datetime import date, datetime
from cache_db import save_scan, _get_conn

TODAY = date.today().isoformat()

TARGETS = [
    {"symbol": "003070.KS", "name": "코스모화학"},
    {"symbol": "377300.KS", "name": "카카오페이"},
]

def get_price_levels(symbol):
    """현재가 기준으로 entry/target/stop 계산"""
    try:
        df = yf.Ticker(symbol).history(period="3mo", auto_adjust=False).dropna(subset=["Close"])
        if len(df) < 20:
            return None
        close = df["Close"]
        high  = df["High"]
        low   = df["Low"]
        current = float(close.iloc[-1])

        # ATR 기반 손익비
        import pandas as pd, numpy as np
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().dropna().iloc[-1])

        ma240 = close.rolling(240).mean()
        ma240_v = float(ma240.iloc[-1]) if not pd.isna(ma240.iloc[-1]) else current * 0.95

        entry  = int(round(current / 10) * 10)  # 호가 단위 근사
        stop   = int(max(ma240_v * 0.995, entry * 0.93))
        risk   = entry - stop
        target = int(entry + risk * 3)  # 손익비 3:1

        return {
            "current": current,
            "entry":   entry,
            "target":  target,
            "stop":    stop,
            "ma240":   round(ma240_v, 0),
        }
    except Exception as e:
        print(f"[오류] {symbol}: {e}")
        return None

results = []
for t in TARGETS:
    sym  = t["symbol"]
    name = t["name"]
    lv   = get_price_levels(sym)
    if not lv:
        print(f"[스킵] {name} 가격 조회 실패")
        continue

    print(f"\n{name} ({sym})")
    print(f"  현재가: ₩{lv['current']:,.0f}")
    print(f"  매수가: ₩{lv['entry']:,}")
    print(f"  목표가: ₩{lv['target']:,}")
    print(f"  손절가: ₩{lv['stop']:,}")
    print(f"  240선:  ₩{lv['ma240']:,}")

    # scan_results용 최소 필드
    results.append({
        "symbol":        sym,
        "name":          name,
        "current_price": lv["current"],
        "total_score":   50,  # 수동 입력 표시
        "ma240":         lv["ma240"],
        "ma240_gap":     round((lv["current"] - lv["ma240"]) / lv["ma240"] * 100, 2),
    })

    # alert_history에 가격 레벨 저장
    conn = _get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO alert_history
        (alert_date, symbol, name, score, entry_price, target_price, stop_price,
         rr_ratio, status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        TODAY, sym, name, 50,
        lv["entry"], lv["target"], lv["stop"],
        round((lv["target"] - lv["entry"]) / max(lv["entry"] - lv["stop"], 1), 2),
        "active",
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()
    print(f"  → alert_history 저장 완료")

if results:
    save_scan(results, TODAY)
    print(f"\n✅ scan_results 저장 완료 ({TODAY}) - {len(results)}개 종목")
    print("내일 09:05 스케줄러가 자동매매 1차 매수 실행합니다.")
else:
    print("\n❌ 저장할 종목 없음")
