"""
RSI(20) 전략: 과매도(30이하) → 30돌파 → 70도달 → 70이탈 사이클 탐지
"""
import yfinance as yf
import pandas as pd
import numpy as np
from stock_surge_detector import ALL_SYMBOLS, STOCK_NAMES


def calc_rsi(series, period=20):
    """Wilder's Smoothing RSI - 이베스트증권 표준 방식"""
    d = series.diff()
    gain = d.where(d > 0, 0.0)
    loss = -d.where(d < 0, 0.0)

    avg_gain = gain.copy() * 0.0
    avg_loss = loss.copy() * 0.0

    avg_gain.iloc[period] = gain.iloc[1:period+1].mean()
    avg_loss.iloc[period] = loss.iloc[1:period+1].mean()

    for i in range(period + 1, len(series)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period

    avg_gain.iloc[:period] = float('nan')
    avg_loss.iloc[:period] = float('nan')

    rs = avg_gain / avg_loss.replace(0, float('nan'))
    return 100 - (100 / (1 + rs))


def find_rsi_pattern(symbol, lookback_days=180):
    """
    RSI 사이클 완성 종목 탐지:
    1) RSI 30 이하 (과매도 바닥)
    2) RSI 30 돌파 (반등 시작)
    3) RSI 70 이상 도달 (과매수)
    4) RSI 70 이탈 (최근) → 다음 매수 준비
    """
    try:
        df = yf.Ticker(symbol).history(period="1y")
        if df is None or len(df) < 60:
            return None

        df["rsi"] = calc_rsi(df["Close"], 20)
        df = df.dropna(subset=["rsi"])

        # 최근 lookback_days 기준
        df = df.tail(lookback_days)
        if len(df) < 40:
            return None

        rsi = df["rsi"]
        dates = df.index

        # 단계별 탐지 (순서대로)
        # 1) 과매도 구간 (RSI <= 30)
        below30_idx = rsi[rsi <= 30].index
        if len(below30_idx) == 0:
            return None
        bottom_date = below30_idx[0]
        bottom_rsi = rsi[below30_idx].min()

        # 2) 30 돌파 (bottom_date 이후)
        after_bottom = rsi[rsi.index > bottom_date]
        cross30_idx = after_bottom[after_bottom > 30].index
        if len(cross30_idx) == 0:
            return None
        cross30_date = cross30_idx[0]

        # 3) 70 이상 도달 (30돌파 이후)
        after_cross30 = rsi[rsi.index > cross30_date]
        above70_idx = after_cross30[after_cross30 >= 70].index
        if len(above70_idx) == 0:
            return None
        peak_date = above70_idx[0]
        peak_rsi = rsi[above70_idx].max()

        # 4) 70 이탈 (peak 이후)
        after_peak = rsi[rsi.index > peak_date]
        cross70_idx = after_peak[after_peak < 70].index
        if len(cross70_idx) == 0:
            return None
        cross70_date = cross70_idx[0]

        # 70 이탈 후 경과일
        last_date = dates[-1]
        days_since = (last_date - cross70_date).days
        if days_since < 0:
            return None

        current_price = df["Close"].iloc[-1]
        prev_price = df["Close"].iloc[-2] if len(df) > 1 else current_price
        price_change_1d = (current_price - prev_price) / prev_price * 100

        return {
            "symbol": symbol,
            "name": STOCK_NAMES.get(symbol, symbol),
            "current_price": current_price,
            "price_change_1d": price_change_1d,
            "current_rsi": round(rsi.iloc[-1], 2),
            "bottom_rsi": round(bottom_rsi, 2),
            "peak_rsi": round(peak_rsi, 2),
            "cross_above_30_date": str(cross30_date.date()),
            "cross_below_70_date": str(cross70_date.date()),
            "days_since_70_cross": days_since,
            "rsi_series": rsi,
            "price_series": df["Close"],
        }
    except Exception:
        return None
