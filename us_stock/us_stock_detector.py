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
        """단일 종목 분석 - 국내와 동일한 R-사이클 전략 (강화 점수 체계)"""
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

            # 장기선 아래 충분히 눌렸는지 확인
            below_mask = close < ma240
            below_days = int(below_mask.tail(self.ob_days).sum())
            if below_days < self.min_below_days:
                return None

            # RSI 30 이하 → 30 돌파 시점 찾기 (R-사이클 패턴)
            rsi_vals = rsi_s.values
            oversold_exit = None
            rsi_bottom_val = 50.0
            for i in range(1, len(rsi_vals)):
                if rsi_vals[i-1] <= 30 and rsi_vals[i] > 30:
                    oversold_exit = i
                    # 해당 구간 RSI 최저값
                    lb = max(0, i - 20)
                    rsi_bottom_val = float(rsi_s.iloc[lb:i].min())
            if oversold_exit is None:
                return None

            days_since = len(rsi_vals) - 1 - oversold_exit
            if days_since > self.ob_days:
                return None

            # ── 점수 계산 ─────────────────────────────────────────
            score = 0
            signals = {}

            # 기본 조건 충족 (장기선 근처 + RSI 사이클)
            score += 10
            signals["rsi_cycle"] = True
            signals["rsi"] = round(cur_rsi, 1)
            signals["rsi_cycle_days_since"] = days_since

            # RSI 바닥 깊이 가산점
            if rsi_bottom_val <= 20:   score += 3
            elif rsi_bottom_val <= 25: score += 2
            elif rsi_bottom_val <= 28: score += 1

            # 거래량 분석
            vol_ma20 = volume.rolling(20).mean()
            recent_vol_ratio = float(volume.tail(5).mean() / vol_ma20.iloc[-1]) if vol_ma20.iloc[-1] > 0 else 1.0
            signals["recent_vol_ratio"] = round(recent_vol_ratio, 2)
            if recent_vol_ratio >= 2.0:
                score += 4; signals["vol_strong"] = True
            elif recent_vol_ratio >= 1.5:
                score += 2; signals["recent_vol"] = True

            # OBV 상승
            obv = (volume * np.sign(close.diff().fillna(0))).cumsum()
            obv_after = obv.iloc[oversold_exit:]
            signals["obv_rising"] = len(obv_after) > 1 and float(obv_after.iloc[-1]) > float(obv_after.iloc[0])
            if signals["obv_rising"]: score += 2

            # 이평선 정배열
            ma5  = close.rolling(5).mean()
            ma20 = close.rolling(20).mean()
            ma60 = close.rolling(60).mean()
            signals["ma_align"] = bool(float(ma5.iloc[-1]) > float(ma20.iloc[-1]) > float(ma60.iloc[-1]))
            if signals["ma_align"]: score += 3

            # RSI 건강 구간 (40~65)
            signals["rsi_healthy"] = 40 <= cur_rsi <= 65
            if signals["rsi_healthy"]: score += 2

            # RSI 기울기 상승
            try:
                rsi_slope = float(rsi_s.iloc[-1]) - float(rsi_s.iloc[-5])
                signals["rsi_slope_up"] = rsi_slope > 0
                if signals["rsi_slope_up"]: score += 3
            except Exception:
                signals["rsi_slope_up"] = False

            # RSI 50 돌파
            try:
                rsi_cross50 = False
                for _i in range(max(1, len(rsi_vals)-10), len(rsi_vals)):
                    if rsi_vals[_i-1] < 50 and rsi_vals[_i] >= 50:
                        rsi_cross50 = True
                signals["rsi_cross50"] = rsi_cross50
                if rsi_cross50: score += 3
            except Exception:
                signals["rsi_cross50"] = False

            # 볼린저밴드 수축→확장
            std20 = close.rolling(20).std()
            bb_width = (std20 / ma20).fillna(0)
            if len(bb_width) >= 10:
                bb_sq = float(bb_width.iloc[-5]) < float(bb_width.tail(20).mean()) * 0.8
                bb_ex = float(bb_width.iloc[-1]) > float(bb_width.iloc[-5])
                signals["bb_squeeze_expand"] = bb_sq and bb_ex
                if signals["bb_squeeze_expand"]: score += 3

            # MACD 골든크로스
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            signal_line = macd.ewm(span=9, adjust=False).mean()
            signals["macd_cross"] = (float(macd.iloc[-1]) > float(signal_line.iloc[-1]) and
                                     float(macd.iloc[-2]) <= float(signal_line.iloc[-2]))
            if signals["macd_cross"]: score += 2

            # 240일선 상승 전환
            if len(ma240) >= 20:
                ma240_old_slope = float(ma240.iloc[-20]) - float(ma240.iloc[-40]) if len(ma240) >= 40 else 0
                ma240_new_slope = float(ma240.iloc[-1]) - float(ma240.iloc[-20])
                signals["ma240_turning_up"] = ma240_old_slope <= 0 and ma240_new_slope >= 0
                if signals["ma240_turning_up"]: score += 3

            # 눌림목 반등
            recent_high5 = float(high.tail(5).max())
            recent_low5  = float(low.tail(5).min())
            bounce_pct = (current - recent_low5) / recent_low5 * 100 if recent_low5 > 0 else 0
            recent_high20 = float(high.tail(20).max())
            pullback_depth = (recent_high20 - current) / recent_high20 * 100
            signals["pullback_depth"] = round(pullback_depth, 1)
            signals["pullback_bounce"] = bounce_pct >= 2.0 and current >= recent_high5 * 0.98
            if signals["pullback_bounce"]: score += 3
            if 3 <= pullback_depth <= 15: score += 2
            elif pullback_depth > 25: score = max(0, score - 2)

            # 52주 신고가 근처
            high_52w = float(high.tail(252).max())
            high_ratio = (current / high_52w - 1) * 100
            signals["high_ratio"] = round(high_ratio, 1)
            signals["near_52w_high"] = high_ratio >= -10
            if signals["near_52w_high"]: score += 2

            # 주봉 RSI (중기 추세 확인)
            try:
                weekly_close = close.resample("W").last().dropna()
                if len(weekly_close) >= 30:
                    w_rsi = _rsi(weekly_close, 14)
                    w_rsi_v = float(w_rsi.iloc[-1])
                    w_slope = float(w_rsi.iloc[-1]) - float(w_rsi.iloc[-4])
                    signals["weekly_rsi"] = round(w_rsi_v, 1)
                    signals["weekly_rsi_bull"] = w_rsi_v > 50
                    signals["weekly_rsi_rising"] = w_slope > 0
                    if signals["weekly_rsi_bull"]:   score += 3
                    if signals["weekly_rsi_rising"]: score += 2
            except Exception:
                signals["weekly_rsi"] = 50

            # S&P500 대비 상대강도 (RS)
            try:
                spy = yf.Ticker("SPY").history(period="3mo", auto_adjust=False)["Close"]
                if len(spy) >= 20 and len(close) >= 20:
                    rs_1m = (float(close.iloc[-1]) / float(close.iloc[-20]) - 1) - \
                            (float(spy.iloc[-1]) / float(spy.iloc[-20]) - 1)
                    signals["rs_vs_spy"] = round(rs_1m * 100, 1)
                    signals["rs_outperform"] = rs_1m > 0
                    signals["rs_strong"] = rs_1m > 0.05
                    if signals["rs_strong"]:     score += 3
                    elif signals["rs_outperform"]: score += 1
            except Exception:
                signals["rs_vs_spy"] = 0

            # 섹터 ETF 모멘텀 (종목이 속한 섹터 ETF 성과)
            try:
                sector_map = {
                    "AAPL|MSFT|NVDA|AMD|INTC|QCOM|AVGO|TXN|AMAT|MU|LRCX|KLAC|MRVL|ASML|MCHP|ON|NXPI|SNPS|CDNS": "XLK",
                    "JPM|BAC|WFC|GS|MS|BLK|V|MA|AXP": "XLF",
                    "XOM|CVX|COP": "XLE",
                    "JNJ|UNH|PFE|MRK|ABT|TMO|LLY|BMY|REGN|VRTX|GILD|AMGN|BIIB|IDXX|DXCM|ILMN": "XLV",
                    "WMT|HD|NKE|MCD|DIS|CMCSA|SBUX|MDLZ|PEP": "XLY",
                }
                sector_etf = None
                for syms, etf in sector_map.items():
                    if symbol in syms.split("|"):
                        sector_etf = etf
                        break
                if sector_etf:
                    etf_data = yf.Ticker(sector_etf).history(period="1mo", auto_adjust=False)["Close"]
                    if len(etf_data) >= 10:
                        etf_ret = (float(etf_data.iloc[-1]) / float(etf_data.iloc[0]) - 1) * 100
                        signals["sector_etf"] = sector_etf
                        signals["sector_momentum"] = round(etf_ret, 1)
                        if etf_ret > 3:   score += 3
                        elif etf_ret > 1: score += 1
                        elif etf_ret < -3: score = max(0, score - 2)
            except Exception:
                signals["sector_momentum"] = 0

            # 세력 매집 감지 (조용한 거래량 증가)
            try:
                price_std_20 = float(close.pct_change().tail(20).std())
                vol_trend_20 = float(volume.tail(10).mean() / volume.tail(20).mean()) if float(volume.tail(20).mean()) > 0 else 1.0
                signals["stealth_accumulation"] = price_std_20 < 0.03 and vol_trend_20 > 1.2
                if signals["stealth_accumulation"]: score += 3
            except Exception:
                signals["stealth_accumulation"] = False

            # 망치형/장악형 캔들
            try:
                o_s = df["Open"]
                body = abs(close - o_s)
                lower_wick = close.combine(o_s, min) - low
                upper_wick = high - close.combine(o_s, max)
                signals["hammer"] = bool((lower_wick.iloc[-1] > body.iloc[-1] * 2) and (upper_wick.iloc[-1] < body.iloc[-1]))
                signals["bullish_engulf"] = bool(((close > o_s) & (close.shift(1) < o_s.shift(1)) &
                                                   (close > o_s.shift(1)) & (o_s < close.shift(1))).iloc[-1])
                if signals["hammer"]:         score += 1
                if signals["bullish_engulf"]: score += 2
            except Exception:
                signals["hammer"] = False
                signals["bullish_engulf"] = False

            # 조정 기간 가산점
            if   below_days >= 240: score += 3
            elif below_days >= 180: score += 2
            elif below_days >= 120: score += 1

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
                "symbol":        symbol,
                "name":          name or symbol,
                "current_price": round(current, 2),
                "ma240":         round(ma240_v, 2),
                "ma240_gap":     round(ma240_gap, 2),
                "rsi":           round(cur_rsi, 1),
                "below_days":    below_days,
                "total_score":   score,
                "signals":       signals,
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
