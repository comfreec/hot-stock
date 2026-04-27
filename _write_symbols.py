with open('_sp500_hardcoded.txt', encoding='utf-8') as f:
    sp500_code = f.read()

header = '"""\n미국 주요 종목 목록\n- S&P500 전체 503개 (하드코딩) + 나스닥 추가 성장주 + ETF\n"""\n\n'

nasdaq_extra = '''
# 나스닥 추가 성장주 (S&P500에 없는 것)
NASDAQ_EXTRA = {
    "NVDA": "엔비디아", "AMD": "AMD", "ADBE": "어도비", "QCOM": "퀄컴",
    "AMAT": "어플라이드머티리얼즈", "MU": "마이크론", "LRCX": "램리서치",
    "KLAC": "KLA코퍼레이션", "MRVL": "마벨테크놀로지", "ASML": "ASML",
    "PANW": "팔로알토네트웍스", "CRWD": "크라우드스트라이크", "SNPS": "시놉시스",
    "CDNS": "케이던스", "FTNT": "포티넷", "MCHP": "마이크로칩테크놀로지",
    "ON": "온세미컨덕터", "NXPI": "NXP세미컨덕터",
    "ABNB": "에어비앤비", "BKNG": "부킹홀딩스", "EXPE": "익스피디아",
    "ZM": "줌", "TEAM": "아틀라시안", "WDAY": "워크데이",
    "OKTA": "옥타", "DDOG": "데이터독", "SNOW": "스노우플레이크",
    "PLTR": "팔란티어", "RBLX": "로블록스", "UBER": "우버",
    "LYFT": "리프트", "DASH": "도어대시", "COIN": "코인베이스",
    "ORCL": "오라클", "CRM": "세일즈포스", "NOW": "서비스나우",
    "SHOP": "쇼피파이", "SQ": "블록", "TWLO": "트윌리오",
    "ZS": "지스케일러", "NET": "클라우드플레어", "HUBS": "허브스팟",
    "BILL": "빌닷컴", "GTLB": "깃랩", "MDB": "몽고DB",
    "ESTC": "엘라스틱", "CFLT": "컨플루언트", "U": "유니티",
    "APP": "앱러빈", "TTD": "더트레이드데스크", "ROKU": "로쿠",
    "SPOT": "스포티파이", "PINS": "핀터레스트", "SNAP": "스냅",
}

# ETF
ETFS = {
    "SPY": "S&P500 ETF", "QQQ": "나스닥100 ETF", "IWM": "러셀2000 ETF",
    "DIA": "다우존스 ETF", "VTI": "전체시장 ETF", "VOO": "뱅가드S&P500",
    "XLK": "기술주 ETF", "XLF": "금융 ETF", "XLE": "에너지 ETF",
    "XLV": "헬스케어 ETF", "XLY": "소비재 ETF", "XLI": "산업재 ETF",
    "XLC": "통신 ETF", "XLB": "소재 ETF", "XLRE": "부동산 ETF",
    "ARKK": "ARK이노베이션", "ARKG": "ARK게노믹스", "ARKW": "ARK인터넷",
    "SOXX": "반도체 ETF", "SMH": "반도체 ETF2", "SOXL": "반도체3배",
    "GLD": "금 ETF", "SLV": "은 ETF", "TLT": "장기국채 ETF",
    "HYG": "하이일드채권", "LQD": "투자등급채권",
    "VNQ": "부동산 ETF", "IEMG": "신흥국 ETF", "EFA": "선진국 ETF",
}

# 전체 합산 (중복 제거)
NASDAQ_100 = {**SP500_LARGE, **NASDAQ_EXTRA}
ALL_SYMBOLS = {**SP500_LARGE, **NASDAQ_EXTRA, **ETFS}


def get_symbols_by_category():
    return {
        "S&P500 전체": SP500_LARGE,
        "나스닥 추가": NASDAQ_EXTRA,
        "ETF": ETFS,
    }
'''

content = header + sp500_code + nasdaq_extra
with open('us_stock/symbols.py', 'w', encoding='utf-8') as f:
    f.write(content)

# 검증
ns = {}
exec(compile(content, 'symbols.py', 'exec'), ns)
print(f"SP500_LARGE: {len(ns['SP500_LARGE'])}개")
print(f"ALL_SYMBOLS: {len(ns['ALL_SYMBOLS'])}개")
print("symbols.py 저장 완료")
