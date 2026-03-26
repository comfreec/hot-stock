code = '''import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

ALL_SYMBOLS = [
    "005930.KS","000660.KS","035420.KS","051910.KS","006400.KS",
    "035720.KS","207940.KS","068270.KS","323410.KS","373220.KS",
    "005380.KS","000270.KS","105560.KS","055550.KS","012330.KS",
    "028260.KS","066570.KS","003550.KS","017670.KS","030200.KS",
    "196170.KQ","263750.KQ","293490.KQ","112040.KQ","357780.KQ",
    "086900.KQ","214150.KQ","950140.KQ","145020.KQ","041510.KQ","247540.KQ",
]

STOCK_NAMES = {
    "005930.KS":"삼성전자","000660.KS":"SK하이닉스","035420.KS":"NAVER",
    "051910.KS":"LG화학","006400.KS":"삼성SDI","035720.KS":"카카오",
    "207940.KS":"삼성바이오","068270.KS":"셀트리온","323410.KS":"카카오뱅크",
    "373220.KS":"LG에너지솔루션","005380.KS":"현대차","000270.KS":"기아",
    "105560.KS":"KB금융","055550.KS":"신한지주","012330.KS":"현대모비스",
    "028260.KS":"삼성물산","066570.KS":"LG전자","003550.KS":"LG",
    "017670.KS":"SK텔레콤","030200.KS":"KT","196170.KQ":"알테오젠",
    "263750.KQ":"펄어비스","293490.KQ":"카카오게임즈","112040.KQ":"위메이드",
    "357780.KQ":"솔브레인","086900.KQ":"메디톡스","214150.KQ":"클래시스",
    "950140.KQ":"잉글우드랩","145020.KQ":"휴젤","041510.KQ":"에스엠",
    "247540.KQ":"에코프로비엠",
}


def calc_rsi(close, period=20):
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calc_obv(data):
    obv = [0]
    for i in range(1, len(data)):
        if data["Close"].iloc[i] > data["Close"].iloc[i-1]:
            obv.append(obv[-1] + data["Volume"].iloc[i])
        elif data["Close"].iloc[i] < data["Close"].iloc[i-1]:
            obv.append(obv[-1] - data["Volume"].iloc[i])
        else:
            obv.append(obv[-1])
    return pd.Series(obv, index=data.index)


def analyze_ma240_breakout(symbol, 
    """
    전략:
    1. 240일선 아래 min_below_days(120일=6개월) 이상 조정
    2. 최근 max_cross_days(90일) 이내 240일선
    3. 현재 주가가 240일선 근처 (0 심 필터
    4. 
    """
    try:
        data = yf.Ticker(symbol).history(period="2y")
        if len(data) < 260:
            return None

        close = data["Close"]
        high  = data["High"]
        low   = data["Low"]
        vol   = data["Volume"]
        n     = len(close)

        ma240 = close.rolling(240).mean()
        ma120 = close.rolling(120).mean()
        ma60  = close.rolling(60).mean()
        ma20  = close.rolling(20).mean()
        ma5   = close.rolling(5).mean()

        if ma240.iloc[-1] !
            return None

        # ── 조건 3 먼저: 현
1])
        ma240_now     = float(ma240.iloc[-1])
        ma240_gap_pct = 

        # 240일선 위 0~max_gap_pct% 이내만 통과
        if not (0 <= ma240_gap_pct <= max_gap_pct):
            return None

─
        cross_idx = None
        search_start = 240)
:
            if (close.iloc[i] > ma240.iloc[iand

                cross_idx = i
                break

        if cross_idx is None:
            return None

        days_sincx


        below_days = 0
        for i in range( -1):

                break
            if close.iloc[i] < ma240.iloc[i]:
                below_dys += 1
lse:
                break

        if below_days:
None

        # ── 급등 예고 신호 점수화 ───────────────
        signals = {}
        score   = 0

        # [신호1] 돌파 시점 거래량 급증 (세력 개입 확인)
        vol_ma20 = vol.rolling(20).mean()
        cross_vol_ratio  = float(vol.iloc[cross_idx] / vol_ma20.il
        recent_vol_ratio = float(vol.iloc[-5:].mean(0 else 0
        signals["vol_at_cross"]   = cross_vol_ratio  2.0

        signals["cross_vol_ratio"]  = round(cr 2)
        signals["recent_vol_2)
        if signals["vol_at_cross"]: score += 3
        if signals["recent_vol"]:   score += 2

        # [신호2] OBV 지속 상승 (돌파 이후)
a)
        obv_after = obv.iloc[cross_idx:]
        obv_rising = len(obv_after) > 1 and f
        signals["obv_rising"] = obising
        if obv_rising: score += 2

        # [신호3] 이평선 정배열 (MA5 > MA20 > MA60)
        ma_al
        signals["ma_align"] = ma_align
        if ma_align: score += 3

        # [신호4] 240일선 위에서 눌림목 후 재상승
        prices_after = close.iloc
        if len(prices_after) >= 3:
            had_pullback     = float(prices_af
            now_above_entry  = current_price > float(clodx])
            signals["pullback_recovery"] = hatry
se:
            signals["pullback_recovery"] = False
        if signals["pullback_recovery"]: score += 2

        # [신호5] RSI(20) 건강한 상승 구간 (0~65)
e, 20)
        current_rsi = float(rsi.)
        signals["rsi"]         = round(c)
        signals["rsi_healthy"] = 40 <= cu65
        if signals["rsi_healthy"]: score += 2

        # [신호6] 볼린저밴드 수축 → 확장 시작 (에너지 충전 완료)
        bb_std   = close.rolling(20).std()
        bb_mid   = close.rolling(20).mean()
        bb_width = (4 * bb_std) / bp.nan)

        bb_squeeze   = float(bb_wiFalse
        bb_expanding = float(bb_width.il
        signals["bb_squeeze_then_expand"g
        if signals["bb_squ

        # [신호7] MACD 골든크로스
        exp1 = close.ewm(span=12).mean()
        exp2 = close.ewm(span=26).mean()
        macd     = exp1 - exp2

        macd_cross = bool(macd.iloc[-1and
                          macd.iloc[-2])
        signals["macd_cross"] = macd_cross
        if macd_cross: score += 2

        # [신호8] 240일선이 하락→횡보→상승 전환 (추세 전환 확인)
)
        ma240_slope_new = float()
        ma240_turning_up = ma240_slope_old <= 0 and ma240
        signals["ma240_turnp
        if ma240_turning_up: score += 3

        # [신호9] 캔들 패턴
        o_s = data["Open"]
        body = abs(close - o_s)
        lower_shadow = o_s.where(close > 
        total_range  = (high - low).replace(0, np
        try:
            hammer = bool(((lower_shaoc[-1])
t:
            hammer = False
        try:
            bullish_engulf = bool(((close > o_s) & (clos) &
                                   (close > o_s.shift(1)) & (o_s < close.shift(1
        except:
se
        signals[
        signals["bullish_engulf"] = bulf
        if hammer:         score += 1
        if bullish_engulf: score += 2

        # [신호10] 조정 기간이 길수록 가산점 (충분한 에너지 축적)
        if below_days >= 240:   score += 3  # 1년 이상
        elif below_days >= 180: score += 2  # 9개월 이상
        elif below_days >= 120: score += 1 개월 이상

        return {
            "symbol":           symbol,
            "name":             STOCK_ol),
            "current_price":    currence,
            "price_change_1d":  round),
            "ma240":            round 0),
            "ma240_gap":        roun
            "days_since_cross": dayscross,
            "below_days":       belo,
            "total_score":      score,
         
,
            "close_series"lose,
            "ma240_
a120,
60,
            "ma20_ser20,
            "rsi_sei,
            "obv_series":       obv,
            "volume_series":    vol,
            "vol_ma


    except Exception as e:
        return None


def run_ma240_scan(max_gap_pcays=90):
65)
    print(f"240일선 돌파 급등 예고 스캔")

    print("=" * 65)

    resul
    for symbol in ALL_SYMBOLS:
        print(f"  스캔: {syl}")
        r = analyze_ma240_breakout(symbol, max_gap_pct, min_below
        if r:
            results.append(r)

    results.sort(key=lambda x: x["total_sco

ts:
")
    else:
        print(f"\\n총
   n results:
and v]
            print(f"{r['name']:12} | 점수:{r['total_score']:2} | "
                  f"현재가:{} | "
                  f"240"

en(code))"완료:", lt(p())
prinstri.write(code.f:
    f) as ng="utf-8" encodi",w", "rategy.pya240_sth open("m'

wit
''a240_scan()
    run_m"__main__":me__ == 

if __nasults
rn re")
    retusigs}']}일 | {daysbelow_['{r정: f"조            
     }일전 | "ross']ince_cays_s'd  f"돌파:{r[                