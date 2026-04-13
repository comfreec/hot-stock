"""
코인 심볼 목록 - 업비트 KRW 마켓 기반
"""

# 기본 이름 매핑
COIN_NAMES = {
    "BTC/KRW": "비트코인", "ETH/KRW": "이더리움", "XRP/KRW": "리플",
    "SOL/KRW": "솔라나", "ADA/KRW": "에이다", "DOGE/KRW": "도지코인",
    "AVAX/KRW": "아발란체", "DOT/KRW": "폴카닷", "LINK/KRW": "체인링크",
    "UNI/KRW": "유니스왑", "ATOM/KRW": "코스모스", "LTC/KRW": "라이트코인",
    "ETC/KRW": "이더리움클래식", "BCH/KRW": "비트코인캐시", "APT/KRW": "앱토스",
    "ARB/KRW": "아비트럼", "OP/KRW": "옵티미즘", "SUI/KRW": "수이",
    "INJ/KRW": "인젝티브", "TIA/KRW": "셀레스티아", "SEI/KRW": "세이",
    "JTO/KRW": "지토", "PYTH/KRW": "파이스네트워크", "WIF/KRW": "도그위프햇",
    "BONK/KRW": "봉크", "PEPE/KRW": "페페", "FLOKI/KRW": "플로키",
    "SHIB/KRW": "시바이누", "FIL/KRW": "파일코인", "ICP/KRW": "인터넷컴퓨터",
    "NEAR/KRW": "니어프로토콜", "ALGO/KRW": "알고랜드", "VET/KRW": "비체인",
    "SAND/KRW": "샌드박스", "MANA/KRW": "디센트럴랜드", "AXS/KRW": "엑시인피니티",
    "GALA/KRW": "갈라", "ENJ/KRW": "엔진코인", "AAVE/KRW": "에이브",
    "MKR/KRW": "메이커", "SNX/KRW": "신세틱스", "CRV/KRW": "커브",
    "COMP/KRW": "컴파운드", "LDO/KRW": "리도", "PENDLE/KRW": "펜들",
    "GRT/KRW": "더그래프", "RUNE/KRW": "토르체인", "FTM/KRW": "팬텀",
    "EGLD/KRW": "멀티버스X", "THETA/KRW": "세타", "CHZ/KRW": "칠리즈",
    "FET/KRW": "페치AI", "RNDR/KRW": "렌더", "WLD/KRW": "월드코인",
    "STX/KRW": "스택스", "BLUR/KRW": "블러", "ORDI/KRW": "오르디",
    "TRX/KRW": "트론", "XLM/KRW": "스텔라루멘", "HBAR/KRW": "헤데라",
    "EOS/KRW": "이오스", "XMR/KRW": "모네로", "OCEAN/KRW": "오션프로토콜",
    "ROSE/KRW": "오아시스", "ONE/KRW": "하모니", "ZIL/KRW": "질리카",
    "KAVA/KRW": "카바", "CFX/KRW": "컨플럭스", "ID/KRW": "스페이스ID",
    "ARKM/KRW": "아르카나", "JUP/KRW": "주피터", "DYM/KRW": "다이멘션",
    "STRK/KRW": "스타크넷", "MANTA/KRW": "만타네트워크", "ALT/KRW": "알트레이어",
    "ENA/KRW": "에테나", "W/KRW": "웜홀", "ZK/KRW": "zkSync",
    "ZRO/KRW": "레이어제로", "BLAST/KRW": "블라스트", "IO/KRW": "IO넷",
    "NOT/KRW": "낫코인", "DOGS/KRW": "독스", "HMSTR/KRW": "햄스터컴뱃",
    "CATI/KRW": "캣이즌", "EIGEN/KRW": "아이겐레이어", "SCR/KRW": "스크롤",
    "NEIRO/KRW": "네이로", "TURBO/KRW": "터보", "PNUT/KRW": "피넛더스쿼럴",
    "ACT/KRW": "액트", "MOODENG/KRW": "무뎅", "GOAT/KRW": "고트",
    "ME/KRW": "매직에덴", "MOVE/KRW": "무브먼트", "PENGU/KRW": "푸들리",
    "USUAL/KRW": "유주얼", "VIRTUAL/KRW": "버추얼", "TRUMP/KRW": "트럼프",
    "BERA/KRW": "베라체인", "LAYER/KRW": "레이어", "IP/KRW": "스토리",
    "KAITO/KRW": "카이토", "INIT/KRW": "이니셔", "TON/KRW": "톤코인",
    "MATIC/KRW": "폴리곤", "DYDX/KRW": "dYdX", "GMX/KRW": "GMX",
    "RPL/KRW": "로켓풀", "AGIX/KRW": "싱귤래리티넷", "BAT/KRW": "베이직어텐션",
    "BORA/KRW": "보라", "HUNT/KRW": "헌트", "PUNDIX/KRW": "펀딕스",
    "LSK/KRW": "리스크", "WAXP/KRW": "왁스", "CARV/KRW": "카브",
}


def get_upbit_symbols(limit: int = 300) -> list:
    """업비트 KRW 마켓 거래량 상위 코인 로드"""
    try:
        import ccxt
        upbit = ccxt.upbit({"enableRateLimit": True})

        # load_markets로 전체 KRW 심볼 가져오기
        markets = upbit.load_markets()
        krw = [s for s, m in markets.items()
               if s.endswith("/KRW") and m.get("active", True)]

        if len(krw) >= 10:
            # COIN_NAMES 우선 배치
            priority = [s for s in krw if s in COIN_NAMES]
            rest = [s for s in krw if s not in COIN_NAMES]
            symbols = (priority + rest)[:limit]
            print(f"[심볼 로드] 업비트 KRW {len(symbols)}개")
            return symbols
    except Exception as e:
        print(f"[심볼 로드 실패] {e}")

    print("[심볼 로드] 기본 목록 사용")
    return list(COIN_NAMES.keys())


# 모듈 로드 시 자동으로 업비트 심볼 가져오기
try:
    CRYPTO_SYMBOLS = get_upbit_symbols(300)
    for sym in CRYPTO_SYMBOLS:
        if sym not in COIN_NAMES:
            COIN_NAMES[sym] = sym.replace("/KRW", "")
except Exception:
    CRYPTO_SYMBOLS = list(COIN_NAMES.keys())
