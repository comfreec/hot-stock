"""
한국 주식 급등 예측 프로그램 v3.0
핵심 전략: 240일선 아래 6개월+ 조정 → 최근 돌파 → 현재 근처 → 급등 신호 복합
"""
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

ALL_SYMBOLS = [
    # 코스피 200 (2024년 기준)
    "005930.KS","000660.KS","035420.KS","051910.KS","006400.KS",
    "035720.KS","207940.KS","068270.KS","323410.KS","373220.KS",
    "005380.KS","000270.KS","105560.KS","055550.KS","012330.KS",
    "028260.KS","066570.KS","003550.KS","017670.KS","030200.KS",
    "000100.KS","001040.KS","002380.KS","003490.KS","004020.KS",
    "005490.KS","007070.KS","010130.KS","010950.KS","011070.KS",
    "011200.KS","016360.KS","018260.KS","021240.KS","023530.KS",
    "024110.KS","029780.KS","032640.KS","033780.KS","034020.KS",
    "034220.KS","036460.KS","036570.KS","042660.KS","047050.KS",
    "051600.KS","060980.KS","064350.KS","071050.KS","078930.KS",
    "086280.KS","090430.KS","096770.KS","097950.KS","100840.KS",
    "161390.KS","175330.KS","180640.KS","192400.KS","204320.KS",
    "267250.KS","316140.KS","326030.KS","329180.KS","336260.KS",
    # 추가 코스피 200 종목
    "000810.KS","001450.KS","002790.KS","003230.KS","003600.KS",
    "003670.KS","004170.KS","004370.KS","004990.KS","005250.KS",
    "005830.KS","006260.KS","006360.KS","006650.KS","007310.KS",
    "008770.KS","009150.KS","009240.KS","009540.KS","009830.KS",
    "010140.KS","010620.KS","011170.KS","011780.KS","012450.KS",
    "012630.KS","014680.KS","015760.KS","016880.KS","017800.KS",
    "018880.KS","019170.KS","019440.KS","020150.KS","021080.KS",
    "023150.KS","024070.KS","025540.KS","026960.KS","027740.KS",
    "028050.KS","030000.KS","030610.KS","032830.KS","033240.KS",
    "034730.KS","035000.KS","035250.KS","036490.KS","037270.KS",
    "039130.KS","040910.KS","041650.KS","042700.KS","044490.KS",
    "045390.KS","046080.KS","047810.KS","049770.KS","051900.KS",
    "052690.KS","053210.KS","055490.KS","057050.KS","058430.KS",
    "060310.KS","061040.KS","063160.KS","064960.KS","066790.KS",
    "067160.KS","068400.KS","069260.KS","069620.KS","071840.KS",
    "072130.KS","073240.KS","075580.KS","077970.KS","079550.KS",
    "081660.KS","082640.KS","083420.KS","084010.KS","085620.KS",
    "086790.KS","088350.KS","089590.KS","090080.KS","091990.KS",
    "092200.KS","093050.KS","095570.KS","096040.KS","097520.KS",
    "099140.KS","100250.KS","101530.KS","102280.KS","103140.KS",
    "105630.KS","108670.KS","111770.KS","114090.KS","115390.KS",
    "120110.KS","128940.KS","130660.KS","138040.KS","139130.KS",
    "145990.KS","148150.KS","152100.KS","155660.KS","158430.KS",
    "163560.KS","170900.KS","178920.KS","185750.KS","187660.KS",
    "194370.KS","196170.KS","199800.KS","200130.KS","214150.KS",
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
    "000100.KS":"유한양행",
    "001040.KS":"CJ",
    "002380.KS":"KCC",
    "003490.KS":"대한항공",
    "004020.KS":"현대제철",
    "005490.KS":"POSCO홀딩스",
    "007070.KS":"GS리테일",
    "010130.KS":"고려아연",
    "010950.KS":"S-Oil",
    "011070.KS":"LG이노텍",
    "011200.KS":"HMM",
    "016360.KS":"삼성증권",
    "018260.KS":"삼성에스디에스",
    "021240.KS":"코웨이",
    "023530.KS":"롯데쇼핑",
    "024110.KS":"기업은행",
    "029780.KS":"삼성카드",
    "032640.KS":"LG유플러스",
    "033780.KS":"KT&G",
    "034020.KS":"두산에너빌리티",
    "034220.KS":"LG디스플레이",
    "036460.KS":"한국가스공사",
    "036570.KS":"엔씨소프트",
    "042660.KS":"한화오션",
    "047050.KS":"포스코인터내셔널",
    "051600.KS":"한전KPS",
    "060980.KS":"한세실업",
    "064350.KS":"현대로템",
    "071050.KS":"한국금융지주",
    "078930.KS":"GS",
    "086280.KS":"현대글로비스",
    "090430.KS":"아모레퍼시픽",
    "096770.KS":"SK이노베이션",
    "097950.KS":"CJ제일제당",
    "100840.KS":"SNT모티브",
    "161390.KS":"한국타이어앤테크놀로지",
    "175330.KS":"JB금융지주",
    "180640.KS":"한진칼",
    "192400.KS":"쿠쿠홀딩스",
    "204320.KS":"HL만도",
    "267250.KS":"HD현대",
    "316140.KS":"우리금융지주",
    "326030.KS":"SK바이오팜",
    "329180.KS":"HD현대중공업",
    "336260.KS":"두산밥캣",
    "035900.KQ":"JYP엔터",
    "036030.KQ":"YG엔터테인먼트",
    "039030.KQ":"이오테크닉스",
    "041960.KQ":"블루콤",
    "045390.KQ":"대아티아이",
    "048260.KQ":"오스템임플란트",
    "053800.KQ":"안랩",
    "058470.KQ":"리노공업",
    "060310.KQ":"3S",
    "064760.KQ":"티씨케이",
    "066970.KQ":"엘앤에프",
    "067160.KQ":"아프리카TV",
    "068760.KQ":"셀트리온제약",
    "078600.KQ":"대주전자재료",
    "086520.KQ":"에코프로",
    "091580.KQ":"상아프론테크",
    "095340.KQ":"ISC",
    "096530.KQ":"씨젠",
    "101490.KQ":"에스앤에스텍",
    "108320.KQ":"LX세미콘",
    "122870.KQ":"와이지-원",
    "131970.KQ":"두산테스나",
    "137310.KQ":"에스디바이오센서",
    "141080.KQ":"레고켐바이오",
    "155900.KQ":"바텍",
    "166090.KQ":"하나머티리얼즈",
    "183300.KQ":"코미코",
    "200130.KQ":"콜마비앤에이치",
    "206650.KQ":"유바이오로직스",
    "214370.KQ":"케어젠",
    "236200.KQ":"슈프리마",
    "237690.KQ":"에스티팜",
    "251270.KQ":"넷마블",
    "253450.KQ":"스튜디오드래곤",
    "256840.KQ":"한국비엔씨",
    "270210.KQ":"에스알바이오텍",
    "277810.KQ":"레인보우로보틱스",
    "290650.KQ":"엔씨소프트",
    "298380.KQ":"에이비엘바이오",
    "302440.KQ":"SK바이오사이언스",
    # 추가 코스피200 종목명
    "000810.KS":"삼성화재","001450.KS":"현대해상","002790.KS":"아모레G",
    "003230.KS":"삼양식품","003600.KS":"SK케미칼","003670.KS":"포스코퓨처엠",
    "004170.KS":"신세계","004370.KS":"농심","004990.KS":"롯데지주",
    "005250.KS":"녹십자홀딩스","005830.KS":"DB손해보험","006260.KS":"LS",
    "006360.KS":"GS건설","006650.KS":"대한유화","007310.KS":"오뚜기",
    "008770.KS":"호텔신라","009150.KS":"삼성전기","009240.KS":"한샘",
    "009540.KS":"HD한국조선해양","009830.KS":"한화솔루션","010140.KS":"삼성중공업",
    "010620.KS":"HD현대미포","011170.KS":"롯데케미칼","011780.KS":"금호석유",
    "012450.KS":"한화에어로스페이스","012630.KS":"HDC","014680.KS":"한솔케미칼",
    "015760.KS":"한국전력","016880.KS":"웅진","017800.KS":"현대엘리베이터",
    "018880.KS":"한온시스템","019170.KS":"신풍제약","019440.KS":"세아제강지주",
    "020150.KS":"일진전기","021080.KS":"에쓰오일우","023150.KS":"MH에탄올",
    "024070.KS":"WISCOM","025540.KS":"한국단자","026960.KS":"동서",
    "027740.KS":"마니커","028050.KS":"삼성엔지니어링","030000.KS":"제일기획",
    "030610.KS":"교보증권","032830.KS":"삼성생명","033240.KS":"자화전자",
    "034730.KS":"SK","035000.KS":"크라운제과","035250.KS":"강원랜드",
    "036490.KS":"SK케미칼우","037270.KS":"YG PLUS","039130.KS":"하나투어",
    "040910.KS":"아이씨디","041650.KS":"상신브레이크","042700.KS":"한미반도체",
    "044490.KS":"태웅","045390.KS":"대아티아이","046080.KS":"에코바이오",
    "047810.KS":"한국항공우주","049770.KS":"동원F&B","051900.KS":"LG생활건강",
    "052690.KS":"한전기술","053210.KS":"스카이라이프","055490.KS":"OCI홀딩스",
    "057050.KS":"현대홈쇼핑","058430.KS":"포스코인터내셔널","060310.KS":"3S",
    "061040.KS":"한국콜마","063160.KS":"종근당홀딩스","064960.KS":"S&T모티브",
    "066790.KS":"씨씨에스충북방송","067160.KS":"아프리카TV","068400.KS":"SK렌터카",
    "069260.KS":"휴켐스","069620.KS":"대웅제약","071840.KS":"하이록코리아",
    "072130.KS":"유니온머티리얼","073240.KS":"금호타이어","075580.KS":"세진중공업",
    "077970.KS":"STX엔진","079550.KS":"LIG넥스원","081660.KS":"한국콜마홀딩스",
    "082640.KS":"동양생명","083420.KS":"그린케미칼","084010.KS":"대한제강",
    "085620.KS":"미래에셋생명","086790.KS":"하나금융지주","088350.KS":"한화생명",
    "089590.KS":"제주항공","090080.KS":"평화홀딩스","091990.KS":"셀트리온헬스케어",
    "092200.KS":"현대글로비스","093050.KS":"LF","095570.KS":"AJ네트웍스",
    "096040.KS":"코리아써키트","097520.KS":"엠씨넥스","099140.KS":"인터지스",
    "100250.KS":"진양홀딩스","101530.KS":"해태제과식품","102280.KS":"쌍용C&E",
    "103140.KS":"풍산","105630.KS":"한세실업","108670.KS":"LX하우시스",
    "111770.KS":"영원무역","114090.KS":"GKL","115390.KS":"락앤락",
    "120110.KS":"코오롱인더","128940.KS":"한미약품","130660.KS":"한전산업",
    "138040.KS":"메리츠금융지주","139130.KS":"DGB금융지주","145990.KS":"삼양사",
    "148150.KS":"세아베스틸지주","152100.KS":"JTBC","155660.KS":"DSR",
    "158430.KS":"KG케미칼","163560.KS":"동일고무벨트","170900.KS":"동아에스티",
    "178920.KS":"PI첨단소재","185750.KS":"종근당","187660.KS":"에이비엘바이오",
    "194370.KS":"제이에스코퍼레이션","196170.KS":"알테오젠","199800.KS":"툴젠",
    "200130.KS":"콜마비앤에이치","214150.KS":"클래시스",
}


class KoreanStockSurgeDetector:
    def __init__(self, max_gap_pct=15.0, min_below_days=90, max_cross_days=180):
        self.all_symbols    = ALL_SYMBOLS
        self.max_gap_pct    = max_gap_pct    # 현재가가 240선 위 최대 %
        self.min_below_days = min_below_days # 240선 아래 최소 일수
        self.max_cross_days = max_cross_days # 돌파 후 최대 경과 일수

    # ── 보조 지표 ────────────────────────────────────────────────

    def _rsi(self, close, period=20):
        """Wilder's Smoothing RSI - 증권사 표준 방식"""
        d = close.diff()
        gain = d.where(d > 0, 0.0)
        loss = -d.where(d < 0, 0.0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, float('nan'))
        return 100 - (100 / (1 + rs))

    def _obv(self, data):
        obv = [0]
        for i in range(1, len(data)):
            if data["Close"].iloc[i] > data["Close"].iloc[i-1]:
                obv.append(obv[-1] + data["Volume"].iloc[i])
            elif data["Close"].iloc[i] < data["Close"].iloc[i-1]:
                obv.append(obv[-1] - data["Volume"].iloc[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=data.index)

    def _news_sentiment(self, symbol):
        code = symbol.replace(".KS","").replace(".KQ","")
        pos = ["급등","상승","돌파","신고가","수주","흑자","성장","호실적","매수","상향","계약"]
        neg = ["급락","하락","적자","손실","매도","하향","감소","부진","우려"]
        try:
            url = "https://finance.naver.com/item/news_news.naver?code=" + code + "&page=1"
            res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=5)
            soup = BeautifulSoup(res.text, "html.parser")
            titles = [a.get_text() for a in soup.select(".title")]
            p = sum(1 for t in titles for k in pos if k in t)
            n = sum(1 for t in titles for k in neg if k in t)
            total = p + n
            return round((p-n)/total, 2) if total > 0 else 0, p, n
        except:
            return 0, 0, 0

    def _dart_disclosure(self, symbol):
        code = symbol.replace(".KS","").replace(".KQ","")
        keys = ["자기주식취득","수주","공급계약","투자","합병"]
        try:
            url = "https://finance.naver.com/item/news_dis.naver?code=" + code
            res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=5)
            soup = BeautifulSoup(res.text, "html.parser")
            titles = [a.get_text() for a in soup.select(".title")]
            hits = [k for t in titles for k in keys if k in t]
            return len(hits) > 0, hits[:3]
        except:
            return False, []

    # ── 핵심 분석 ────────────────────────────────────────────────

    def analyze_stock(self, symbol):
        """
        필수 조건 3가지 모두 통과해야 결과 반환:
          1) 240일선 아래 min_below_days 이상 조정
          2) 최근 max_cross_days 이내 240일선 상향 돌파
          3) 현재 주가가 240일선 위 0 ~ max_gap_pct% 이내
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

            if pd.isna(ma240.iloc[-1]):
                return None

            current = float(close.iloc[-1])
            ma240_v = float(ma240.iloc[-1])

            # ── 필수 조건 1: 현재 주가가 240선 근처 (0 ~ max_gap_pct%) ──
            gap_pct = (current - ma240_v) / ma240_v * 100
            if not (0 <= gap_pct <= self.max_gap_pct):
                return None

            # ── 필수 조건 2: 최근 max_cross_days 이내 240선 상향 돌파 ──
            cross_idx = None
            for i in range(n-1, max(n - self.max_cross_days - 1, 240), -1):
                if (close.iloc[i] > ma240.iloc[i] and
                        close.iloc[i-1] <= ma240.iloc[i-1]):
                    cross_idx = i
                    break
            if cross_idx is None:
                return None

            days_since_cross = n - 1 - cross_idx

            # ── 필수 조건 3: 돌파 이전 min_below_days 이상 240선 아래 ──
            below_days = sum(
                1 for i in range(cross_idx)
                if not pd.isna(ma240.iloc[i]) and close.iloc[i] < ma240.iloc[i]
            )
            if below_days < self.min_below_days:
                return None

            # ── 여기까지 통과 = 핵심 조건 충족 ─────────────────────
            score   = 0
            signals = {}

            # [+3] 돌파 시 거래량 급증
            vol_ma20 = vol.rolling(20).mean()
            cross_vr = float(vol.iloc[cross_idx] / vol_ma20.iloc[cross_idx]) if vol_ma20.iloc[cross_idx] > 0 else 0
            recent_vr = float(vol.iloc[-5:].mean() / vol_ma20.iloc[-1]) if vol_ma20.iloc[-1] > 0 else 0
            signals["vol_at_cross"]   = cross_vr >= 2.0
            signals["recent_vol"]     = recent_vr >= 1.5
            signals["cross_vol_ratio"]  = round(cross_vr, 2)
            signals["recent_vol_ratio"] = round(recent_vr, 2)
            if signals["vol_at_cross"]: score += 3
            if signals["recent_vol"]:   score += 2

            # [+2] OBV 지속 상승
            obv = self._obv(data)
            obv_after = obv.iloc[cross_idx:]
            signals["obv_rising"] = len(obv_after) > 1 and float(obv_after.iloc[-1]) > float(obv_after.iloc[0])
            if signals["obv_rising"]: score += 2

            # [+3] 이평선 정배열 MA5 > MA20 > MA60
            signals["ma_align"] = bool(ma5.iloc[-1] > ma20.iloc[-1] > ma60.iloc[-1])
            if signals["ma_align"]: score += 3

            # [+2] 눌림목 후 재상승
            pa = close.iloc[cross_idx:]
            signals["pullback_recovery"] = (
                len(pa) >= 3 and
                float(pa.min()) < float(pa.iloc[0]) and
                current > float(close.iloc[cross_idx])
            )
            if signals["pullback_recovery"]: score += 2

            # [+2] RSI(20) 건강 구간 40~65
            rsi = self._rsi(close, 20)
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
            macd    = close.ewm(span=12).mean() - close.ewm(span=26).mean()
            macd_s  = macd.ewm(span=9).mean()
            signals["macd_cross"] = bool(
                macd.iloc[-1] > macd_s.iloc[-1] and
                macd.iloc[-2] <= macd_s.iloc[-2]
            )
            if signals["macd_cross"]: score += 2

            # [+3] 240일선 하락→상승 전환
            ma240_old_slope = float(ma240.iloc[-20]) - float(ma240.iloc[-40])
            ma240_new_slope = float(ma240.iloc[-1])  - float(ma240.iloc[-20])
            signals["ma240_turning_up"] = ma240_old_slope <= 0 and ma240_new_slope >= 0
            if signals["ma240_turning_up"]: score += 3

            # [+1~2] 캔들 패턴
            o_s  = data["Open"]
            body = abs(close - o_s)
            ls   = o_s.where(close > o_s, close) - low
            tr   = (high - low).replace(0, np.nan)
            try:    signals["hammer"]         = bool(((ls >= 2*body) & (tr > 0)).iloc[-1])
            except: signals["hammer"]         = False
            try:    signals["bullish_engulf"] = bool(((close > o_s) & (close.shift(1) < o_s.shift(1)) & (close > o_s.shift(1)) & (o_s < close.shift(1))).iloc[-1])
            except: signals["bullish_engulf"] = False
            if signals["hammer"]:         score += 1
            if signals["bullish_engulf"]: score += 2

            # [+1~3] 조정 기간 가산점
            if   below_days >= 240: score += 3
            elif below_days >= 180: score += 2
            elif below_days >= 120: score += 1

            # [+1~2] 뉴스 감성
            sentiment, pos_n, neg_n = self._news_sentiment(symbol)
            signals["news_sentiment"] = sentiment
            signals["pos_news"]       = pos_n
            signals["neg_news"]       = neg_n
            if sentiment > 0.3: score += 2
            elif sentiment > 0: score += 1

            # [+2] 호재 공시
            has_disc, disc_types = self._dart_disclosure(symbol)
            signals["has_disclosure"]   = has_disc
            signals["disclosure_types"] = disc_types
            if has_disc: score += 2

            return {
                "symbol":           symbol,
                "name":             STOCK_NAMES.get(symbol, symbol),
                "current_price":    current,
                "price_change_1d":  round((current - float(close.iloc[-2])) / float(close.iloc[-2]) * 100, 2),
                "ma240":            round(ma240_v, 0),
                "ma240_gap":        round(gap_pct, 2),
                "days_since_cross": days_since_cross,
                "below_days":       below_days,
                "total_score":      score,
                "signals":          signals,
                "rsi":              signals["rsi"],
                "vol_ratio":        round(recent_vr, 2),
                "vol_accumulation": signals["vol_at_cross"] or signals["recent_vol"],
                "obv_divergence":   signals["obv_rising"],
                "bb_squeeze":       signals["bb_squeeze_expand"],
                "squeeze_ratio":    0,
                "near_52w_high":    False,
                "high_ratio":       0,
                "golden_cross_imminent": signals["ma_align"],
                "macd_cross":       signals["macd_cross"],
                "disparity":        round(gap_pct, 2),
                "candle_patterns":  {
                    "hammer":         signals["hammer"],
                    "bullish_engulf": signals["bullish_engulf"],
                    "morning_star":   False,
                    "inv_hammer":     False,
                },
                "news_sentiment":   sentiment,
                "pos_news":         pos_n,
                "neg_news":         neg_n,
                "has_disclosure":   has_disc,
                "disclosure_types": disc_types,
                "close_series":     close,
                "ma240_series":     ma240,
                "ma60_series":      ma60,
                "ma20_series":      ma20,
                "rsi_series":       rsi,
                "volume_series":    vol,
                "vol_ma_series":    vol_ma20,
            }

        except Exception as e:
            return None

    def analyze_all_stocks(self):
        results = []
        print("스캔 중 (240일선 조건 필터)...")
        for symbol in self.all_symbols:
            print(f"  {symbol}")
            r = self.analyze_stock(symbol)
            if r:
                results.append(r)
        return sorted(results, key=lambda x: x["total_score"], reverse=True)

    def run_analysis(self):
        print(f"한국 주식 급등 예측 v3.0  ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        print(f"조건: 240선 아래 {self.min_below_days}일+ → {self.max_cross_days}일내 돌파 → 근처 {self.max_gap_pct}%")
        results = self.analyze_all_stocks()
        print(f"\n총 {len(results)}개 종목 발견")
        for r in results:
            print(f"  {r['name']:12} 점수:{r['total_score']:2d}  "
                  f"240선위:{r['ma240_gap']:+.1f}%  "
                  f"조정:{r['below_days']}일  돌파:{r['days_since_cross']}일전")
        return results


if __name__ == "__main__":
    KoreanStockSurgeDetector().run_analysis()