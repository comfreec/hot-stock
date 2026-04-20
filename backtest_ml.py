"""
백테스팅 - 실제 앱과 동일한 신호 체계로 과거 수익률 검증
ML 점수 보정 - 신호 조합으로 미래 수익률 예측
"""
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# 신호별 가중치 (백테스팅 + 실전 검증 기반으로 재조정)
SIGNAL_WEIGHTS = {
    # 핵심 강력 신호 (실전 수익률 높음)
    "bb_squeeze_expand":    2.5,  # BB수축→확장: 폭발 직전 가장 강력
    "stealth_accumulation": 2.3,  # 세력 매집: 조용한 거래량 증가
    "vol_price_rising3":    2.2,  # 3일 연속 거래량+가격 상승
    "vol_strong_cross":     2.5,  # 돌파 시 거래량 3배+ (강한 돌파)
    "vol_at_cross":         2.0,  # 돌파 시 거래량 2배+
    "vol_surge_sustained":  1.8,  # 돌파 전후 거래량 지속 증가
    "both_buying":          2.8,  # 기관+외국인 동시 순매수 (최강 수급)
    "smart_money_in":       1.8,  # 기관 또는 외국인 순매수
    "pullback_bounce":      2.0,  # 눌림목 반등: 최적 진입 타이밍
    "ichimoku_bull":        1.9,  # 일목균형표: 추세 확인
    "ma240_turning_up":     1.8,  # 240선 상승 전환: 장기 추세 전환
    # 보조 신호
    "ma_align":             1.6,  # 이평선 정배열
    "macd_cross":           1.5,  # MACD 골든크로스
    "obv_rising":           1.4,  # OBV 상승: 매집 확인
    "near_52w_high":        1.4,  # 52주 신고가 근처
    "pullback_recovery":    1.3,  # 눌림목 회복
    "mfi_oversold_recovery":1.3,  # MFI 과매도 반등
    "adx_strong":           1.2,  # ADX 추세 강도
    "stoch_cross":          1.2,  # 스토캐스틱 골든크로스
    "recent_vol":           1.2,  # 최근 거래량 증가
    "rsi_healthy":          1.0,  # RSI 건강 구간
    "above_vwap":           0.9,  # VWAP 위
    "hammer":               0.8,  # 망치형 캔들
    "bullish_engulf":       1.1,  # 장악형 캔들
}


def backtest_signal(symbol, lookback_days=60, hold_days=20, min_score=5):
    """
    실제 앱과 동일한 신호 체계로 백테스트
    - 과거 각 시점(5일 간격)에서 신호 계산
    - 신호 가중치 합산 >= min_score 시점 → hold_days 후 수익률 측정
    Returns: dict (avg_ret, win_rate, trades, sig_contrib) 또는 None
    """
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).history(period="2y")
        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        if len(df) < lookback_days + hold_days:
            return None

        close = df["Close"]
        high  = df["High"]
        low   = df["Low"]
        volume = df["Volume"]

        results     = []
        signal_hits = {k: {"count": 0, "total_ret": 0.0} for k in SIGNAL_WEIGHTS}

        for i in range(lookback_days, len(close) - hold_days, 5):
            c   = close.iloc[:i]
            h   = high.iloc[:i]
            l   = low.iloc[:i]
            v   = volume.iloc[:i]
            cur = float(c.iloc[-1])
            if cur <= 0:
                continue

            sigs = {}

            # BB 수축→확장
            try:
                bb_std = c.rolling(20).std()
                bb_mid = c.rolling(20).mean()
                bb_w   = (4 * bb_std) / bb_mid.replace(0, np.nan)
                bwa    = bb_w.rolling(40).mean()
                if not pd.isna(bwa.iloc[-5]):
                    sigs["bb_squeeze_expand"] = (
                        float(bb_w.iloc[-5]) < float(bwa.iloc[-5]) * 0.7 and
                        float(bb_w.iloc[-1]) > float(bb_w.iloc[-5])
                    )
            except: pass

            # MACD 골든크로스
            try:
                macd   = c.ewm(span=12).mean() - c.ewm(span=26).mean()
                macd_s = macd.ewm(span=9).mean()
                sigs["macd_cross"] = bool(
                    macd.iloc[-1] > macd_s.iloc[-1] and
                    macd.iloc[-2] <= macd_s.iloc[-2]
                )
            except: pass

            # 거래량 급증
            try:
                vol_ma = v.rolling(20).mean()
                sigs["recent_vol"] = bool(
                    float(v.iloc[-1]) / float(vol_ma.iloc[-1]) >= 1.5
                ) if float(vol_ma.iloc[-1]) > 0 else False
            except: pass

            # 이동평균 정배열
            try:
                ma5  = float(c.rolling(5).mean().iloc[-1])
                ma20 = float(c.rolling(20).mean().iloc[-1])
                ma60 = float(c.rolling(60).mean().iloc[-1]) if len(c) >= 60 else ma20
                sigs["ma_align"] = bool(cur > ma5 > ma20 > ma60)
            except: pass

            # OBV 상승
            try:
                obv = (np.sign(c.diff()) * v).fillna(0).cumsum()
                sigs["obv_rising"] = bool(float(obv.iloc[-1]) > float(obv.rolling(10).mean().iloc[-1]))
            except: pass

            # RSI 건강 구간 (40~70)
            try:
                d    = c.diff()
                gain = d.where(d > 0, 0).rolling(14).mean()
                loss = (-d.where(d < 0, 0)).rolling(14).mean()
                rsi  = 100 - 100 / (1 + gain.iloc[-1] / (loss.iloc[-1] + 1e-9))
                sigs["rsi_healthy"] = bool(40 <= rsi <= 70)
            except: pass

            # 240일선 상승 전환
            try:
                if len(c) >= 250:
                    ma240 = c.rolling(240).mean()
                    sigs["ma240_turning_up"] = bool(float(ma240.iloc[-1]) > float(ma240.iloc[-20]))
            except: pass

            # 52주 신고가 근처
            try:
                high_52w = float(h.tail(252).max())
                sigs["near_52w_high"] = bool((cur / high_52w) >= 0.95)
            except: pass

            # MFI 과매도 반등
            try:
                tp  = (h + l + c) / 3
                mf  = tp * v
                pos = mf.where(tp > tp.shift(1), 0).rolling(14).sum()
                neg = mf.where(tp < tp.shift(1), 0).rolling(14).sum()
                mfi = 100 - 100 / (1 + pos.iloc[-1] / (neg.iloc[-1] + 1e-9))
                sigs["mfi_oversold_recovery"] = bool(mfi < 40 and float(tp.iloc[-1]) > float(tp.iloc[-3]))
            except: pass

            # 스토캐스틱 골든크로스
            try:
                low14  = l.rolling(14).min()
                high14 = h.rolling(14).max()
                k_line = 100 * (c - low14) / (high14 - low14 + 1e-9)
                d_line = k_line.rolling(3).mean()
                sigs["stoch_cross"] = bool(
                    k_line.iloc[-1] > d_line.iloc[-1] and
                    k_line.iloc[-2] <= d_line.iloc[-2] and
                    k_line.iloc[-1] < 80
                )
            except: pass

            # 3일 연속 거래량+가격 상승
            try:
                sigs["vol_price_rising3"] = bool(
                    all(float(c.iloc[-j]) > float(c.iloc[-j-1]) for j in range(1, 4)) and
                    all(float(v.iloc[-j]) > float(v.iloc[-j-1]) for j in range(1, 4))
                )
            except: pass

            # 가중치 합산 점수
            score = sum(SIGNAL_WEIGHTS.get(k, 1.0) for k, val in sigs.items() if val is True)

            if score >= min_score:
                ret = (float(close.iloc[i + hold_days]) - cur) / cur * 100
                results.append({"ret": ret, "score": score})
                for k, val in sigs.items():
                    if val is True and k in signal_hits:
                        signal_hits[k]["count"] += 1
                        signal_hits[k]["total_ret"] += ret

        if not results:
            return None

        rets = [r["ret"] for r in results]
        sig_contrib = {
            k: round(v["total_ret"] / v["count"], 2)
            for k, v in signal_hits.items() if v["count"] > 0
        }

        return {
            "avg_ret":   round(float(np.mean(rets)), 2),
            "win_rate":  round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1),
            "trades":    len(results),
            "avg_score": round(float(np.mean([r["score"] for r in results])), 1),
            "hold_days": hold_days,
            "sig_contrib": sig_contrib,
        }
    except:
        return None


def ml_score_adjustment(signals: dict, base_score: int) -> float:
    """신호 조합 기반 ML 점수 보정 (최적화된 가중치 사용)"""
    weighted_sum = 0.0
    active_count = 0

    for sig, weight in SIGNAL_WEIGHTS.items():
        val = signals.get(sig, False)
        if isinstance(val, bool) and val:
            weighted_sum += weight
            active_count += 1

    if active_count == 0:
        return float(base_score)

    # 활성 신호 수에 따른 콤보 배율
    combo_multiplier = 1.0
    if active_count >= 5:   combo_multiplier = 1.3
    elif active_count >= 3: combo_multiplier = 1.15

    # BB수축 + MACD + 거래량 3종 세트
    if (signals.get("bb_squeeze_expand") and signals.get("macd_cross") and
            (signals.get("vol_strong_cross") or signals.get("vol_at_cross") or signals.get("recent_vol"))):
        combo_multiplier *= 1.2

    # 일목균형표 + 이평선 정배열
    if signals.get("ichimoku_bull") and signals.get("ma_align"):
        combo_multiplier *= 1.1

    # 기관+외국인 동시 수급 + 거래량 = 최강 조합
    if signals.get("both_buying") and (signals.get("vol_strong_cross") or signals.get("vol_at_cross")):
        combo_multiplier *= 1.15

    # 주봉 RSI 상승 + 일봉 눌림목 = 신뢰도 높은 조합 (개선1 반영)
    if signals.get("weekly_rsi_rising") and signals.get("rsi_slope_up"):
        combo_multiplier *= 1.1

    return round(base_score * combo_multiplier + (weighted_sum - active_count) * 0.5, 1)
