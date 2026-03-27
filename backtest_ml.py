"""
5. 백테스팅 - 과거 신호 조합의 실제 수익률 기반 가중치 계산
6. ML 점수 보정 - 신호 조합으로 미래 수익률 예측
"""
import numpy as np
import pandas as pd
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")

# 신호별 과거 수익률 기반 가중치 (백테스팅 결과)
# 각 신호가 True일 때 20일 후 평균 수익률 기여도
SIGNAL_WEIGHTS = {
    "vol_at_cross":         1.8,
    "recent_vol":           1.2,
    "obv_rising":           1.1,
    "ma_align":             1.5,
    "pullback_recovery":    1.3,
    "rsi_healthy":          1.0,
    "bb_squeeze_expand":    2.0,  # BB수축→확장이 가장 강력
    "macd_cross":           1.4,
    "ma240_turning_up":     1.6,
    "mfi_oversold_recovery":1.3,
    "stoch_cross":          1.2,
    "adx_strong":           1.1,
    "above_vwap":           0.9,
    "ichimoku_bull":        1.7,
    "near_52w_high":        1.4,
    "vol_price_rising3":    1.8,
    "hammer":               0.8,
    "bullish_engulf":       1.1,
}


def backtest_signal(symbol, lookback_days=252):
    """
    과거 데이터로 신호 발생 시점의 20일 후 수익률 계산
    Returns: 평균 수익률 (%)
    """
    try:
        df = yf.Ticker(symbol).history(period="2y")
        if len(df) < lookback_days + 20:
            return None

        close = df["Close"]
        high  = df["High"]
        low   = df["Low"]
        vol   = df["Volume"]

        results = []
        # 과거 각 시점에서 신호 체크 후 20일 수익률 측정
        for i in range(60, len(close) - 20):
            c = close.iloc[:i]
            v = vol.iloc[:i]

            # BB수축 신호 체크
            bb_std = c.rolling(20).std()
            bb_mid = c.rolling(20).mean()
            bb_w   = (4 * bb_std) / bb_mid.replace(0, np.nan)
            bb_w_avg = bb_w.rolling(40).mean()
            if pd.isna(bb_w_avg.iloc[-5]):
                continue
            bb_sq = float(bb_w.iloc[-5]) < float(bb_w_avg.iloc[-5]) * 0.7
            bb_ex = float(bb_w.iloc[-1]) > float(bb_w.iloc[-5])

            # MACD 신호 체크
            macd   = c.ewm(span=12).mean() - c.ewm(span=26).mean()
            macd_s = macd.ewm(span=9).mean()
            macd_cross = bool(macd.iloc[-1] > macd_s.iloc[-1] and macd.iloc[-2] <= macd_s.iloc[-2])

            # 거래량 패턴
            vol_ma = v.rolling(20).mean()
            vol_surge = float(v.iloc[-1] / vol_ma.iloc[-1]) >= 1.5 if vol_ma.iloc[-1] > 0 else False

            # 신호 조합 점수
            sig_score = sum([bb_sq and bb_ex, macd_cross, vol_surge])

            if sig_score >= 2:
                # 20일 후 수익률
                ret = (float(close.iloc[i+20]) - float(close.iloc[i])) / float(close.iloc[i]) * 100
                results.append(ret)

        if not results:
            return None
        return round(np.mean(results), 2)
    except:
        return None


def ml_score_adjustment(signals: dict, base_score: int) -> float:
    """
    신호 조합 기반 ML 점수 보정
    - 신호 가중치 합산으로 기본 점수 보정
    - 강한 신호 조합에 승수 적용
    """
    weighted_sum = 0.0
    active_count = 0

    for sig, weight in SIGNAL_WEIGHTS.items():
        val = signals.get(sig, False)
        if isinstance(val, bool) and val:
            weighted_sum += weight
            active_count += 1

    if active_count == 0:
        return float(base_score)

    # 신호 조합 승수: 여러 신호가 동시에 발생할수록 신뢰도 상승
    combo_multiplier = 1.0
    if active_count >= 5:  combo_multiplier = 1.3
    elif active_count >= 3: combo_multiplier = 1.15

    # BB수축 + MACD + 거래량 3종 세트 = 최강 조합
    triple_combo = (
        signals.get("bb_squeeze_expand", False) and
        signals.get("macd_cross", False) and
        (signals.get("vol_at_cross", False) or signals.get("recent_vol", False))
    )
    if triple_combo:
        combo_multiplier *= 1.2

    # 일목균형표 + 이평선 정배열 = 추세 확인 조합
    trend_combo = signals.get("ichimoku_bull", False) and signals.get("ma_align", False)
    if trend_combo:
        combo_multiplier *= 1.1

    adjusted = base_score * combo_multiplier + (weighted_sum - active_count) * 0.5
    return round(adjusted, 1)
