"""
경량 ML 예측 모듈 (sklearn 기반)
- RandomForest + GradientBoosting 앙상블
- 20일 후 상승 확률 예측
- tensorflow 불필요, 빠른 실행
"""
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")


def _make_features(close: pd.Series, high: pd.Series,
                   low: pd.Series, vol: pd.Series) -> pd.DataFrame:
    """기술적 지표 피처 생성"""
    df = pd.DataFrame(index=close.index)

    # 수익률
    df["ret_1"]  = close.pct_change(1)
    df["ret_5"]  = close.pct_change(5)
    df["ret_20"] = close.pct_change(20)

    # 이동평균 이격
    for w in [5, 20, 60, 120, 240]:
        ma = close.rolling(w).mean()
        df[f"ma{w}_gap"] = (close - ma) / ma

    # 변동성
    df["vol_20"] = close.pct_change().rolling(20).std()
    df["vol_60"] = close.pct_change().rolling(60).std()

    # RSI
    d = close.diff()
    gain = d.where(d > 0, 0).rolling(14).mean()
    loss = (-d.where(d < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - 100 / (1 + gain / (loss + 1e-9))

    # MACD
    macd = close.ewm(span=12).mean() - close.ewm(span=26).mean()
    macd_s = macd.ewm(span=9).mean()
    df["macd_gap"] = (macd - macd_s) / (close + 1e-9)

    # 볼린저밴드
    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    df["bb_pos"] = (close - ma20) / (2 * std20 + 1e-9)
    df["bb_width"] = (4 * std20) / (ma20 + 1e-9)

    # 거래량
    vol_ma = vol.rolling(20).mean()
    df["vol_ratio"] = vol / (vol_ma + 1e-9)

    # 고가/저가 위치
    high_20 = high.rolling(20).max()
    low_20  = low.rolling(20).min()
    df["hl_pos"] = (close - low_20) / (high_20 - low_20 + 1e-9)

    # 52주 고점 대비
    high_52w = high.rolling(252).max()
    df["high52w_ratio"] = close / (high_52w + 1e-9)

    return df


def train_and_predict(symbol: str, hold_days: int = 20) -> dict | None:
    """
    과거 데이터로 모델 학습 후 현재 시점 상승 확률 예측
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

        # 타겟: hold_days 후 상승 여부
        future_ret = close.shift(-hold_days) / close - 1
        target = (future_ret > 0).astype(int)

        # 학습 데이터 준비
        data = feats.copy()
        data["target"] = target
        data = data.dropna()

        # 마지막 hold_days는 미래 데이터 없으므로 제외
        train_data = data.iloc[:-hold_days]
        if len(train_data) < 100:
            return None

        X = train_data.drop("target", axis=1).values
        y = train_data["target"].values

        # 스케일링
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # TimeSeriesSplit 교차검증
        tscv = TimeSeriesSplit(n_splits=3)
        accuracies = []

        rf  = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
        gb  = GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42)

        for train_idx, val_idx in tscv.split(X_scaled):
            X_tr, X_val = X_scaled[train_idx], X_scaled[val_idx]
            y_tr, y_val = y[train_idx], y[val_idx]
            rf.fit(X_tr, y_tr)
            acc = accuracy_score(y_val, rf.predict(X_val))
            accuracies.append(acc)

        model_accuracy = round(np.mean(accuracies) * 100, 1)

        # 전체 데이터로 최종 학습
        rf.fit(X_scaled, y)
        gb.fit(X_scaled, y)

        # 현재 시점 예측
        current_feats = feats.iloc[-1:].values
        if np.isnan(current_feats).any():
            return None

        current_scaled = scaler.transform(current_feats)
        prob_rf = rf.predict_proba(current_scaled)[0][1]
        prob_gb = gb.predict_proba(current_scaled)[0][1]
        prob_up = round((prob_rf * 0.5 + prob_gb * 0.5) * 100, 1)

        # 과거 유사 구간 평균 수익률
        all_feats = feats.dropna()
        all_scaled = scaler.transform(all_feats.values)
        probs = rf.predict_proba(all_scaled)[:, 1]
        high_prob_mask = probs > 0.6
        if high_prob_mask.sum() > 5:
            idx = all_feats.index[high_prob_mask]
            rets = []
            for i in idx:
                pos = close.index.get_loc(i)
                if pos + hold_days < len(close):
                    ret = (float(close.iloc[pos + hold_days]) - float(close.iloc[pos])) / float(close.iloc[pos]) * 100
                    rets.append(ret)
            expected_return = round(np.mean(rets), 1) if rets else 0
        else:
            expected_return = 0

        # 신뢰도: 모델 정확도 + 확률 강도
        confidence = "높음" if prob_up >= 65 and model_accuracy >= 55 else \
                     "보통" if prob_up >= 55 else "낮음"

        return {
            "prob_up":        prob_up,
            "expected_return": expected_return,
            "model_accuracy": model_accuracy,
            "confidence":     confidence,
            "hold_days":      hold_days,
        }

    except Exception as e:
        return None
