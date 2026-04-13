"""
코인 급등 예측 프로그램 v1.0
핵심 전략: 200일선 아래 조정 → 최근 돌파 → 현재 근처 → 급등 신호 복합
주식 버전(240일선)과 동일한 로직, 코인 특성에 맞게 조정 (200일선 기준)
"""
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import warnings
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
warnings.filterwarnings("ignore")

try:
    import ta
    _TA_AVAILABLE = True
except ImportError:
    _TA_AVAILABLE = False

from symbols import CRYPTO_SYMBOLS, COIN_NAMES

# 업비트 거래소 (공개 API, 인증 불필요)
_exchange = ccxt.upbit({"enableRateLimit": True})


def fetch_ohlcv(symbol: str, timeframe: str = "1d", limit: int = 300) -> pd.DataFrame | None:
    """업비트에서 OHLCV 데이터 가져오기"""
    try:
        raw = _exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not raw or len(raw) < 60:
            return None
        df = pd.DataFrame(raw, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        return df
    except Exception as e:
        return None


class CryptoSurgeDetector:
    def __init__(self, max_gap_pct=15.0, min_below_days=60, max_cross_days=45):
        """
        max_gap_pct    : 200일선 위 최대 이격 (코인은 변동성 크므로 15%)
        min_below_days : 최소 조정 기간 (코인은 60일 = 2개월)
        max_cross_days : 돌파 후 최대 경과일 (45일)
        """
        self.symbols        = CRYPTO_SYMBOLS
        self.max_gap_pct    = max_gap_pct
        self.min_below_days = min_below_days
        self.max_cross_days = max_cross_days

    # ── 보조 지표 ────────────────────────────────────────────────

    def _rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        if _TA_AVAILABLE:
            try:
                return ta.momentum.RSIIndicator(close=close, window=period).rsi()
            except:
                pass
        d = close.diff()
        gain = d.where(d > 0, 0.0)
        loss = -d.where(d < 0, 0.0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, float("nan"))
        return 100 - (100 / (1 + rs))

    def _obv(self, data: pd.DataFrame) -> pd.Series:
        if _TA_AVAILABLE:
            try:
                return ta.volume.OnBalanceVolumeIndicator(
                    close=data["Close"], volume=data["Volume"]
                ).on_balance_volume()
            except:
                pass
        obv = [0]
        for i in range(1, len(data)):
            if data["Close"].iloc[i] > data["Close"].iloc[i-1]:
                obv.append(obv[-1] + data["Volume"].iloc[i])
            elif data["Close"].iloc[i] < data["Close"].iloc[i-1]:
                obv.append(obv[-1] - data["Volume"].iloc[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=data.index)

    def _funding_rate_signal(self, symbol: str) -> float:
        """펀딩비 조회 - 업비트는 현물만 지원하므로 0 반환"""
        return 0.0

    # ── 핵심 분석 ────────────────────────────────────────────────

    def analyze_coin(self, symbol: str) -> dict | None:
        """개별 코인 분석"""
        try:
            data = fetch_ohlcv(symbol, limit=300)
            if data is None or len(data) < 200:
                return None

            close = data["Close"]
            high  = data["High"]
            low   = data["Low"]
            vol   = data["Volume"]
            n     = len(close)

            # 이동평균
            ma200 = close.rolling(200).mean()
            ma50  = close.rolling(50).mean()
            ma20  = close.rolling(20).mean()
            ma5   = close.rolling(5).mean()

            current = float(close.iloc[-1])

            # ── 필수 조건 1: 현재가가 200일선 위 0~max_gap_pct% ──
            ma200_cur = float(ma200.iloc[-1])
            if pd.isna(ma200_cur):
                return None
            gap_pct = (current - ma200_cur) / ma200_cur * 100
            if not (0 <= gap_pct <= self.max_gap_pct):
                return None

            # ── 필수 조건 2: 최근 max_cross_days 이내 200일선 돌파 ──
            cross_idx = None
            search_start = max(0, n - self.max_cross_days - 1)
            for i in range(n - 1, search_start, -1):
                if pd.isna(ma200.iloc[i]) or pd.isna(ma200.iloc[i-1]):
                    continue
                prev_below = float(close.iloc[i-1]) < float(ma200.iloc[i-1])
                curr_above = float(close.iloc[i]) >= float(ma200.iloc[i]) * 1.005
                if prev_below and curr_above:
                    cross_idx = i
                    break
            if cross_idx is None:
                return None

            # ── 필수 조건 3: 돌파 전 min_below_days 이상 200일선 아래 ──
            below_days = sum(
                1 for i in range(cross_idx)
                if not pd.isna(ma200.iloc[i]) and float(close.iloc[i]) < float(ma200.iloc[i])
            )
            if below_days < self.min_below_days:
                return None

            # ── 필수 조건 4: 200일선 기울기 (급격한 하락 추세만 제외) ──
            ma200_at_cross   = float(ma200.iloc[cross_idx])
            ma200_20d_before = float(ma200.iloc[cross_idx - 20]) if cross_idx >= 20 else ma200_at_cross
            slope = (ma200_at_cross - ma200_20d_before) / ma200_20d_before * 100
            if slope < -5.0:  # 코인은 변동성 크므로 -5% 기준
                return None

            # ── 필수 조건 5: 돌파 후 3일 연속 이탈 없음 ──
            consecutive = 0
            for i in range(cross_idx + 1, n):
                if float(close.iloc[i]) < float(ma200.iloc[i]):
                    consecutive += 1
                    if consecutive >= 3:
                        return None
                else:
                    consecutive = 0

            # ── 점수 계산 ─────────────────────────────────────────
            score   = 0
            signals = {}

            # [+4/3] 돌파 시 거래량 급증
            vol_ma20 = vol.rolling(20).mean()
            cross_vr = float(vol.iloc[cross_idx] / vol_ma20.iloc[cross_idx]) if vol_ma20.iloc[cross_idx] > 0 else 0
            recent_vr = float(vol.iloc[-5:].mean() / vol_ma20.iloc[-1]) if vol_ma20.iloc[-1] > 0 else 0
            signals["vol_at_cross"]    = cross_vr >= 2.0
            signals["vol_strong_cross"] = cross_vr >= 3.0
            signals["recent_vol"]      = recent_vr >= 1.5
            signals["cross_vol_ratio"] = round(cross_vr, 2)
            signals["recent_vol_ratio"] = round(recent_vr, 2)
            if signals["vol_strong_cross"]: score += 4
            elif signals["vol_at_cross"]:   score += 3
            if signals["recent_vol"]:       score += 2

            # [+2] OBV 지속 상승
            obv = self._obv(data)
            obv_after = obv.iloc[cross_idx:]
            signals["obv_rising"] = len(obv_after) > 1 and float(obv_after.iloc[-1]) > float(obv_after.iloc[0])
            if signals["obv_rising"]: score += 2

            # [+3] 이평선 정배열 MA5 > MA20 > MA50
            signals["ma_align"] = bool(ma5.iloc[-1] > ma20.iloc[-1] > ma50.iloc[-1])
            if signals["ma_align"]: score += 3

            # [+2] 눌림목 후 재상승
            pa = close.iloc[cross_idx:]
            signals["pullback_recovery"] = (
                len(pa) >= 3 and
                float(pa.min()) < float(pa.iloc[0]) and
                current > float(close.iloc[cross_idx])
            )
            if signals["pullback_recovery"]: score += 2

            # [+2] RSI 건강 구간 40~65
            rsi = self._rsi(close, 14)
            cur_rsi = float(rsi.iloc[-1])
            signals["rsi"]         = round(cur_rsi, 1)
            signals["rsi_healthy"] = 40 <= cur_rsi <= 65
            if signals["rsi_healthy"]: score += 2

            # [+3] 볼린저밴드 수축 → 확장
            bb_std   = close.rolling(20).std()
            bb_mid   = close.rolling(20).mean()
            bb_w     = (4 * bb_std) / bb_mid.replace(0, np.nan)
            bb_w_avg = bb_w.rolling(40).mean()
            bb_sq = (not pd.isna(bb_w_avg.iloc[-5]) and
                     float(bb_w.iloc[-5]) < float(bb_w_avg.iloc[-5]) * 0.7)
            bb_ex = float(bb_w.iloc[-1]) > float(bb_w.iloc[-5])
            signals["bb_squeeze_expand"] = bb_sq and bb_ex
            if signals["bb_squeeze_expand"]: score += 3

            # [+2] MACD 골든크로스
            try:
                if _TA_AVAILABLE:
                    _macd_ind = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
                    macd   = _macd_ind.macd()
                    macd_s = _macd_ind.macd_signal()
                else:
                    macd   = close.ewm(span=12).mean() - close.ewm(span=26).mean()
                    macd_s = macd.ewm(span=9).mean()
                signals["macd_cross"] = bool(
                    macd.iloc[-1] > macd_s.iloc[-1] and
                    macd.iloc[-2] <= macd_s.iloc[-2]
                )
                if signals["macd_cross"]: score += 2
            except:
                signals["macd_cross"] = False

            # [+2] 펀딩비 음수 (숏 과열 → 반등 신호) - 코인 전용
            funding = self._funding_rate_signal(symbol)
            signals["funding_rate"]    = round(funding, 4)
            signals["funding_negative"] = funding < -0.01  # -0.01% 이하
            if signals["funding_negative"]: score += 2

            # [+2] 4시간봉 추세 확인 (단기 모멘텀)
            try:
                df4h = fetch_ohlcv(symbol, timeframe="4h", limit=50)
                if df4h is not None and len(df4h) >= 20:
                    ma20_4h = df4h["Close"].rolling(20).mean()
                    signals["4h_above_ma20"] = float(df4h["Close"].iloc[-1]) > float(ma20_4h.iloc[-1])
                    if signals["4h_above_ma20"]: score += 2
                else:
                    signals["4h_above_ma20"] = False
            except:
                signals["4h_above_ma20"] = False

            # ── 복합 신호 승수 ──────────────────────────────────────
            key_signals = sum([
                signals.get("vol_at_cross", False),
                signals.get("ma_align", False),
                signals.get("obv_rising", False),
                signals.get("rsi_healthy", False),
            ])
            if key_signals >= 3:
                score = int(score * 1.3)
            elif key_signals >= 2:
                score = int(score * 1.15)

            # ── 최소 점수 필터 ──────────────────────────────────────
            if score < 10:
                return None

            name = COIN_NAMES.get(symbol, symbol.replace("/USDT", ""))
            days_since_cross = n - 1 - cross_idx

            return {
                "symbol":            symbol,
                "name":              name,
                "current_price":     round(current, 6),
                "ma200":             round(ma200_cur, 6),
                "gap_pct":           round(gap_pct, 2),
                "days_since_cross":  days_since_cross,
                "below_days":        below_days,
                "total_score":       score,
                "signals":           signals,
                "rsi":               round(cur_rsi, 1),
                "funding_rate":      round(funding, 4),
                "scan_time":         datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            return None

    def analyze_all_coins(self, max_workers: int = 5) -> list:
        """전체 코인 병렬 스캔 (rate limit 고려해 워커 수 제한)"""
        results = []
        print(f"[스캔 시작] {len(self.symbols)}개 코인 분석 중...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.analyze_coin, sym): sym for sym in self.symbols}
            for i, future in enumerate(as_completed(futures)):
                sym = futures[future]
                try:
                    r = future.result(timeout=30)
                    if r:
                        results.append(r)
                        print(f"  ✓ {sym} → 점수 {r['total_score']}")
                except Exception as e:
                    pass
                # rate limit 방지
                if i % 10 == 9:
                    time.sleep(1)
        results.sort(key=lambda x: x["total_score"], reverse=True)
        print(f"[스캔 완료] 조건 충족: {len(results)}개")
        return results
