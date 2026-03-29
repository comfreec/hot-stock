"""
경량 ML 예측 모듈 (sklearn 기반) v2.0
- RandomForest + GradientBoosting 앙상블
- 240선 돌파 컨텍스트 피처 추가
- 타겟: 20일 후 2% 이상 상승 (의미있는 상승만 카운트)
- 상승장 구간 가중치 적용
"""
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")


def _make_features(close: pd.Series, high: pd.Series,
                   low: pd.Series, vol: pd.Series) -> pd.DataFrame:
    """기술적 지표 피처 생성 (240선 돌파 컨텍스트 포함)"""
    df = pd.DataFrame(index=close.index)

    # 수익률
    df["ret_1"]  = close.pct_change(1)
    df["ret_5"]  = close.pct_change(5)
    df["ret_20"] = close.pct_change(20)
    df["ret_60"] = close.pct_change(60)

    # 이동평균 이격
    for w in [5, 20, 60, 120, 240]:
        ma = close.rolling(w).mean()
        df[f"ma{w}_gap"] = (close - ma) / ma.replace(0, np.nan)

    # 이평선 정배열 여부
    ma5  = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    df["ma_align"] = ((ma5 > ma20) & (ma20 > ma60)).astype(int)

    # 240선 기울기 (20일)
    ma240 = close.rolling(240).mean()
    df["ma240_slope"] = ma240.pct_change(20)

    # 변동성
    df["vol_20"] = close.pct_change().rolling(20).std()
    df["vol_60"] = close.pct_change().rolling(60).std()
    df["vol_ratio_20_60"] = df["vol_20"] / (df["vol_60"] + 1e-9)  # 단기/장기 변동성 비율

    # RSI (14일, 20일)
    for period in [14, 20]:
        d = close.diff()
        gain = d.where(d > 0, 0).ewm(alpha=1/period, adjust=False).mean()
        loss = (-d.where(d < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        df[f"rsi{period}"] = 100 - 100 / (1 + gain / (loss + 1e-9))

    # MACD
    macd = close.ewm(span=12).mean() - close.ewm(span=26).mean()
    macd_s = macd.ewm(span=9).mean()
    df["macd_gap"]  = (macd - macd_s) / (close + 1e-9)
    df["macd_hist"] = (macd - macd_s).pct_change(3)  # 히스토그램 기울기

    # 볼린저밴드
    ma20_bb = close.rolling(20).mean()
    std20   = close.rolling(20).std()
    df["bb_pos"]   = (close - ma20_bb) / (2 * std20 + 1e-9)
    df["bb_width"] = (4 * std20) / (ma20_bb + 1e-9)
    df["bb_width_chg"] = df["bb_width"].pct_change(5)  # BB폭 변화율 (수축→확장)

    # 거래량
    vol_ma20 = vol.rolling(20).mean()
    vol_ma60 = vol.rolling(60).mean()
    df["vol_ratio"]    = vol / (vol_ma20 + 1e-9)
    df["vol_trend"]    = vol_ma20 / (vol_ma60 + 1e-9)  # 거래량 추세

    # OBV 기울기
    obv = (np.sign(close.diff()) * vol).fillna(0).cumsum()
    df["obv_slope"] = obv.pct_change(20)

    # 고가/저가 위치
    high_20 = high.rolling(20).max()
    low_20  = low.rolling(20).min()
    df["hl_pos"] = (close - low_20) / (high_20 - low_20 + 1e-9)

    # 52주 고점 대비
    high_52w = high.rolling(252).max()
    df["high52w_ratio"] = close / (high_52w + 1e-9)

    # ADX (추세 강도)
    try:
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        dm_plus  = (high - high.shift(1)).clip(lower=0)
        dm_minus = (low.shift(1) - low).clip(lower=0)
        atr14    = tr.ewm(span=14, adjust=False).mean()
        di_plus  = 100 * dm_plus.ewm(span=14, adjust=False).mean() / (atr14 + 1e-9)
        di_minus = 100 * dm_minus.ewm(span=14, adjust=False).mean() / (atr14 + 1e-9)
        dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus + 1e-9)
        df["adx"] = dx.ewm(span=14, adjust=False).mean() / 100
        df["di_diff"] = (di_plus - di_minus) / 100
    except:
        df["adx"]     = 0.0
        df["di_diff"] = 0.0

    return df


def train_and_predict(symbol: str, hold_days: int = 20) -> dict | None:
    """
    과거 데이터로 모델 학습 후 현재 시점 상승 확률 예측
    - 타겟: hold_days 후 2% 이상 상승 (의미있는 상승)
    - 상승 구간 샘플 가중치 적용
    Returns: {prob_up, expected_return, confidence, model_accuracy}
    """
    try:
        import yfinance as yf
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.metrics import accuracy_score

        df = yf.Ticker(symbol).history(period="3y")
        df = df.dropna(subset=["Open","High","Low","Close"])
        if len(df) < 300:
            return None

        close = df["Close"]
        high  = df["High"]
        low   = df["Low"]
        vol   = df["Volume"]

        # 피처 생성
        feats = _make_features(close, high, low, vol)

        # ── 타겟: hold_days 후 2% 이상 상승 (의미있는 상승만) ──
        future_ret = close.shift(-hold_days) / close - 1
        target = (future_ret > 0.02).astype(int)  # 0% → 2% 기준 상향

        # 학습 데이터 준비
        data = feats.copy()
        data["target"]     = target
        data["future_ret"] = future_ret
        data = data.dropna()

        train_data = data.iloc[:-hold_days]
        if len(train_data) < 100:
            return None

        X = train_data.drop(["target", "future_ret"], axis=1).values
        y = train_data["target"].values

        # ── 상승 구간 샘플 가중치 (불균형 보정) ──
        pos_count = y.sum()
        neg_count = len(y) - pos_count
        if pos_count > 0 and neg_count > 0:
            weight_pos = neg_count / pos_count  # 상승 샘플에 더 높은 가중치
            sample_weights = np.where(y == 1, weight_pos, 1.0)
        else:
            sample_weights = np.ones(len(y))

        # 스케일링
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # TimeSeriesSplit 교차검증
        tscv = TimeSeriesSplit(n_splits=3)
        accuracies = []
        rf = RandomForestClassifier(
            n_estimators=200, max_depth=8,
            min_samples_leaf=5, random_state=42, n_jobs=-1
        )
        gb = GradientBoostingClassifier(
            n_estimators=150, max_depth=5,
            learning_rate=0.05, random_state=42
        )

        for train_idx, val_idx in tscv.split(X_scaled):
            X_tr, X_val = X_scaled[train_idx], X_scaled[val_idx]
            y_tr, y_val = y[train_idx], y[val_idx]
            w_tr = sample_weights[train_idx]
            rf.fit(X_tr, y_tr, sample_weight=w_tr)
            acc = accuracy_score(y_val, rf.predict(X_val))
            accuracies.append(acc)

        model_accuracy = round(np.mean(accuracies) * 100, 1)

        # 전체 데이터로 최종 학습
        rf.fit(X_scaled, y, sample_weight=sample_weights)
        gb.fit(X_scaled, y, sample_weight=sample_weights)

        # 현재 시점 예측
        current_feats = feats.iloc[-1:].values
        if np.isnan(current_feats).any():
            # NaN 있으면 마지막 유효값으로 채움
            current_feats = np.nan_to_num(current_feats, nan=0.0)

        current_scaled = scaler.transform(current_feats)
        prob_rf = rf.predict_proba(current_scaled)[0][1]
        prob_gb = gb.predict_proba(current_scaled)[0][1]

        # RF 60% + GB 40% 앙상블 (RF가 더 안정적)
        prob_up_raw = prob_rf * 0.6 + prob_gb * 0.4

        # ── 현재 종목이 스캔 조건(240선 돌파 등)을 통과했으므로 컨텍스트 보정 ──
        # 스캔된 종목은 이미 긍정적 조건을 충족 → 베이스라인보다 높게 보정
        ma240 = close.rolling(240).mean()
        ma240_v = float(ma240.iloc[-1]) if not pd.isna(ma240.iloc[-1]) else None
        current_price = float(close.iloc[-1])

        context_boost = 0.0
        if ma240_v and current_price > ma240_v:
            gap = (current_price - ma240_v) / ma240_v
            if 0 < gap <= 0.10:
                context_boost += 0.05  # 240선 근처 = 초기 상승 구간 보정

        # MA 정배열 확인
        ma5_v  = float(close.rolling(5).mean().iloc[-1])
        ma20_v = float(close.rolling(20).mean().iloc[-1])
        ma60_v = float(close.rolling(60).mean().iloc[-1])
        if ma5_v > ma20_v > ma60_v:
            context_boost += 0.03

        prob_up_adjusted = min(prob_up_raw + context_boost, 0.95)
        prob_up = round(prob_up_adjusted * 100, 1)

        # 과거 유사 구간 평균 수익률
        all_feats  = feats.dropna()
        all_scaled = scaler.transform(np.nan_to_num(all_feats.values, nan=0.0))
        probs_all  = rf.predict_proba(all_scaled)[:, 1]
        high_prob_mask = probs_all > 0.55
        if high_prob_mask.sum() > 5:
            idx  = all_feats.index[high_prob_mask]
            rets = []
            for i in idx:
                pos = close.index.get_loc(i)
                if pos + hold_days < len(close):
                    ret = (float(close.iloc[pos + hold_days]) - float(close.iloc[pos])) / float(close.iloc[pos]) * 100
                    rets.append(ret)
            expected_return = round(np.mean(rets), 1) if rets else 0
        else:
            expected_return = 0

        # 신뢰도
        confidence = "높음" if prob_up >= 65 and model_accuracy >= 52 else \
                     "보통" if prob_up >= 55 else "낮음"

        return {
            "prob_up":         prob_up,
            "expected_return": expected_return,
            "model_accuracy":  model_accuracy,
            "confidence":      confidence,
            "hold_days":       hold_days,
        }

    except Exception:
        return None
