"""
미국 주요 종목 목록
- S&P500 대형주 + 나스닥100 주요 종목
- yfinance 심볼 기준
"""

# 나스닥 100 주요 종목
NASDAQ_100 = {
    "AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "AMZN": "아마존",
    "META": "메타", "GOOGL": "알파벳A", "GOOG": "알파벳C", "TSLA": "테슬라",
    "AVGO": "브로드컴", "COST": "코스트코", "NFLX": "넷플릭스", "AMD": "AMD",
    "ADBE": "어도비", "QCOM": "퀄컴", "INTC": "인텔", "TXN": "텍사스인스트루먼트",
    "AMAT": "어플라이드머티리얼즈", "MU": "마이크론", "LRCX": "램리서치",
    "KLAC": "KLA코퍼레이션", "MRVL": "마벨테크놀로지", "ASML": "ASML",
    "PANW": "팔로알토네트웍스", "CRWD": "크라우드스트라이크", "SNPS": "시놉시스",
    "CDNS": "케이던스", "FTNT": "포티넷", "MCHP": "마이크로칩테크놀로지",
    "ON": "온세미컨덕터", "NXPI": "NXP세미컨덕터",
    "PYPL": "페이팔", "INTU": "인튜이트", "ISRG": "인튜이티브서지컬",
    "REGN": "리제네론", "VRTX": "버텍스파마슈티컬", "GILD": "길리어드",
    "AMGN": "암젠", "BIIB": "바이오젠", "IDXX": "아이덱스",
    "DXCM": "덱스콤", "ILMN": "일루미나",
    "SBUX": "스타벅스", "MDLZ": "몬델리즈", "PEP": "펩시코",
    "ABNB": "에어비앤비", "BKNG": "부킹홀딩스", "EXPE": "익스피디아",
    "ZM": "줌", "TEAM": "아틀라시안", "WDAY": "워크데이",
    "OKTA": "옥타", "DDOG": "데이터독", "SNOW": "스노우플레이크",
    "PLTR": "팔란티어", "RBLX": "로블록스", "UBER": "우버",
    "LYFT": "리프트", "DASH": "도어대시", "COIN": "코인베이스",
}

# S&P500 대형주 (금융/에너지/헬스케어/소비재)
SP500_LARGE = {
    "JPM": "JP모건", "BAC": "뱅크오브아메리카", "WFC": "웰스파고",
    "GS": "골드만삭스", "MS": "모건스탠리", "BLK": "블랙록",
    "V": "비자", "MA": "마스터카드", "AXP": "아메리칸익스프레스",
    "XOM": "엑슨모빌", "CVX": "쉐브론", "COP": "코노코필립스",
    "JNJ": "존슨앤존슨", "UNH": "유나이티드헬스", "PFE": "화이자",
    "MRK": "머크", "ABT": "애보트", "TMO": "써모피셔",
    "LLY": "일라이릴리", "BMY": "브리스톨마이어스",
    "WMT": "월마트", "HD": "홈디포", "NKE": "나이키",
    "MCD": "맥도날드", "DIS": "디즈니", "CMCSA": "컴캐스트",
    "T": "AT&T", "VZ": "버라이즌",
    "BA": "보잉", "CAT": "캐터필러", "GE": "GE", "MMM": "3M",
    "HON": "허니웰", "RTX": "레이시온", "LMT": "록히드마틴",
    "BRK-B": "버크셔해서웨이B", "SPGI": "S&P글로벌",
    "NEE": "넥스트에라에너지", "DUK": "듀크에너지",
}

# ETF
ETFS = {
    "SPY": "S&P500 ETF", "QQQ": "나스닥100 ETF", "IWM": "러셀2000 ETF",
    "DIA": "다우존스 ETF", "VTI": "전체시장 ETF",
    "XLK": "기술주 ETF", "XLF": "금융 ETF", "XLE": "에너지 ETF",
    "XLV": "헬스케어 ETF", "XLY": "소비재 ETF",
    "ARKK": "ARK이노베이션", "ARKG": "ARK게노믹스",
    "SOXX": "반도체 ETF", "SMH": "반도체 ETF2",
    "GLD": "금 ETF", "SLV": "은 ETF", "TLT": "장기국채 ETF",
}

# 전체 합산
ALL_SYMBOLS = {**NASDAQ_100, **SP500_LARGE, **ETFS}

def get_symbols_by_category():
    return {
        "나스닥100": NASDAQ_100,
        "S&P500 대형주": SP500_LARGE,
        "ETF": ETFS,
    }
