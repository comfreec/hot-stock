"""
코인 심볼 목록 - 바이낸스 USDT 마켓 거래량 상위 자동 로드
"""

# 기본 이름 매핑 (자주 쓰는 코인)
COIN_NAMES = {
    "BTC/USDT": "비트코인", "ETH/USDT": "이더리움", "BNB/USDT": "바이낸스코인",
    "SOL/USDT": "솔라나", "XRP/USDT": "리플", "ADA/USDT": "에이다",
    "AVAX/USDT": "아발란체", "DOGE/USDT": "도지코인", "DOT/USDT": "폴카닷",
    "MATIC/USDT": "폴리곤", "LINK/USDT": "체인링크", "UNI/USDT": "유니스왑",
    "ATOM/USDT": "코스모스", "LTC/USDT": "라이트코인", "ETC/USDT": "이더리움클래식",
    "BCH/USDT": "비트코인캐시", "APT/USDT": "앱토스", "ARB/USDT": "아비트럼",
    "OP/USDT": "옵티미즘", "SUI/USDT": "수이", "INJ/USDT": "인젝티브",
    "TIA/USDT": "셀레스티아", "SEI/USDT": "세이", "JTO/USDT": "지토",
    "PYTH/USDT": "파이스네트워크", "WIF/USDT": "도그위프햇", "BONK/USDT": "봉크",
    "PEPE/USDT": "페페", "FLOKI/USDT": "플로키", "SHIB/USDT": "시바이누",
    "FIL/USDT": "파일코인", "ICP/USDT": "인터넷컴퓨터", "NEAR/USDT": "니어프로토콜",
    "ALGO/USDT": "알고랜드", "VET/USDT": "비체인", "SAND/USDT": "샌드박스",
    "MANA/USDT": "디센트럴랜드", "AXS/USDT": "엑시인피니티", "GALA/USDT": "갈라",
    "ENJ/USDT": "엔진코인", "AAVE/USDT": "에이브", "MKR/USDT": "메이커",
    "SNX/USDT": "신세틱스", "CRV/USDT": "커브", "COMP/USDT": "컴파운드",
    "LDO/USDT": "리도", "RPL/USDT": "로켓풀", "PENDLE/USDT": "펜들",
    "GMX/USDT": "GMX", "DYDX/USDT": "dYdX", "GRT/USDT": "더그래프",
    "RUNE/USDT": "토르체인", "FTM/USDT": "팬텀", "EGLD/USDT": "멀티버스X",
    "THETA/USDT": "세타", "CHZ/USDT": "칠리즈", "FET/USDT": "페치AI",
    "AGIX/USDT": "싱귤래리티넷", "RNDR/USDT": "렌더", "WLD/USDT": "월드코인",
    "STX/USDT": "스택스", "BLUR/USDT": "블러", "ORDI/USDT": "오르디",
    "TRX/USDT": "트론", "XLM/USDT": "스텔라루멘", "HBAR/USDT": "헤데라",
    "EOS/USDT": "이오스", "XMR/USDT": "모네로", "OCEAN/USDT": "오션프로토콜",
    "ROSE/USDT": "오아시스", "ONE/USDT": "하모니", "ZIL/USDT": "질리카",
    "KAVA/USDT": "카바", "BAND/USDT": "밴드프로토콜", "CFX/USDT": "컨플럭스",
    "ID/USDT": "스페이스ID", "CYBER/USDT": "사이버커넥트", "ARKM/USDT": "아르카나",
    "ACE/USDT": "에이스", "JUP/USDT": "주피터", "DYM/USDT": "다이멘션",
    "STRK/USDT": "스타크넷", "MANTA/USDT": "만타네트워크", "ALT/USDT": "알트레이어",
    "PIXEL/USDT": "픽셀", "PORTAL/USDT": "포탈", "AEVO/USDT": "에보",
    "W/USDT": "웜홀", "ENA/USDT": "에테나", "ETHFI/USDT": "이더파이",
    "OMNI/USDT": "옴니네트워크", "REZ/USDT": "레조", "BB/USDT": "부스트비",
    "NOT/USDT": "낫코인", "IO/USDT": "IO넷", "ZK/USDT": "zkSync",
    "LISTA/USDT": "리스타DAO", "ZRO/USDT": "레이어제로", "BLAST/USDT": "블라스트",
    "DOGS/USDT": "독스", "HMSTR/USDT": "햄스터컴뱃", "CATI/USDT": "캣이즌",
    "EIGEN/USDT": "아이겐레이어", "SCR/USDT": "스크롤", "NEIRO/USDT": "네이로",
    "TURBO/USDT": "터보", "PNUT/USDT": "피넛더스쿼럴", "ACT/USDT": "액트",
    "MOODENG/USDT": "무뎅", "GOAT/USDT": "고트", "CHILLGUY/USDT": "칠가이",
    "ME/USDT": "매직에덴", "MOVE/USDT": "무브먼트", "PENGU/USDT": "푸들리",
    "USUAL/USDT": "유주얼", "HYPE/USDT": "하이퍼리퀴드", "VIRTUAL/USDT": "버추얼",
    "AI16Z/USDT": "AI16Z", "AIXBT/USDT": "AIXBT", "FARTCOIN/USDT": "팟코인",
    "TRUMP/USDT": "트럼프", "MELANIA/USDT": "멜라니아", "VINE/USDT": "바인",
    "TST/USDT": "TST", "BERA/USDT": "베라체인", "LAYER/USDT": "레이어",
    "IP/USDT": "스토리", "RED/USDT": "레드", "KAITO/USDT": "카이토",
    "PARTI/USDT": "파티클", "SIGN/USDT": "사인", "NIL/USDT": "닐",
    "INIT/USDT": "이니셔", "KERNEL/USDT": "커널", "HAEDAL/USDT": "헤달",
    "BABY/USDT": "베이비도지", "SIREN/USDT": "사이렌", "PUMP/USDT": "펌프",
    # 추가 주요 코인
    "TON/USDT": "톤코인", "NOT/USDT": "낫코인", "DOGS/USDT": "독스",
    "HMSTR/USDT": "햄스터컴뱃", "CATI/USDT": "캣이즌", "EIGEN/USDT": "아이겐레이어",
    "SCR/USDT": "스크롤", "NEIRO/USDT": "네이로", "TURBO/USDT": "터보",
    "PNUT/USDT": "피넛더스쿼럴", "ACT/USDT": "액트", "MOODENG/USDT": "무뎅",
    "GOAT/USDT": "고트", "CHILLGUY/USDT": "칠가이", "ME/USDT": "매직에덴",
    "MOVE/USDT": "무브먼트", "PENGU/USDT": "푸들리", "IO/USDT": "IO넷",
    "ZK/USDT": "zkSync", "LISTA/USDT": "리스타DAO", "ZRO/USDT": "레이어제로",
    "BLAST/USDT": "블라스트", "W/USDT": "웜홀", "ENA/USDT": "에테나",
    "ETHFI/USDT": "이더파이", "OMNI/USDT": "옴니네트워크", "REZ/USDT": "레조",
    "BB/USDT": "부스트비", "PIXEL/USDT": "픽셀", "PORTAL/USDT": "포탈",
    "AEVO/USDT": "에보", "STRK/USDT": "스타크넷", "MANTA/USDT": "만타네트워크",
    "ALT/USDT": "알트레이어", "DYM/USDT": "다이멘션", "JUP/USDT": "주피터",
    "ACE/USDT": "에이스", "ARKM/USDT": "아르카나", "CYBER/USDT": "사이버커넥트",
    "ID/USDT": "스페이스ID", "CFX/USDT": "컨플럭스", "BAND/USDT": "밴드프로토콜",
    "KAVA/USDT": "카바", "ZIL/USDT": "질리카", "ONE/USDT": "하모니",
    "ROSE/USDT": "오아시스", "OCEAN/USDT": "오션프로토콜", "XMR/USDT": "모네로",
    "EOS/USDT": "이오스", "HBAR/USDT": "헤데라", "XLM/USDT": "스텔라루멘",
    "TRX/USDT": "트론", "ORDI/USDT": "오르디", "BLUR/USDT": "블러",
    "STX/USDT": "스택스", "WLD/USDT": "월드코인", "RNDR/USDT": "렌더",
    "AGIX/USDT": "싱귤래리티넷", "FET/USDT": "페치AI", "CHZ/USDT": "칠리즈",
    "THETA/USDT": "세타", "EGLD/USDT": "멀티버스X", "FTM/USDT": "팬텀",
    "RUNE/USDT": "토르체인", "GRT/USDT": "더그래프", "DYDX/USDT": "dYdX",
    "GMX/USDT": "GMX", "PENDLE/USDT": "펜들", "RPL/USDT": "로켓풀",
    "LDO/USDT": "리도", "COMP/USDT": "컴파운드", "CRV/USDT": "커브",
    "SNX/USDT": "신세틱스", "MKR/USDT": "메이커", "AAVE/USDT": "에이브",
    "ENJ/USDT": "엔진코인", "GALA/USDT": "갈라", "AXS/USDT": "엑시인피니티",
    "MANA/USDT": "디센트럴랜드", "SAND/USDT": "샌드박스", "VET/USDT": "비체인",
    "ALGO/USDT": "알고랜드", "NEAR/USDT": "니어프로토콜", "ICP/USDT": "인터넷컴퓨터",
    "FIL/USDT": "파일코인", "FLOKI/USDT": "플로키", "PEPE/USDT": "페페",
    "BONK/USDT": "봉크", "WIF/USDT": "도그위프햇", "PYTH/USDT": "파이스네트워크",
    "JTO/USDT": "지토", "SEI/USDT": "세이", "TIA/USDT": "셀레스티아",
    "INJ/USDT": "인젝티브", "SUI/USDT": "수이", "OP/USDT": "옵티미즘",
    "ARB/USDT": "아비트럼", "APT/USDT": "앱토스", "BCH/USDT": "비트코인캐시",
    "ETC/USDT": "이더리움클래식", "LTC/USDT": "라이트코인", "ATOM/USDT": "코스모스",
    "UNI/USDT": "유니스왑", "LINK/USDT": "체인링크", "MATIC/USDT": "폴리곤",
    "DOT/USDT": "폴카닷", "DOGE/USDT": "도지코인", "AVAX/USDT": "아발란체",
    "ADA/USDT": "에이다", "XRP/USDT": "리플", "SOL/USDT": "솔라나",
}


def get_top_symbols(limit: int = 500) -> list:
    """바이낸스 USDT 마켓 거래량 상위 코인 자동 로드"""
    try:
        import ccxt
        ex = ccxt.binance({"enableRateLimit": True})

        # 1순위: load_markets (빠르고 안정적, 거래량 정렬 불가)
        try:
            markets = ex.load_markets()
            usdt = []
            for sym, m in markets.items():
                if not sym.endswith("/USDT"):
                    continue
                if m.get("type") != "spot":
                    continue
                base = sym.replace("/USDT", "")
                if any(x in base for x in ["UP", "DOWN", "BULL", "BEAR", "3L", "3S", "2L", "2S"]):
                    continue
                if base in ["USDC", "BUSD", "TUSD", "USDP", "FDUSD", "DAI", "USDD",
                            "USD1", "USDE", "PYUSD", "SUSD", "GUSD", "FRAX", "LUSD"]:
                    continue
                usdt.append(sym)

            if len(usdt) >= 100:
                # COIN_NAMES에 있는 주요 코인 우선 배치
                priority = [s for s in usdt if s in COIN_NAMES]
                rest = [s for s in usdt if s not in COIN_NAMES]
                symbols = (priority + rest)[:limit]
                print(f"[심볼 로드] 바이낸스 마켓 {len(symbols)}개")
                return symbols
        except Exception as e:
            print(f"[심볼 load_markets 실패] {e}")

        # 2순위: fetch_tickers (거래량 정렬 가능하지만 일부 환경에서 제한됨)
        try:
            tickers = ex.fetch_tickers()
            usdt = []
            for sym, t in tickers.items():
                if not sym.endswith("/USDT"):
                    continue
                base = sym.replace("/USDT", "")
                if any(x in base for x in ["UP", "DOWN", "BULL", "BEAR", "3L", "3S", "2L", "2S"]):
                    continue
                if base in ["USDC", "BUSD", "TUSD", "USDP", "FDUSD", "DAI", "USDD",
                            "USD1", "USDE", "PYUSD", "SUSD", "GUSD", "FRAX", "LUSD"]:
                    continue
                quote_vol = float(t.get("quoteVolume") or 0)
                usdt.append((sym, quote_vol))

            usdt.sort(key=lambda x: x[1], reverse=True)
            symbols = [s for s, _ in usdt[:limit]]
            print(f"[심볼 로드] 바이낸스 거래량 상위 {len(symbols)}개")
            return symbols
        except Exception as e:
            print(f"[심볼 fetch_tickers 실패] {e}")

    except Exception as e:
        print(f"[심볼 로드 실패] {e}")

    print("[심볼 로드] 기본 목록 사용")
    return list(COIN_NAMES.keys())


# 폴백용 기본 목록 (API 실패 시) - COIN_NAMES 전체 사용
CRYPTO_SYMBOLS_FALLBACK = list(COIN_NAMES.keys())

# 모듈 로드 시 자동으로 상위 300개 가져오기
try:
    CRYPTO_SYMBOLS = get_top_symbols(500)
    # 이름 매핑에 없는 심볼은 베이스 이름으로 추가
    for sym in CRYPTO_SYMBOLS:
        if sym not in COIN_NAMES:
            COIN_NAMES[sym] = sym.replace("/USDT", "")
except Exception:
    CRYPTO_SYMBOLS = CRYPTO_SYMBOLS_FALLBACK
