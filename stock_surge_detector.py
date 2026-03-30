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

try:
    from backtest_ml import ml_score_adjustment
except:
    def ml_score_adjustment(signals, base_score): return float(base_score)

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
    "000810.KS","001450.KS","002790.KS","003230.KS",
    "003670.KS","004170.KS","004370.KS","004990.KS","005250.KS",
    "005830.KS","006260.KS","006360.KS","006650.KS","007310.KS",
    "008770.KS","009150.KS","009240.KS","009540.KS","009830.KS",
    "010140.KS","011170.KS","011780.KS","012450.KS",
    "012630.KS","014680.KS","015760.KS","016880.KS","017800.KS",
    "018880.KS","019170.KS","020150.KS","021080.KS",
    "023150.KS","024070.KS","025540.KS","026960.KS","027740.KS",
    "028050.KS","030000.KS","030610.KS","032830.KS","033240.KS",
    "034730.KS","035000.KS","035250.KS","037270.KS",
    "039130.KS","040910.KS","041650.KS","042700.KS","044490.KS",
    "045390.KS","047810.KS","051900.KS",
    "052690.KS","053210.KS","055490.KS","057050.KS","058430.KS",
    "060310.KS","061040.KS","063160.KS","064960.KS","066790.KS",
    "067160.KS","069260.KS","069620.KS","071840.KS",
    "072130.KS","073240.KS","075580.KS","077970.KS","079550.KS",
    "081660.KS","082640.KS","083420.KS","084010.KS","085620.KS",
    "086790.KS","088350.KS","089590.KS","090080.KS",
    "092200.KS","093050.KS","095570.KS","096040.KS","097520.KS",
    "099140.KS","100250.KS","101530.KS","103140.KS",
    "105630.KS","108670.KS","111770.KS","114090.KS",
    "120110.KS","128940.KS","130660.KS","138040.KS","139130.KS",
    "145990.KS","148150.KS","152100.KS","155660.KS","158430.KS",
    "163560.KS","170900.KS","178920.KS","185750.KS","187660.KS",
    "194370.KS","196170.KS","199800.KS","200130.KS","214150.KS",
    # ── 코스닥 우량 성장주 (섹터별 엄선) ──────────────────────────
    # 반도체/장비
    "039030.KQ","058470.KQ","064760.KQ","091580.KQ","095340.KQ",
    "101490.KQ","108320.KQ","122870.KQ","131970.KQ",
    "166090.KQ","183300.KQ","236200.KQ",
    # 바이오/헬스케어
    "086900.KQ","096530.KQ","137310.KQ","141080.KQ","145020.KQ",
    "196170.KQ","206650.KQ","214370.KQ","237690.KQ","247540.KQ",
    "950140.KQ","068760.KQ","086520.KQ",
    # 2차전지/소재
    "078600.KQ",
    # 엔터/미디어
    "035900.KQ","036030.KQ","041510.KQ","251270.KQ","253450.KQ",
    # IT/소프트웨어
    "053800.KQ","067160.KQ","112040.KQ","263750.KQ","293490.KQ",
    # 방산/항공
    "047810.KQ",
    # 기타 우량 코스닥
    "048260.KQ","200130.KQ",    "357780.KQ","041960.KQ","039440.KQ","033290.KQ","032500.KQ",
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
    # 코스닥 우량 성장주
    # 반도체/장비
    "039030.KQ":"이오테크닉스","058470.KQ":"리노공업","064760.KQ":"티씨케이",
    "091580.KQ":"상아프론테크","095340.KQ":"ISC","101490.KQ":"에스앤에스텍",
    "108320.KQ":"LX세미콘","122870.KQ":"와이지-원","131970.KQ":"두산테스나",
    "155900.KQ":"바텍","166090.KQ":"하나머티리얼즈","183300.KQ":"코미코",
    "236200.KQ":"슈프리마",
    # 바이오/헬스케어
    "086900.KQ":"메디톡스","096530.KQ":"씨젠","137310.KQ":"에스디바이오센서",
    "141080.KQ":"레고켐바이오","145020.KQ":"휴젤","196170.KQ":"알테오젠",
    "206650.KQ":"유바이오로직스","214370.KQ":"케어젠","237690.KQ":"에스티팜",
    "247540.KQ":"에코프로비엠","950140.KQ":"잉글우드랩","068760.KQ":"셀트리온제약",
    "091990.KQ":"셀트리온헬스케어","086520.KQ":"에코프로",
    # 2차전지/소재
    "066970.KQ":"엘앤에프","078600.KQ":"대주전자재료",
    # 엔터/미디어
    "035900.KQ":"JYP엔터","036030.KQ":"YG엔터테인먼트","041510.KQ":"에스엠",
    "251270.KQ":"넷마블","253450.KQ":"스튜디오드래곤",
    # IT/소프트웨어
    "053800.KQ":"안랩","067160.KQ":"아프리카TV","112040.KQ":"위메이드",
    "263750.KQ":"펄어비스","293490.KQ":"카카오게임즈",
    # 기타 우량 코스닥
    "048260.KQ":"오스템임플란트","060310.KQ":"3S","200130.KQ":"콜마비앤에이치",
    "214150.KQ":"클래시스","357780.KQ":"솔브레인","041960.KQ":"블루콤",
    "039440.KQ":"에스티아이","033290.KQ":"NICE평가정보","032500.KQ":"케이엠더블유",
}


class KoreanStockSurgeDetector:
    def __init__(self, max_gap_pct=15.0, min_below_days=90, max_cross_days=60):  # max_cross 120→60
        self.all_symbols    = ALL_SYMBOLS
        self.max_gap_pct    = max_gap_pct
        self.min_below_days = min_below_days
        self.max_cross_days = max_cross_days

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
            res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=2)
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
            res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=2)
            soup = BeautifulSoup(res.text, "html.parser")
            titles = [a.get_text() for a in soup.select(".title")]
            hits = [k for t in titles for k in keys if k in t]
            return len(hits) > 0, hits[:3]
        except:
            return False, []

    def _institutional_flow(self, symbol):
        """기관/외국인 순매수 크롤링 (네이버 금융) - timeout 3초 제한
        Returns: (inst_net: int, foreign_net: int)  단위: 주
        """
        code = symbol.replace(".KS","").replace(".KQ","")
        try:
            url = f"https://finance.naver.com/item/frgn.naver?code={code}"
            res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=2)
            soup = BeautifulSoup(res.text, "html.parser")
            rows = soup.select("table.type2 tr")
            inst_net    = 0
            foreign_net = 0
            for row in rows[1:6]:
                cols = row.select("td")
                if len(cols) < 5:
                    continue
                try:
                    f_val = cols[4].get_text(strip=True).replace(",","").replace("+","")
                    if f_val and f_val != "-":
                        foreign_net += int(f_val)
                    i_val = cols[5].get_text(strip=True).replace(",","").replace("+","") if len(cols) > 5 else "0"
                    if i_val and i_val != "-":
                        inst_net += int(i_val)
                except:
                    pass
            return inst_net, foreign_net
        except:
            return 0, 0

    # ── 핵심 분석 ────────────────────────────────────────────────

    def _market_condition(self):
        """KOSPI 시장 상태 확인 - 상승장/하락장"""
        try:
            kospi = yf.Ticker("^KS11").history(period="1y")
            kospi = kospi.dropna(subset=["Close"])
            close = kospi["Close"]
            ma200 = float(close.rolling(200).mean().iloc[-1])
            ma60  = float(close.rolling(60).mean().iloc[-1])
            cur   = float(close.iloc[-1])
            # 200일선 위 = 상승장, 아래 = 하락장
            bull = cur > ma200
            # 60일선 기울기 (모멘텀)
            slope = (float(close.rolling(60).mean().iloc[-1]) - float(close.rolling(60).mean().iloc[-20])) / float(close.rolling(60).mean().iloc[-20]) * 100
            return bull, round(slope, 2)
        except:
            return True, 0

    def _sector_momentum(self, symbol):
        """섹터 모멘텀 - 같은 섹터 ETF 기준"""
        sector_etf = {
            # 반도체
            "005930.KS":"091160.KS","000660.KS":"091160.KS","011070.KS":"091160.KS",
            # 자동차
            "005380.KS":"091180.KS","000270.KS":"091180.KS",
            # 바이오
            "207940.KS":"244580.KS","068270.KS":"244580.KS","145020.KQ":"244580.KS",
            # 2차전지
            "006400.KS":"305720.KS","051910.KS":"305720.KS","373220.KS":"305720.KS",
            # 방산
            "047810.KS":"459580.KS","064350.KS":"459580.KS",
        }
        etf = sector_etf.get(symbol)
        if not etf:
            return 0
        try:
            df = yf.Ticker(etf).history(period="3mo")
            df = df.dropna(subset=["Close"])
            close = df["Close"]
            ret_1m = (float(close.iloc[-1]) - float(close.iloc[-20])) / float(close.iloc[-20]) * 100
            return round(ret_1m, 2)
        except:
            return 0

    def analyze_stock(self, symbol):
        """
        필수 조건 3가지 모두 통과해야 결과 반환:
          1) 240일선 아래 min_below_days 이상 조정
          2) 최근 max_cross_days 이내 240일선 상향 돌파
          3) 현재 주가가 240일선 위 0 ~ max_gap_pct% 이내
        """
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="2y")
            data = data.dropna(subset=["Open","High","Low","Close"])
            if len(data) < 260:
                return None

            # ── 재무 자동 검증 (강화) ─────────────────────────────
            try:
                info = ticker.info
                market_cap       = info.get("marketCap", 0) or 0
                per              = info.get("trailingPE") or info.get("forwardPE") or 0
                operating_income = info.get("operatingIncome") or 0
                revenue          = info.get("totalRevenue") or 0
                revenue_growth   = info.get("revenueGrowth") or None   # 전년비 매출 성장률 (소수)
                earnings_growth  = info.get("earningsGrowth") or None  # 전년비 이익 성장률

                # 시총 1000억 미만 제외
                if market_cap > 0 and market_cap < 100_000_000_000:
                    return None
                # 영업이익 적자 제외 (데이터 있을 때만)
                if operating_income != 0 and operating_income < 0:
                    return None
                # PER 비정상 제외 (음수 or 200 초과)
                if per and (per < 0 or per > 200):
                    return None
                # ▶ 추가: 매출 성장률 마이너스 제외 (데이터 있을 때만)
                if revenue_growth is not None and revenue_growth < -0.05:
                    return None  # 매출 5% 이상 역성장 제외
                # ▶ 추가: 이익 성장률 심각한 역성장 제외
                if earnings_growth is not None and earnings_growth < -0.30:
                    return None  # 이익 30% 이상 역성장 제외
            except:
                pass  # 재무 데이터 없으면 통과 (데이터 누락 방어)

            close = data["Close"]
            high  = data["High"]
            low   = data["Low"]
            vol   = data["Volume"]
            n     = len(close)

            # ── 거래대금 필터: 일평균 20억 미만 제외 ────────────────
            avg_price  = float(close.tail(20).mean())
            avg_vol    = float(vol.tail(20).mean())
            avg_amount = avg_price * avg_vol  # 일평균 거래대금 (원)
            if avg_amount < 2_000_000_000:    # 20억 미만 제외
                return None

            # ── 하락장 필터: analyze_all_stocks에서 사전 체크 완료 ──
            # (KOSPI 200일선 체크는 analyze_all_stocks에서 1회만 수행)

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
            # → 먼저 이격 체크해서 이미 많이 오른 종목은 즉시 제외 (불필요한 연산 방지)
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

            # ── 가짜 돌파 방지: 돌파 후 3일 이상 240선 위 유지 ──
            confirm_end = min(cross_idx + 4, n)
            days_above_after = sum(
                1 for i in range(cross_idx, confirm_end)
                if float(close.iloc[i]) > float(ma240.iloc[i])
            )
            if days_above_after < 3:
                return None  # 3일 미만 유지 = 가짜 돌파

            # ── 돌파 강도 확인: 돌파 당일 종가가 240선 위 0.5% 이상 ──
            cross_gap = (float(close.iloc[cross_idx]) - float(ma240.iloc[cross_idx])) / float(ma240.iloc[cross_idx]) * 100
            if cross_gap < 0.5:
                return None  # 0.5% 미만 돌파 = 신뢰도 낮음

            days_since_cross = n - 1 - cross_idx

            # ── 필수 조건 3: 돌파 직전 연속 하락 기간이 min_below_days 이상 ──
            # 연속 기간 우선, 부족하면 전체 기간으로 fallback
            below_days = 0
            for i in range(cross_idx - 1, -1, -1):
                if not pd.isna(ma240.iloc[i]) and close.iloc[i] < ma240.iloc[i]:
                    below_days += 1
                else:
                    break
            # 연속 기간이 부족하면 cross_idx 이전 전체 기간으로 재계산
            if below_days < self.min_below_days:
                below_days = sum(
                    1 for i in range(cross_idx)
                    if not pd.isna(ma240.iloc[i]) and close.iloc[i] < ma240.iloc[i]
                )
            if below_days < self.min_below_days:
                return None

            # ── 필수 조건 4: 240선 기울기 확인 (급격한 하락 추세만 제외) ──
            ma240_at_cross     = float(ma240.iloc[cross_idx])
            ma240_20d_before   = float(ma240.iloc[cross_idx - 20]) if cross_idx >= 20 else ma240_at_cross
            ma240_slope_at_cross = (ma240_at_cross - ma240_20d_before) / ma240_20d_before * 100
            if ma240_slope_at_cross < -3.0:
                return None  # 20일간 3% 이상 급락 중인 240선 돌파만 제외 (기준 완화: -1.5 → -3.0)

            # ── 필수 조건 5: 돌파 후 240선 아래 재이탈 횟수 제한 ──
            # 단 하루도 허용 안 하면 종목이 거의 없음 → 3일 이상 연속 이탈만 제외
            rebreak_count = 0
            consecutive = 0
            for i in range(cross_idx + 1, n):
                if float(close.iloc[i]) < float(ma240.iloc[i]):
                    consecutive += 1
                    if consecutive >= 3:  # 3일 연속 이탈 = 진짜 추세 붕괴
                        return None
                else:
                    consecutive = 0

            # ── 여기까지 통과 = 핵심 조건 충족 ─────────────────────
            score   = 0
            signals = {}

            # [+3] 돌파 시 거래량 급증 (기준 강화: 3배 이상 = 강한 신호)
            vol_ma20 = vol.rolling(20).mean()
            cross_vr = float(vol.iloc[cross_idx] / vol_ma20.iloc[cross_idx]) if vol_ma20.iloc[cross_idx] > 0 else 0
            recent_vr = float(vol.iloc[-5:].mean() / vol_ma20.iloc[-1]) if vol_ma20.iloc[-1] > 0 else 0
            signals["vol_at_cross"]     = cross_vr >= 2.0
            signals["vol_strong_cross"] = cross_vr >= 3.0   # ▶ 추가: 강한 돌파 (3배 이상)
            signals["recent_vol"]       = recent_vr >= 1.5
            signals["cross_vol_ratio"]  = round(cross_vr, 2)
            signals["recent_vol_ratio"] = round(recent_vr, 2)
            if signals["vol_strong_cross"]: score += 4   # 3배 이상 = 4점
            elif signals["vol_at_cross"]:   score += 3   # 2배 이상 = 3점
            if signals["recent_vol"]:       score += 2

            # ▶ 추가: 돌파 전후 5일 평균 거래량 증가 확인
            try:
                vol_before5 = float(vol.iloc[cross_idx-5:cross_idx].mean())
                vol_after5  = float(vol.iloc[cross_idx:cross_idx+5].mean())
                signals["vol_surge_sustained"] = vol_after5 > vol_before5 * 1.5
                if signals["vol_surge_sustained"]: score += 2
            except:
                signals["vol_surge_sustained"] = False

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

            # [+2] MFI (Money Flow Index) - RSI에 거래량 가중
            try:
                tp = (high + low + close) / 3
                mf = tp * vol
                pos_mf = mf.where(tp > tp.shift(1), 0).rolling(14).sum()
                neg_mf = mf.where(tp < tp.shift(1), 0).rolling(14).sum()
                mfi = 100 - (100 / (1 + pos_mf / neg_mf.replace(0, np.nan)))
                cur_mfi = float(mfi.iloc[-1])
                signals["mfi"] = round(cur_mfi, 1)
                signals["mfi_oversold_recovery"] = (
                    float(mfi.iloc[-5:].min()) < 25 and cur_mfi > 30
                )
                if signals["mfi_oversold_recovery"]: score += 2
            except:
                signals["mfi"] = 50
                signals["mfi_oversold_recovery"] = False

            # [+2] 스토캐스틱 골든크로스 (과매도 구간에서)
            try:
                low14  = low.rolling(14).min()
                high14 = high.rolling(14).max()
                k = 100 * (close - low14) / (high14 - low14).replace(0, np.nan)
                d = k.rolling(3).mean()
                stoch_cross = bool(
                    k.iloc[-1] > d.iloc[-1] and
                    k.iloc[-2] <= d.iloc[-2] and
                    k.iloc[-1] < 50
                )
                signals["stoch_k"] = round(float(k.iloc[-1]), 1)
                signals["stoch_cross"] = stoch_cross
                if stoch_cross: score += 2
            except:
                signals["stoch_k"] = 50
                signals["stoch_cross"] = False

            # [+2] ADX (추세 강도) - 25 이상이면 추세 확인
            try:
                tr_s = pd.concat([
                    high - low,
                    (high - close.shift(1)).abs(),
                    (low  - close.shift(1)).abs()
                ], axis=1).max(axis=1)
                dm_plus  = (high - high.shift(1)).where((high - high.shift(1)) > (low.shift(1) - low), 0).clip(lower=0)
                dm_minus = (low.shift(1) - low).where((low.shift(1) - low) > (high - high.shift(1)), 0).clip(lower=0)
                atr14    = tr_s.ewm(span=14, adjust=False).mean()
                di_plus  = 100 * dm_plus.ewm(span=14, adjust=False).mean() / atr14.replace(0, np.nan)
                di_minus = 100 * dm_minus.ewm(span=14, adjust=False).mean() / atr14.replace(0, np.nan)
                dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, np.nan)
                adx = dx.ewm(span=14, adjust=False).mean()
                cur_adx = float(adx.iloc[-1])
                signals["adx"] = round(cur_adx, 1)
                signals["adx_strong"] = cur_adx >= 25 and float(di_plus.iloc[-1]) > float(di_minus.iloc[-1])
                if signals["adx_strong"]: score += 2
            except:
                signals["adx"] = 0
                signals["adx_strong"] = False

            # [+2] VWAP 위에 있는지 (당일 매수세 우위)
            try:
                vwap = (close * vol).rolling(20).sum() / vol.rolling(20).sum()
                signals["above_vwap"] = bool(current > float(vwap.iloc[-1]))
                if signals["above_vwap"]: score += 2
            except:
                signals["above_vwap"] = False

            # [+3] 일목균형표 - 구름대 돌파
            try:
                tenkan  = (high.rolling(9).max()  + low.rolling(9).min())  / 2
                kijun   = (high.rolling(26).max() + low.rolling(26).min()) / 2
                senkou_a = ((tenkan + kijun) / 2).shift(26)
                senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
                cloud_top = pd.concat([senkou_a, senkou_b], axis=1).max(axis=1)
                cloud_bot = pd.concat([senkou_a, senkou_b], axis=1).min(axis=1)
                ichimoku_bull = bool(
                    current > float(cloud_top.iloc[-1]) and
                    float(tenkan.iloc[-1]) > float(kijun.iloc[-1])
                )
                signals["ichimoku_bull"] = ichimoku_bull
                if ichimoku_bull: score += 3
            except:
                signals["ichimoku_bull"] = False

            # [+2] 52주 신고가 근처 (5% 이내)
            high_52w = float(high.tail(252).max())
            high_ratio = current / high_52w
            signals["near_52w_high"] = high_ratio >= 0.95
            signals["high_ratio"] = round(high_ratio * 100, 1)
            if signals["near_52w_high"]: score += 2

            # ── 시장 상태 필터 ────────────────────────────────────
            market_bull, market_slope = self._market_condition()
            signals["market_bull"]  = market_bull
            signals["market_slope"] = market_slope
            # 하락장이면 점수 패널티
            if not market_bull:
                score = max(0, score - 3)
            elif market_slope > 2:
                score += 2  # 강한 상승장 가산점

            # ── 섹터 모멘텀 ──────────────────────────────────────
            sector_ret = self._sector_momentum(symbol)
            signals["sector_momentum"] = sector_ret
            if sector_ret > 5:   score += 3  # 섹터 강세
            elif sector_ret > 2: score += 1
            elif sector_ret < -5: score = max(0, score - 2)  # 섹터 약세 패널티

            # ── 거래량 패턴 정교화 ───────────────────────────────
            # 3일 연속 거래량 증가 + 가격 상승
            vol3 = vol.iloc[-3:]
            close3 = close.iloc[-3:]
            vol_rising3 = bool(
                vol3.iloc[-1] > vol3.iloc[-2] > vol3.iloc[-3] and
                close3.iloc[-1] > close3.iloc[-2] > close3.iloc[-3]
            )
            signals["vol_price_rising3"] = vol3_rising = vol_rising3
            if vol_rising3: score += 3

            # ── 눌림목 깊이 측정 ─────────────────────────────────
            # 240선 돌파 후 최대 하락폭
            prices_after = close.iloc[cross_idx:]
            if len(prices_after) >= 3:
                entry_price = float(close.iloc[cross_idx])
                min_after   = float(prices_after.min())
                pullback_depth = (entry_price - min_after) / entry_price * 100
                signals["pullback_depth"] = round(pullback_depth, 1)
                # 얕은 눌림(5~15%) = 강한 신호
                if 3 <= pullback_depth <= 15:
                    score += 3
                elif pullback_depth > 25:
                    score = max(0, score - 2)  # 깊은 눌림 패널티
            else:
                signals["pullback_depth"] = 0

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

            # [+1~2] 뉴스 감성 - 손익비 통과 후 실행 (기본값)
            sentiment, pos_n, neg_n = 0, 0, 0
            signals["news_sentiment"] = 0
            signals["pos_news"]       = 0
            signals["neg_news"]       = 0

            # [+2] 호재 공시 - 손익비 통과 후 실행 (기본값)
            has_disc, disc_types = False, []
            signals["has_disclosure"]   = False
            signals["disclosure_types"] = []

            # ── 1. 세력 매집 감지 (조용한 거래량 증가) ──────────
            # 주가 횡보 + 거래량 꾸준히 증가 = 세력 매집 패턴
            try:
                price_std_20  = float(close.tail(20).std() / close.tail(20).mean())  # 가격 변동성
                vol_trend_20  = float(vol.tail(20).mean() / vol.tail(40).mean())      # 거래량 증가율
                # 가격은 조용하고(변동성 낮음) 거래량은 늘어남 = 매집
                signals["stealth_accumulation"] = price_std_20 < 0.05 and vol_trend_20 > 1.2
                if signals["stealth_accumulation"]: score += 3
            except:
                signals["stealth_accumulation"] = False

            # ── 2. 눌림목 타이밍 정교화 ─────────────────────────
            # 240선 돌파 후 첫 번째 눌림목에서 반등 중인지 확인
            try:
                prices_after = close.iloc[cross_idx:]
                if len(prices_after) >= 5:
                    # 최근 5일 저점 대비 반등 중
                    recent_low5  = float(close.tail(5).min())
                    recent_high5 = float(close.tail(5).max())
                    bounce_pct   = (current - recent_low5) / (recent_low5 + 1e-9) * 100
                    # 저점 대비 2% 이상 반등 + 고점 갱신 중
                    signals["pullback_bounce"] = bounce_pct >= 2.0 and current >= recent_high5 * 0.98
                    if signals["pullback_bounce"]: score += 3
                else:
                    signals["pullback_bounce"] = False
            except:
                signals["pullback_bounce"] = False

            # ── 3. 복합 신호 승수 (강한 조합 = 배율 적용) ───────
            # BB수축 + MACD + 거래량 3종 세트 = 최강 조합
            triple_combo = (
                signals.get("bb_squeeze_expand") and
                signals.get("macd_cross") and
                (signals.get("vol_at_cross") or signals.get("recent_vol"))
            )
            if triple_combo:
                score = int(score * 1.3)  # 30% 가산

            # 이평선 정배열 + 일목균형표 + ADX = 추세 확인 조합
            trend_combo = (
                signals.get("ma_align") and
                signals.get("ichimoku_bull") and
                signals.get("adx_strong")
            )
            if trend_combo:
                score = int(score * 1.2)  # 20% 가산

            # 세력 매집 + OBV 상승 + 눌림목 반등 = 매집 완료 신호
            accumulation_combo = (
                signals.get("stealth_accumulation") and
                signals.get("obv_rising") and
                signals.get("pullback_bounce")
            )
            if accumulation_combo:
                score = int(score * 1.25)  # 25% 가산

            # ── 4. 섹터 모멘텀 강화 ─────────────────────────────
            # 같은 섹터 상위 3개 종목 동반 상승 여부 체크
            try:
                sector_peers = {
                    "005930.KS": ["000660.KS","011070.KS"],  # 반도체
                    "000660.KS": ["005930.KS","011070.KS"],
                    "005380.KS": ["000270.KS","012330.KS"],  # 자동차
                    "000270.KS": ["005380.KS","012330.KS"],
                    "006400.KS": ["051910.KS","373220.KS"],  # 2차전지
                    "051910.KS": ["006400.KS","373220.KS"],
                    "207940.KS": ["068270.KS","196170.KQ"],  # 바이오
                    "068270.KS": ["207940.KS","196170.KQ"],
                }
                peers = sector_peers.get(symbol, [])
                if peers:
                    peer_up_count = 0
                    for peer in peers:
                        try:
                            peer_data = yf.Ticker(peer).history(period="5d").dropna(subset=["Close"])
                            if len(peer_data) >= 2:
                                peer_ret = (float(peer_data["Close"].iloc[-1]) - float(peer_data["Close"].iloc[-5])) / float(peer_data["Close"].iloc[-5]) * 100
                                if peer_ret > 2:
                                    peer_up_count += 1
                        except:
                            pass
                    signals["peer_momentum"] = peer_up_count
                    if peer_up_count >= 2: score += 3   # 동종 섹터 동반 상승
                    elif peer_up_count == 1: score += 1
                else:
                    signals["peer_momentum"] = 0
            except:
                signals["peer_momentum"] = 0

            # ── 기관/외국인 수급 ─────────────────────────────────
            inst_net, foreign_net = self._institutional_flow(symbol)
            signals["inst_net_buy"]    = inst_net
            signals["foreign_net_buy"] = foreign_net
            signals["smart_money_in"]  = inst_net > 0 or foreign_net > 0
            signals["both_buying"]     = inst_net > 0 and foreign_net > 0
            if signals["both_buying"]:     score += 4  # 기관+외국인 동시 순매수 = 강한 신호
            elif signals["smart_money_in"]: score += 2  # 둘 중 하나라도 순매수

            # ── 필수 신호 최소 개수 조건 ─────────────────────────
            # 핵심 신호 중 최소 2개 이상 충족해야 통과
            core_signals = [
                signals.get("ma_align"),           # 이평선 정배열
                signals.get("obv_rising"),          # OBV 상승
                signals.get("vol_at_cross"),        # 돌파 시 거래량
                signals.get("vol_surge_sustained"), # 거래량 지속
                signals.get("macd_cross"),          # MACD 골든크로스
                signals.get("ichimoku_bull"),       # 일목균형표
                signals.get("adx_strong"),          # ADX 추세
                signals.get("smart_money_in"),      # 기관/외국인 수급
            ]
            core_count = sum(1 for s in core_signals if s)
            signals["core_signal_count"] = core_count
            if core_count < 2:
                return None  # 핵심 신호 2개 미만 = 제외

            # ── ML 점수 보정 ─────────────────────────────────────
            ml_adjusted = ml_score_adjustment(signals, score)
            signals["ml_adjusted_score"] = ml_adjusted

            # ── 손익비 필터: 2.5:1 미만 제외 ────────────────────────
            try:
                tr_f = pd.concat([
                    high - low,
                    (high - close.shift(1)).abs(),
                    (low  - close.shift(1)).abs()
                ], axis=1).max(axis=1)
                atr_f = float(tr_f.rolling(14).mean().dropna().iloc[-1])

                ma240_v_f  = float(ma240.iloc[-1])
                ma20_v_f   = float(ma20.iloc[-1])
                swing_low_f = float(low.tail(20).min())

                # 매수가 (240선 근거)
                entry_cands = []
                if not pd.isna(ma240_v_f):
                    entry_cands.append(ma240_v_f * 1.005)
                entry_cands.append(ma20_v_f)
                entry_cands.append(swing_low_f)
                valid_e = [p for p in entry_cands if p < current]
                entry_f = max(valid_e) if valid_e else current

                # 손절가
                stop_cands = []
                if not pd.isna(ma240_v_f):
                    stop_cands.append(ma240_v_f * 0.995)
                stop_cands.append(swing_low_f - atr_f * 1.0)
                stop_f = max(stop_cands) if stop_cands else entry_f * 0.93
                stop_f = max(stop_f, entry_f * 0.88)
                stop_f = min(stop_f, entry_f * 0.95)
                risk_f = max(entry_f - stop_f, entry_f * 0.01)

                # 목표가: 피보나치 확장 + ATR 복합 (앱과 동일 방식)
                recent_high_f = float(high.tail(120).max())
                recent_low_f  = float(low.tail(120).min())
                swing_range_f = max(recent_high_f - recent_low_f, entry_f * 0.01)

                target_cands = sorted([
                    x for x in [
                        recent_low_f + swing_range_f * 1.272,
                        recent_low_f + swing_range_f * 1.618,
                        recent_low_f + swing_range_f * 2.0,
                        recent_high_f * 1.05,
                        entry_f + atr_f * 3.0,
                        entry_f + atr_f * 5.0,
                    ] if x > entry_f * 1.03
                ])
                min_rr3 = entry_f + risk_f * 3.0
                valid_t = [x for x in target_cands if x >= min_rr3]
                if valid_t:
                    weights = [1 / (x - entry_f) for x in valid_t]
                    target_f = sum(x * w for x, w in zip(valid_t, weights)) / sum(weights)
                elif target_cands:
                    target_f = target_cands[-1]
                else:
                    target_f = entry_f + risk_f * 3.0
                target_f = min(target_f, entry_f * 2.0)

                rr_f = (target_f - entry_f) / risk_f
                signals["rr_ratio"] = round(rr_f, 2)
                if rr_f < 2.0:  # 기준 완화: 2.5 → 2.0 (피보나치 기반이라 더 현실적)
                    return None
            except:
                signals["rr_ratio"] = 0

            # ── 손익비 통과 후에만 크롤링 실행 (속도 최적화) ────
            # 하루 1~5개 통과 종목에만 크롤링 → 224번 → 1~5번으로 감소
            sentiment, pos_n, neg_n = self._news_sentiment(symbol)
            signals["news_sentiment"] = sentiment
            signals["pos_news"]       = pos_n
            signals["neg_news"]       = neg_n
            if sentiment > 0.3: score += 2
            elif sentiment > 0: score += 1

            has_disc, disc_types = self._dart_disclosure(symbol)
            signals["has_disclosure"]   = has_disc
            signals["disclosure_types"] = disc_types
            if has_disc: score += 2

            # ML 점수 재보정 (뉴스/공시 반영 후)
            ml_adjusted = ml_score_adjustment(signals, score)
            signals["ml_adjusted_score"] = ml_adjusted

            return {
                "symbol":           symbol,
                "name":             STOCK_NAMES.get(symbol, symbol),
                "current_price":    current,
                "price_change_1d":  round((current - float(close.iloc[-2])) / float(close.iloc[-2]) * 100, 2),
                "ma240":            round(ma240_v, 0),
                "ma240_gap":        round(gap_pct, 2),
                "days_since_cross": days_since_cross,
                "below_days":       below_days,
                "total_score":      int(ml_adjusted),
                "raw_score":        score,
                "signals":          signals,
                "rsi":              signals["rsi"],
                "vol_ratio":        round(recent_vr, 2),
                "vol_accumulation": signals["vol_at_cross"] or signals["recent_vol"],
                "obv_divergence":   signals["obv_rising"],
                "bb_squeeze":       signals["bb_squeeze_expand"],
                "squeeze_ratio":    0,
                "near_52w_high":    signals.get("near_52w_high", False),
                "high_ratio":       signals.get("high_ratio", 0),
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
                "inst_net_buy":     inst_net,
                "foreign_net_buy":  foreign_net,
                "smart_money_in":   signals["smart_money_in"],
                "both_buying":      signals["both_buying"],
                "core_signal_count": signals["core_signal_count"],
                "cross_gap_pct":    round(cross_gap, 2),
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

        # ── KOSPI 상태 1회만 가져와서 공유 (종목별 중복 호출 제거) ──
        kospi_filter = True  # 기본값: 통과
        try:
            kospi_df = yf.Ticker("^KS11").history(period="1y").dropna(subset=["Close"])
            kospi_cur   = float(kospi_df["Close"].iloc[-1])
            kospi_ma200 = float(kospi_df["Close"].rolling(200).mean().iloc[-1])
            if kospi_cur < kospi_ma200 * 0.97:
                kospi_filter = False  # 하락장 → 전체 차단
                print(f"[하락장 감지] KOSPI {kospi_cur:,.0f} / 200일선 {kospi_ma200:,.0f} → 스캔 중단")
        except:
            pass

        if not kospi_filter:
            return []

        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(self.analyze_stock, sym): sym for sym in self.all_symbols}
            for future in as_completed(futures):
                sym = futures[future]
                try:
                    r = future.result()
                    if r:
                        results.append(r)
                        print(f"  OK {sym} ({r['total_score']}pt)")
                    else:
                        print(f"  [X] {sym}")
                except Exception as e:
                    print(f"  [!] {sym}: {e}")
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