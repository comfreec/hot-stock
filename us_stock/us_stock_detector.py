"""
미국 주식 급등 예고 탐지기
- 국내 stock_surge_detector와 동일한 R-사이클 + 장기선 전략
- yfinance 기반 (달러 단위)
"""
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date, timedelta


def _rsi(close: pd.Series, period: int = 20) -> pd.Series:
    d = close.diff()
    gain = d.where(d > 0, 0.0).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    loss = (-d.where(d < 0, 0.0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, float('nan'))
    return (100 - 100 / (1 + rs)).fillna(50)


class USStockDetector:
    def __init__(self, max_gap_pct: float = 7.0, ob_days: int = 180,
                 min_below_days: int = 0, min_score: int = 15):
        self.max_gap_pct = max_gap_pct
        self.ob_days = ob_days
        self.min_below_days = min_below_days
        self.min_score = min_score

    def analyze_stock(self, symbol: str, name: str = None) -> dict | None:
        """단일 종목 분석 - 국내와 동일한 R-사이클 전략"""
        try:
            df = yf.Ticker(symbol).history(period="5y", auto_adjust=False)
            df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
            if len(df) < 60:
                return None

            close  = df["Close"]
            high   = df["High"]
            low    = df["Low"]
            volume = df["Volume"]
            current = float(close.iloc[-1])

            # 240일선
            ma240 = close.rolling(240).mean()
            ma240_v = float(ma240.iloc[-1]) if not pd.isna(ma240.iloc[-1]) else None
            if not ma240_v:
                return None

            ma240_gap = (current / ma240_v - 1) * 100

            # 장기선 위 7% 이내인지 확인
            if not (0 <= ma240_gap <= self.max_gap_pct):
                return None

            # R-사이클(RSI 20) 계산
            rsi_s = _rsi(close, 20)
            cur_rsi = float(rsi_s.iloc[-1])

            # 장기선 아래 충분히 눌렸는지 확인 (ob_days 내 장기선 아래 기간)
            below_mask = close < ma240
            below_days = int(below_mask.tail(self.ob_days).sum())
            if below_days < self.min_below_days:
                return None

            # RSI 30 이하 → 30 돌파 시점 찾기 (R-사이클 패턴)
            rsi_vals = rsi_s.values
            oversold_exit = None
            for i in range(1, len(rsi_vals)):
                if rsi_vals[i-1] <= 30 and rsi_vals[i] > 30:
                    oversold_exit = i
            if oversold_exit is None:
                return None

            days_since = len(rsi_vals) - 1 - oversold_exit
            if days_since > self.ob_days:
                return None

            # 점수 계산
            score = 0
            signals = {}

            # 기본 조건 충족 (장기선 근처 + RSI 사이클)
            score += 10
            signals["rsi_cycle"] = True
            signals["rsi"] = round(cur_rsi, 1)
            signals["rsi_cycle_days_since"] = days_since

            # 거래량 분석
            vol_ma20 = volume.rolling(20).mean()
            recent_vol_ratio = float(volume.tail(5).mean() / vol_ma20.iloc[-1]) if vol_ma20.iloc[-1] > 0 else 1.0
            signals["recent_vol_ratio"] = round(recent_vol_ratio, 2)
            if recent_vol_ratio >= 1.5:
                score += 2
                signals["recent_vol"] = True

            # 이평선 정배열
            ma5  = close.rolling(5).mean()
            ma20 = close.rolling(20).mean()
            ma60 = close.rolling(60).mean()
            if float(ma5.iloc[-1]) > float(ma20.iloc[-1]) > float(ma60.iloc[-1]):
                score += 3
                signals["ma_align"] = True

            # RSI 건강 구간 (40~65)
            if 40 <= cur_rsi <= 65:
                score += 2
                signals["rsi_healthy"] = True

            # 볼린저밴드 수축→확장
            std20 = close.rolling(20).std()
            bb_width = (std20 / ma20).fillna(0)
            if len(bb_width) >= 10:
                if float(bb_width.iloc[-1]) > float(bb_width.tail(10).mean()) * 1.2:
                    score += 3
                    signals["bb_squeeze_expand"] = True

            # MACD 골든크로스
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            signal_line = macd.ewm(span=9, adjust=False).mean()
            if float(macd.iloc[-1]) > float(signal_line.iloc[-1]) and float(macd.iloc[-2]) <= float(signal_line.iloc[-2]):
                score += 2
                signals["macd_cross"] = True

            # 240일선 상승 전환
            if len(ma240) >= 20:
                ma240_slope = float(ma240.iloc[-1]) - float(ma240.iloc[-20])
                if ma240_slope > 0:
                    score += 3
                    signals["ma240_turning_up"] = True

            # 눌림목 반등
            recent_high = float(high.tail(20).max())
            pullback_depth = (recent_high - current) / recent_high * 100
            signals["pullback_depth"] = round(pullback_depth, 1)
            if 3 <= pullback_depth <= 15:
                score += 3
                signals["pullback_bounce"] = True

            # 52주 신고가 근처
            high_52w = float(high.tail(252).max())
            high_ratio = (current / high_52w - 1) * 100
            signals["high_ratio"] = round(high_ratio, 1)
            if high_ratio >= -10:
                score += 2
                signals["near_52w_high"] = True

            # 손절가: RSI 저점 기준
            try:
                _lb = max(0, oversold_exit - 5)
                stop_price = float(low.iloc[_lb:oversold_exit].min())
                signals["stop_price"] = round(stop_price, 2)
            except Exception:
                signals["stop_price"] = round(ma240_v * 0.95, 2)

            if score < self.min_score:
                return None

            return {
                "symbol":      symbol,
                "name":        name or symbol,
                "current_price": round(current, 2),
                "ma240":       round(ma240_v, 2),
                "ma240_gap":   round(ma240_gap, 2),
                "rsi":         round(cur_rsi, 1),
                "below_days":  below_days,
                "total_score": score,
                "signals":     signals,
                "close_series":  close,
                "high_series":   high,
                "low_series":    low,
                "volume_series": volume,
                "open_series":   df["Open"],
            }
        except Exception as e:
            print(f"[US스캔] {symbol} 오류: {e}")
            return None

    def analyze_all(self, symbols: dict, max_workers: int = 8) -> list:
        """전체 종목 스캔"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []

        def _scan(sym, nm):
            r = self.analyze_stock(sym, nm)
            return r

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(_scan, sym, nm): sym for sym, nm in symbols.items()}
            for fut in as_completed(futures):
                r = fut.result()
                if r:
                    results.append(r)

        return sorted(results, key=lambda x: x["total_score"], reverse=True)
