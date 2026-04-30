"""
한국투자증권 KIS API 자동매매 모듈
- 스캔 결과 기반 매수 주문 (지정가)
- 장중 모니터링 → 목표가/손절가 도달 시 매도
- KIS_APP_KEY 환경변수 없으면 비활성화
"""
import os
import requests
import json
import time
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# ── 환경변수 ──────────────────────────────────────────────────────
def _cfg():
    return {
        "app_key":    os.environ.get("KIS_APP_KEY", ""),
        "app_secret": os.environ.get("KIS_APP_SECRET", ""),
        "account":    os.environ.get("KIS_ACCOUNT", ""),      # 예: 50123456-01
        "mock":       os.environ.get("KIS_MOCK", "1") == "1", # 1=모의투자, 0=실전
        "max_stocks": int(os.environ.get("KIS_MAX_STOCKS", "3")),   # 최대 동시 보유 종목
        "budget_per": int(os.environ.get("KIS_BUDGET_PER", "300000")), # 종목당 예산 (원)
        "max_days":   int(os.environ.get("KIS_MAX_DAYS", "5")),     # 미체결 최대 유지일
    }

def is_enabled() -> bool:
    return bool(os.environ.get("KIS_APP_KEY"))


# ── API 한도 절약: 잔고 캐시 (5분에 1번만 조회) ─────────────────
_balance_cache = {"data": None, "ts": 0.0}
_BALANCE_TTL = 300  # 5분

def _get_cached_balance(client) -> dict:
    """잔고를 5분 캐시로 조회 (KIS API 한도 절약)"""
    import time as _time
    now = _time.time()
    if _balance_cache["data"] is None or now - _balance_cache["ts"] > _BALANCE_TTL:
        _balance_cache["data"] = client.get_balance()
        _balance_cache["ts"]   = now
    return _balance_cache["data"]

def _invalidate_balance_cache():
    """매수/매도 후 캐시 무효화 (즉시 재조회)"""
    _balance_cache["data"] = None
    _balance_cache["ts"]   = 0.0


def _get_price_yfinance_first(symbol: str, client=None) -> float | None:
    """
    현재가 조회 - yfinance 우선, 실패 시 KIS API
    (KIS API 한도 절약)
    """
    # 1. KIS API 우선 (한국 주식은 KIS가 더 안정적)
    if client:
        _kis_price = client.get_price(symbol)
        if _kis_price:
            return _kis_price
    # 2. yfinance 폴백 (KIS 실패 시)
    try:
        import yfinance as _yf
        _ticker = _yf.Ticker(symbol)
        # 장중: 1분봉
        _d = _ticker.history(period="1d", interval="1m")
        if len(_d) > 0:
            return float(_d["Close"].iloc[-1])
        # 장 마감 후: 일봉
        _d2 = _ticker.history(period="2d")
        if len(_d2) > 0:
            return float(_d2["Close"].iloc[-1])
    except Exception:
        pass
    return None


# ── 한국 공휴일 (5번: 공휴일 처리) ──────────────────────────────
def _build_kr_holidays() -> set:
    year = date.today().year
    fixed = {
        f"{year}-01-01", f"{year}-03-01", f"{year}-05-05",
        f"{year}-06-06", f"{year}-08-15", f"{year}-10-03",
        f"{year}-10-09", f"{year}-12-25",
    }
    extra = os.environ.get("KR_HOLIDAYS_EXTRA", "")  # "2026-01-28,2026-01-29"
    if extra:
        for d in extra.split(","):
            fixed.add(d.strip())
    return fixed

_KR_HOLIDAYS = _build_kr_holidays()


def is_trading_day() -> bool:
    """오늘이 거래일인지 확인 (평일 + 공휴일 아님)"""
    if date.today().weekday() >= 5:
        return False
    return date.today().isoformat() not in _KR_HOLIDAYS


def is_market_open() -> bool:
    """한국 주식 시장 개장 시간 확인 (09:00~15:30 KST, 거래일)"""
    if not is_trading_day():
        return False
    now = datetime.now(KST)
    # KIS 서버 점검 시간 제외 (매일 05:30~06:00 KST)
    if now.hour == 5 and now.minute >= 30:
        return False
    if now.hour == 6 and now.minute == 0:
        return False
    return now.replace(hour=9, minute=0, second=0, microsecond=0) <= now <= now.replace(hour=15, minute=30, second=0, microsecond=0)


def is_order_time() -> bool:
    """매수 주문 가능 시간 (09:05~15:20 KST, 거래일)"""
    if not is_trading_day():
        return False
    now = datetime.now(KST)
    return now.replace(hour=9, minute=5, second=0, microsecond=0) <= now <= now.replace(hour=15, minute=20, second=0, microsecond=0)


def round_to_tick(price: float) -> int:
    """한국 주식 호가 단위로 반올림"""
    if price < 2000:      tick = 1
    elif price < 5000:    tick = 5
    elif price < 20000:   tick = 10
    elif price < 50000:   tick = 50
    elif price < 200000:  tick = 100
    elif price < 500000:  tick = 500
    else:                 tick = 1000
    return int(round(price / tick) * tick)


def _send_admin(message: str):
    """관리자(본인)에게만 텔레그램 DM 전송"""
    try:
        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("KIS_ADMIN_CHAT_ID", "1663019049")
        if not token:
            print("[자동매매] TELEGRAM_TOKEN 없음 - 알림 스킵")
            return
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
        if not resp.ok:
            print(f"[자동매매] 텔레그램 전송 실패: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        print(f"[자동매매] 텔레그램 오류: {e}")


# ── KIS API 클라이언트 ────────────────────────────────────────────
class KISClient:
    REAL_BASE = "https://openapi.koreainvestment.com:9443"
    MOCK_BASE = "https://openapivts.koreainvestment.com:29443"

    def __init__(self):
        cfg = _cfg()
        self.app_key    = cfg["app_key"]
        self.app_secret = cfg["app_secret"]
        self.account    = cfg["account"]
        self.mock       = cfg["mock"]
        self.base       = self.MOCK_BASE if self.mock else self.REAL_BASE
        self._token     = None
        self._token_exp = None

    def _get_token(self) -> str:
        """액세스 토큰 발급 (파일 캐시 + 메모리 캐시) - 재시작 후에도 유지"""
        now = datetime.now(KST)
        # 1. 메모리 캐시 확인
        if self._token and self._token_exp and now < self._token_exp:
            return self._token
        # 2. 파일 캐시 확인 (재시작 후에도 유효한 토큰 재사용)
        mode_tag = "mock" if self.mock else "real"
        token_file = f"/data/.kis_token_{mode_tag}" if os.path.isdir("/data") else f".kis_token_{mode_tag}"
        try:
            import json as _json
            with open(token_file) as f:
                cached = _json.load(f)
            exp_dt = datetime.fromisoformat(cached["expires_at"]).replace(tzinfo=KST)
            if now < exp_dt - timedelta(minutes=30):  # 30분 여유
                self._token = cached["token"]
                self._token_exp = exp_dt
                return self._token
        except Exception:
            pass
        # 3. 새 토큰 발급
        try:
            resp = requests.post(f"{self.base}/oauth2/tokenP", json={
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
            }, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            self._token_exp = now + timedelta(hours=23)
            # 파일에 저장
            try:
                import json as _json
                with open(token_file, "w") as f:
                    _json.dump({"token": self._token, "expires_at": self._token_exp.isoformat()}, f)
            except Exception:
                pass
            return self._token
        except Exception as e:
            mode = "모의투자" if self.mock else "실전투자"
            _send_admin(
                f"⚠️ <b>KIS 토큰 발급 실패</b>\n"
                f"모드: {mode}\n"
                f"오류: {e}\n"
                f"→ 매수/매도 주문이 실행되지 않습니다.\n"
                f"APP KEY/SECRET을 확인하거나 재발급하세요."
            )
            raise

    def _headers(self, tr_id: str, extra: dict = None) -> dict:
        acct = self.account.replace("-", "")
        # 토큰 만료 임박 시 강제 재발급
        now = datetime.now(KST)
        if self._token_exp and now >= self._token_exp - timedelta(minutes=60):
            self._token = None  # 캐시 무효화 → _get_token()에서 재발급
        h = {
            "content-type":  "application/json",
            "authorization": f"Bearer {self._get_token()}",
            "appkey":        self.app_key,
            "appsecret":     self.app_secret,
            "tr_id":         tr_id,
            "custtype":      "P",
        }
        if extra:
            h.update(extra)
        return h

    def get_price(self, symbol: str) -> float | None:
        """현재가 조회"""
        try:
            code = symbol.replace(".KS", "").replace(".KQ", "")
            resp = requests.get(
                f"{self.base}/uapi/domestic-stock/v1/quotations/inquire-price",
                headers=self._headers("FHKST01010100"),
                params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
                timeout=10
            )
            resp.raise_for_status()
            return float(resp.json()["output"]["stck_prpr"])
        except:
            return None

    def get_daily_ohlcv(self, symbol: str, start_date: str, end_date: str) -> "pd.DataFrame | None":
        """
        일봉 OHLCV 조회 (KIS API)
        start_date / end_date: 'YYYYMMDD'
        반환: DataFrame with columns [Open, High, Low, Close, Volume], index=date
        """
        try:
            import pandas as pd
            code = symbol.replace(".KS", "").replace(".KQ", "")
            resp = requests.get(
                f"{self.base}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
                headers=self._headers("FHKST03010100"),
                params={
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD":         code,
                    "FID_INPUT_DATE_1":        start_date,
                    "FID_INPUT_DATE_2":        end_date,
                    "FID_PERIOD_DIV_CODE":     "D",  # D=일봉
                    "FID_ORG_ADJ_PRC":         "0",  # 0=수정주가
                },
                timeout=15
            )
            resp.raise_for_status()
            rows = resp.json().get("output2", [])
            if not rows:
                return None
            records = []
            for r in rows:
                try:
                    records.append({
                        "date":   r["stck_bsop_date"],
                        "Open":   float(r["stck_oprc"]),
                        "High":   float(r["stck_hgpr"]),
                        "Low":    float(r["stck_lwpr"]),
                        "Close":  float(r["stck_clpr"]),
                        "Volume": float(r["acml_vol"]),
                    })
                except:
                    pass
            if not records:
                return None
            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            return df
        except Exception as e:
            print(f"[KIS] 일봉 조회 오류 {symbol}: {e}")
            return None

    def get_balance(self) -> dict:
        """잔고 조회 - 보유 종목 + 예수금"""
        try:
            acct_no = self.account.split("-")[0]
            acct_cd = self.account.split("-")[1] if "-" in self.account else "01"
            tr_id = "VTTC8434R" if self.mock else "TTTC8434R"
            resp = requests.get(
                f"{self.base}/uapi/domestic-stock/v1/trading/inquire-balance",
                headers=self._headers(tr_id),
                params={
                    "CANO": acct_no, "ACNT_PRDT_CD": acct_cd,
                    "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02",
                    "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
                    "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "01", "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""
                },
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            holdings = {}
            for item in data.get("output1", []):
                code = item.get("pdno", "")
                qty  = int(item.get("hldg_qty", 0))
                if qty > 0:
                    holdings[code] = {
                        "qty":        qty,
                        "avg_price":  float(item.get("pchs_avg_pric", 0)),
                        "eval_price": float(item.get("prpr", 0)),
                    }
            cash = float(data.get("output2", [{}])[0].get("dnca_tot_amt", 0))
            return {"holdings": holdings, "cash": cash}
        except Exception as e:
            print(f"[KIS] 잔고 조회 오류: {e}")
            return {"holdings": {}, "cash": 0}

    def buy_order(self, symbol: str, price: int, qty: int, market: bool = False) -> dict:
        """매수 주문 (지정가 or 시장가)"""
        # ── 안전 검증 ──────────────────────────────────────────────
        if qty <= 0:
            return {"success": False, "error": f"수량 오류: qty={qty}"}
        price = round_to_tick(price)  # 호가 단위 보정
        code  = symbol.replace(".KS", "").replace(".KQ", "")
        acct_no = self.account.split("-")[0]
        acct_cd = self.account.split("-")[1] if "-" in self.account else "01"
        tr_id = "VTTC0802U" if self.mock else "TTTC0802U"
        ord_dvsn  = "01" if market else "00"
        ord_price = "0"  if market else str(price)
        for attempt in range(2):  # 토큰 만료 시 1회 재시도
            try:
                resp = requests.post(
                    f"{self.base}/uapi/domestic-stock/v1/trading/order-cash",
                    headers=self._headers(tr_id),
                    json={
                        "CANO": acct_no, "ACNT_PRDT_CD": acct_cd,
                        "PDNO": code, "ORD_DVSN": ord_dvsn,
                        "ORD_QTY": str(qty), "ORD_UNPR": ord_price,
                    },
                    timeout=10
                )
                resp.raise_for_status()
                result = resp.json()
                # 토큰 만료 오류 감지
                if result.get("rt_cd") == "1" and "token" in result.get("msg1", "").lower():
                    if attempt == 0:
                        self._token = None  # 토큰 무효화 후 재시도
                        continue
                order_no = result.get("output", {}).get("ODNO", "")
                kind = "시장가" if market else f"@{price:,}원"
                print(f"[KIS] 매수 주문 {code} {qty}주 {kind} → 주문번호 {order_no}")
                return {"success": True, "order_no": order_no}
            except requests.exceptions.Timeout:
                # 4번: 타임아웃 - 주문이 실제로 들어갔는지 불명확
                if attempt == 0:
                    print(f"[KIS] 매수 주문 타임아웃 {code} - 잔고 확인 후 재시도")
                    time.sleep(3)
                    try:
                        bal = self.get_balance()
                        if code in bal.get("holdings", {}):
                            print(f"[KIS] {code} 타임아웃 후 잔고 확인 → 이미 체결됨")
                            return {"success": True, "order_no": "", "note": "timeout_but_filled"}
                    except Exception:
                        pass
                    self._token = None
                    continue
                _send_admin(
                    f"⚠️ <b>매수 주문 타임아웃</b>\n"
                    f"{code} {qty}주 주문 응답 없음\n"
                    f"실제 체결 여부 수동 확인 필요"
                )
                return {"success": False, "error": "timeout"}
            except Exception as e:
                if attempt == 0:
                    self._token = None
                    time.sleep(1)
                    continue
                print(f"[KIS] 매수 주문 오류 {code}: {e}")
                return {"success": False, "error": str(e)}

    def sell_order(self, symbol: str, price: int, qty: int, market: bool = False) -> dict:
        """매도 주문 (지정가 or 시장가)"""
        # ── 안전 검증 ──────────────────────────────────────────────
        if qty <= 0:
            return {"success": False, "error": f"수량 오류: qty={qty}"}
        price = round_to_tick(price)  # 호가 단위 보정
        code  = symbol.replace(".KS", "").replace(".KQ", "")
        acct_no = self.account.split("-")[0]
        acct_cd = self.account.split("-")[1] if "-" in self.account else "01"
        tr_id = "VTTC0801U" if self.mock else "TTTC0801U"
        ord_dvsn = "01" if market else "00"
        ord_price = "0" if market else str(price)
        for attempt in range(2):  # 토큰 만료 시 1회 재시도
            try:
                resp = requests.post(
                    f"{self.base}/uapi/domestic-stock/v1/trading/order-cash",
                    headers=self._headers(tr_id),
                    json={
                        "CANO": acct_no, "ACNT_PRDT_CD": acct_cd,
                        "PDNO": code, "ORD_DVSN": ord_dvsn,
                        "ORD_QTY": str(qty), "ORD_UNPR": ord_price,
                    },
                    timeout=10
                )
                resp.raise_for_status()
                result = resp.json()
                if result.get("rt_cd") == "1" and "token" in result.get("msg1", "").lower():
                    if attempt == 0:
                        self._token = None
                        continue
                order_no = result.get("output", {}).get("ODNO", "")
                kind = "시장가" if market else f"@{price:,}원"
                print(f"[KIS] 매도 주문 {code} {qty}주 {kind} → 주문번호 {order_no}")
                return {"success": True, "order_no": order_no}
            except requests.exceptions.Timeout:
                # 4번: 타임아웃 - 매도는 특히 위험하므로 잔고 확인
                if attempt == 0:
                    print(f"[KIS] 매도 주문 타임아웃 {code} - 잔고 확인")
                    time.sleep(3)
                    try:
                        bal = self.get_balance()
                        remaining = bal.get("holdings", {}).get(code, {}).get("qty", 0)
                        if remaining == 0:
                            print(f"[KIS] {code} 타임아웃 후 잔고 0 → 매도 체결됨")
                            return {"success": True, "order_no": "", "note": "timeout_but_sold"}
                    except Exception:
                        pass
                    self._token = None
                    continue
                _send_admin(
                    f"🚨 <b>매도 주문 타임아웃</b>\n"
                    f"{code} {qty}주 매도 응답 없음\n"
                    f"⚠️ 실제 체결 여부 즉시 수동 확인 필요"
                )
                return {"success": False, "error": "timeout"}
            except Exception as e:
                if attempt == 0:
                    self._token = None
                    time.sleep(1)
                    continue
                print(f"[KIS] 매도 주문 오류 {code}: {e}")
                return {"success": False, "error": str(e)}

    def get_order_status(self, order_no: str, symbol: str) -> str:
        """주문 체결 상태 조회 - filled / partial / pending / cancelled"""
        try:
            code    = symbol.replace(".KS", "").replace(".KQ", "")
            acct_no = self.account.split("-")[0]
            acct_cd = self.account.split("-")[1] if "-" in self.account else "01"
            tr_id   = "VTTC8001R" if self.mock else "TTTC8001R"
            resp = requests.get(
                f"{self.base}/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
                headers=self._headers(tr_id),
                params={
                    "CANO": acct_no, "ACNT_PRDT_CD": acct_cd,
                    "INQR_STRT_DT": date.today().strftime("%Y%m%d"),
                    "INQR_END_DT":  date.today().strftime("%Y%m%d"),
                    "SLL_BUY_DVSN_CD": "02",  # 매수
                    "INQR_DVSN": "00", "PDNO": code,
                    "CCLD_DVSN": "00", "ORD_GNO_BRNO": "", "ODNO": order_no,
                    "INQR_DVSN_3": "00", "INQR_DVSN_1": "",
                    "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""
                },
                timeout=10
            )
            resp.raise_for_status()
            rows = resp.json().get("output1", [])
            if not rows:
                return "pending"
            row = rows[0]
            tot_qty  = int(row.get("ord_qty", 0))
            fill_qty = int(row.get("tot_ccld_qty", 0))
            if fill_qty >= tot_qty:
                return "filled"
            elif fill_qty > 0:
                return "partial"
            else:
                return "pending"
        except Exception as e:
            print(f"[KIS] 체결 조회 오류: {e}")
            return "unknown"

    def get_filled_price(self, order_no: str, symbol: str) -> float:
        """실제 체결 평균가 조회 - 체결된 경우 평균 체결가 반환, 없으면 0"""
        try:
            code    = symbol.replace(".KS", "").replace(".KQ", "")
            acct_no = self.account.split("-")[0]
            acct_cd = self.account.split("-")[1] if "-" in self.account else "01"
            tr_id   = "VTTC8001R" if self.mock else "TTTC8001R"
            resp = requests.get(
                f"{self.base}/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
                headers=self._headers(tr_id),
                params={
                    "CANO": acct_no, "ACNT_PRDT_CD": acct_cd,
                    "INQR_STRT_DT": date.today().strftime("%Y%m%d"),
                    "INQR_END_DT":  date.today().strftime("%Y%m%d"),
                    "SLL_BUY_DVSN_CD": "02",
                    "INQR_DVSN": "00", "PDNO": code,
                    "CCLD_DVSN": "00", "ORD_GNO_BRNO": "", "ODNO": order_no,
                    "INQR_DVSN_3": "00", "INQR_DVSN_1": "",
                    "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""
                },
                timeout=10
            )
            resp.raise_for_status()
            rows = resp.json().get("output1", [])
            if not rows:
                return 0.0
            row = rows[0]
            # avg_prvs: 체결 평균가, tot_ccld_amt/tot_ccld_qty로 계산
            fill_qty = int(row.get("tot_ccld_qty", 0))
            fill_amt = float(row.get("tot_ccld_amt", 0))
            if fill_qty > 0 and fill_amt > 0:
                return round(fill_amt / fill_qty, 2)
            # 단일 체결가
            ccld_pric = float(row.get("avg_prvs", 0) or row.get("ccld_pric", 0))
            return ccld_pric
        except Exception as e:
            print(f"[KIS] 체결가 조회 오류: {e}")
            return 0.0

    def cancel_order(self, order_no: str, symbol: str, qty: int) -> bool:
        code  = symbol.replace(".KS", "").replace(".KQ", "")
        acct_no = self.account.split("-")[0]
        acct_cd = self.account.split("-")[1] if "-" in self.account else "01"
        tr_id = "VTTC0803U" if self.mock else "TTTC0803U"
        try:
            resp = requests.post(
                f"{self.base}/uapi/domestic-stock/v1/trading/order-rvsecncl",
                headers=self._headers(tr_id),
                json={
                    "CANO": acct_no, "ACNT_PRDT_CD": acct_cd,
                    "KRX_FWDG_ORD_ORGNO": "", "ORGN_ODNO": order_no,
                    "ORD_DVSN": "00", "RVSE_CNCL_DVSN_CD": "02",  # 02=취소
                    "ORD_QTY": str(qty), "ORD_UNPR": "0", "QTY_ALL_ORD_YN": "Y",
                },
                timeout=10
            )
            return resp.ok
        except:
            return False


# ── 주문 관리 DB ──────────────────────────────────────────────────
def _get_trade_conn():
    """자동매매 전용 DB (주식 scan_cache.db와 같은 /data 볼륨)"""
    import sqlite3
    import os as _os
    db_path = _os.environ.get("DB_PATH",
        "/data/scan_cache.db" if _os.path.isdir("/data") else "scan_cache.db"
    )
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=10000")  # DB 락 시 10초 대기
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_date  TEXT NOT NULL,
            symbol      TEXT NOT NULL,
            name        TEXT NOT NULL,
            entry_price INTEGER NOT NULL,
            target_price INTEGER NOT NULL,
            stop_price  INTEGER NOT NULL,
            qty         INTEGER NOT NULL,
            order_no    TEXT,
            status      TEXT DEFAULT 'pending',
            -- pending / active / hit_target / hit_stop / expired / cancelled
            exit_price  INTEGER,
            exit_date   TEXT,
            return_pct  REAL,
            created_at  TEXT NOT NULL,
            -- 분할매수 관련
            split_step  INTEGER DEFAULT 1,   -- 현재 몇 차 매수 (1/2/3)
            split_qty   INTEGER DEFAULT 0,   -- 총 체결 수량
            avg_price   REAL DEFAULT 0,      -- 평균 매수가
            base_price  INTEGER DEFAULT 0,   -- 1차 매수가 (2/3차 트리거 기준)
            step2_price REAL DEFAULT 0,      -- 2차 실제 체결가
            step2_qty   INTEGER DEFAULT 0,   -- 2차 체결 수량
            step3_price REAL DEFAULT 0,      -- 3차 실제 체결가
            step3_qty   INTEGER DEFAULT 0    -- 3차 체결 수량
        )
    """)
    conn.commit()
    # 기존 DB에 컬럼 없으면 추가 (마이그레이션)
    existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(trade_orders)").fetchall()]
    for col, typ, default in [
        ("split_step", "INTEGER", "1"), ("split_qty", "INTEGER", "0"),
        ("avg_price",  "REAL",    "0"), ("base_price","INTEGER", "0"),
        ("trigger2",   "INTEGER", "0"), ("trigger3",  "INTEGER", "0"),
        ("step2_price","REAL",    "0"), ("step2_qty", "INTEGER", "0"),
        ("step3_price","REAL",    "0"), ("step3_qty", "INTEGER", "0"),
        ("sell_order_no", "TEXT", "''"),  # 매도 주문번호 (미체결 확인용)
        ("sell_order_ts", "TEXT", "''"),  # 매도 주문 시각
    ]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE trade_orders ADD COLUMN {col} {typ} DEFAULT {default}")
    conn.commit()
    return conn


def _get_pending_orders() -> list:
    conn = _get_trade_conn()
    rows = conn.execute("""
        SELECT id, alert_date, symbol, name, entry_price, target_price, stop_price,
               qty, order_no, status, split_step, split_qty, avg_price, base_price,
               trigger2, trigger3, step2_price, step2_qty, step3_price, step3_qty,
               sell_order_no, sell_order_ts
        FROM trade_orders WHERE status IN ('pending', 'active')
        ORDER BY alert_date ASC
    """).fetchall()
    conn.close()
    keys = ["id","alert_date","symbol","name","entry_price","target_price","stop_price",
            "qty","order_no","status","split_step","split_qty","avg_price","base_price",
            "trigger2","trigger3","step2_price","step2_qty","step3_price","step3_qty",
            "sell_order_no","sell_order_ts"]
    return [dict(zip(keys, r)) for r in rows]


def _update_order(order_id: int, **kwargs):
    conn = _get_trade_conn()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [order_id]
    conn.execute(f"UPDATE trade_orders SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def _get_ma240(symbol: str) -> float | None:
    """yfinance로 240일선 현재값 조회"""
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).history(period="2y").dropna(subset=["Close"])
        if len(df) < 240:
            return None
        return float(df["Close"].rolling(240).mean().iloc[-1])
    except:
        return None


def _calc_split_triggers(base_price: float, ma240: float) -> tuple:
    """
    분할매수 트리거 계산
    - 2차 매수가: 1차 매수가와 240일선의 중간값
    - 3차 매수가: 1차 매수 시점의 240일선 가격 (이후 240선 변동 무관하게 고정)
    base_price: 1차 매수가
    ma240: 1차 매수 시점의 240일선 가격 (고정값으로 저장됨)
    returns: (trigger2, trigger3)
    """
    if ma240 >= base_price:
        # 240선이 매수가보다 높으면 기존 방식(-2%, -4%) 사용
        return round_to_tick(base_price * 0.98), round_to_tick(base_price * 0.96)
    trigger2 = (base_price + ma240) / 2  # 1차 매수가와 240선의 중간
    trigger3 = ma240                      # 240일선 가격 (1차 매수 시점 고정)
    return round_to_tick(trigger2), round_to_tick(trigger3)


def _save_order(alert_date, symbol, name, entry_price, target_price, stop_price, qty, order_no,
                split_step=1, base_price=0, trigger2=0, trigger3=0):
    conn = _get_trade_conn()
    existing = conn.execute(
        "SELECT id FROM trade_orders WHERE symbol=? AND status IN ('pending','active')", (symbol,)
    ).fetchone()
    if existing:
        conn.close()
        return
    # trigger2/trigger3 컬럼 마이그레이션
    existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(trade_orders)").fetchall()]
    for col in ["trigger2", "trigger3"]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE trade_orders ADD COLUMN {col} INTEGER DEFAULT 0")
    conn.commit()
    conn.execute("""
        INSERT INTO trade_orders
        (alert_date, symbol, name, entry_price, target_price, stop_price, qty, order_no, status,
         split_step, split_qty, avg_price, base_price, trigger2, trigger3, created_at)
        VALUES (?,?,?,?,?,?,?,?,'pending',?,?,?,?,?,?,?)
    """, (alert_date, symbol, name, entry_price, target_price, stop_price, qty, order_no,
          split_step, qty, float(entry_price), base_price or entry_price,
          int(trigger2), int(trigger3), datetime.now().isoformat()))
    conn.commit()
    conn.close()


# ── 핵심 함수 ─────────────────────────────────────────────────────
def place_orders(results: list):
    """
    스캔 결과 기반 매수 주문 배치
    - 이미 보유/대기 중인 종목 스킵
    - 예산 내에서 수량 계산
    - 지정가 매수 주문
    """
    if not is_enabled():
        return

    # ── 장 시간 체크 ──────────────────────────────────────────────
    if not is_order_time():
        now = datetime.now(KST)
        print(f"[자동매매] 주문 가능 시간 외 ({now.strftime('%H:%M')}) - 매수 주문 스킵")
        return

    cfg    = _cfg()
    client = KISClient()
    today  = date.today().isoformat()

    # 현재 보유 종목 수 확인
    pending = _get_pending_orders()
    active_count = len([o for o in pending if o["status"] in ("pending", "active")])
    if active_count >= cfg["max_stocks"]:
        print(f"[자동매매] 최대 보유 종목 수 도달 ({active_count}/{cfg['max_stocks']}) - 신규 주문 스킵")
        return

    balance = client.get_balance()
    cash    = balance.get("cash", 0)
    holdings = balance.get("holdings", {})

    # 총 투자금 한도 체크 (예수금 기준)
    total_budget = cfg["max_stocks"] * cfg["budget_per"]
    if cash < cfg["budget_per"]:
        print(f"[자동매매] 예수금 부족 (₩{cash:,.0f}) - 주문 중단")
        _send_admin(
            f"⚠️ <b>예수금 부족 - 주문 중단</b>\n"
            f"현재 예수금: ₩{cash:,.0f}\n"
            f"종목당 필요 예산: ₩{cfg['budget_per']:,.0f}\n"
            f"→ 신규 매수 주문이 실행되지 않았습니다."
        )
        return

    slots = cfg["max_stocks"] - active_count
    budget = cfg["budget_per"]
    # 실제 사용 가능 예산 = min(종목당 예산, 예수금/남은슬롯)
    if slots > 0:
        budget = min(budget, int(cash / slots))

    ordered = 0
    for r in results:
        if ordered >= slots:
            break

        symbol = r.get("symbol", "")
        name   = r.get("name", symbol)
        code   = symbol.replace(".KS", "").replace(".KQ", "")

        # 이미 보유 중이면 스킵
        if code in holdings:
            print(f"[자동매매] {name} 이미 보유 중 - 스킵")
            continue

        # 이미 대기/매수중 주문 있으면 스킵 (pending + active 모두 체크)
        if any(o["symbol"] == symbol for o in pending):
            print(f"[자동매매] {name} 이미 주문 진행 중 (pending/active) - 스킵")
            continue

        # 최근 3일 내 손절/목표가 도달 종목 재매수 방지 (6번)
        if _is_recently_sold(symbol, days=3):
            print(f"[자동매매] {name} 최근 3일 내 매도된 종목 - 재매수 방지 스킵")
            continue

        # 가격 레벨 - alert_history에서 조회 (전날 스캔 기준)
        from cache_db import _get_conn as _db_conn
        lv = {}
        try:
            _conn = _db_conn()
            _row = _conn.execute(
                "SELECT entry_price, target_price, stop_price FROM alert_history "
                "WHERE symbol=? ORDER BY id DESC LIMIT 1",
                (symbol,)
            ).fetchone()
            if _row:
                lv = {"entry": _row[0], "target": _row[1], "stop": _row[2]}
        except Exception:
            pass

        if not lv.get("entry") or not lv.get("target") or not lv.get("stop"):
            print(f"[자동매매] {name} 가격 레벨 없음 - 스킵")
            continue

        entry  = int(lv["entry"])
        target = int(lv["target"])

        # ── 자동매매 전용 손절가: telegram_alert._calc_levels_core와 동일 로직 ──
        try:
            import yfinance as _yf
            _df = _yf.Ticker(symbol).history(period="5y", auto_adjust=False).dropna(subset=["Close","Low"])
            _close = _df["Close"]
            _low   = _df["Low"]
            _n     = len(_close)
            # RSI(20) 계산
            _d = _close.diff()
            _gain = _d.where(_d > 0, 0.0).ewm(alpha=1/20, min_periods=20, adjust=False).mean()
            _loss = (-_d.where(_d < 0, 0.0)).ewm(alpha=1/20, min_periods=20, adjust=False).mean()
            _rsi  = (100 - 100 / (1 + _gain / _loss.replace(0, float("nan")))).fillna(50)
            _rsi_vals = _rsi.values
            # RSI 30 돌파 시점 중 가장 최근 것
            _oversold_exit = None
            for _i in range(1, _n):
                if _rsi_vals[_i-1] <= 30 and _rsi_vals[_i] > 30:
                    _oversold_exit = _i
            if _oversold_exit is not None:
                _lb = max(0, _oversold_exit - 5)
                stop = int(float(_low.iloc[_lb:_oversold_exit].min()))
                print(f"[자동매매] {name} 손절가 RSI바닥 저점 적용: ₩{stop:,}")
            else:
                stop = int(lv["stop"])  # RSI 패턴 없으면 스캔 손절가 사용
        except Exception as _e:
            print(f"[자동매매] {name} RSI 손절가 계산 실패 ({_e}) → 스캔 손절가 사용")
            stop = int(lv["stop"])

        if cash < budget * 0.8:
            print(f"[자동매매] 예수금 부족 ({cash:,.0f}원) - 주문 중단")
            _send_admin(f"⚠️ <b>예수금 부족</b>\n현재 예수금: ₩{cash:,.0f}\n→ 추가 매수 중단")
            break

        qty = max(1, int(budget / entry) // 3)  # 1/3 수량으로 1차 매수
        if qty == 0:
            qty = 1
        actual_cost = entry * qty

        if actual_cost > cash:
            print(f"[자동매매] {name} 예수금 부족 - 스킵")
            continue

        result = client.buy_order(symbol, entry, qty, market=True)  # 1차는 시장가
        if result["success"]:
            order_no = result.get("order_no", "")
            # 240선 조회해서 분할매수 트리거 계산
            ma240 = _get_ma240(symbol)
            t2, t3 = _calc_split_triggers(entry, ma240) if ma240 else (int(entry * 0.98), int(entry * 0.96))
            _save_order(today, symbol, name, entry, target, stop, qty, order_no,
                       split_step=1, base_price=entry, trigger2=t2, trigger3=t3)

            # 시장가 주문 → 잠시 후 실제 체결가 조회 (2가지 방법 병행)
            time.sleep(2)
            actual_entry = entry  # 기본값

            # 방법1: 체결 내역 API
            filled_price = client.get_filled_price(order_no, symbol) if order_no else 0
            if filled_price > 0:
                actual_entry = int(filled_price)
            else:
                # 방법2: 잔고 조회에서 평균매수가 (더 신뢰도 높음)
                try:
                    balance = client.get_balance()
                    code = symbol.replace(".KS", "").replace(".KQ", "")
                    holding = balance.get("holdings", {}).get(code)
                    if holding and holding.get("avg_price", 0) > 0:
                        actual_entry = int(holding["avg_price"])
                except:
                    pass

            # 실제 체결가로 업데이트 후 active 전환
            conn = _get_trade_conn()
            conn.execute(
                "UPDATE trade_orders SET status='active', entry_price=?, avg_price=?, base_price=? WHERE symbol=? AND alert_date=?",
                (actual_entry, float(actual_entry), actual_entry, symbol, today)
            )
            conn.commit()
            conn.close()

            # 실제 체결가 기준으로 분할매수 트리거 + 손절가 재계산
            if actual_entry != entry:
                t2, t3 = _calc_split_triggers(actual_entry, ma240) if ma240 else (int(actual_entry * 0.98), int(actual_entry * 0.96))
                # 손절가도 실제 체결가 기준으로 재계산 (RSI 저점은 동일, stop 그대로 유효)
                # stop은 RSI 바닥 절대가격이라 entry 변동과 무관하게 유지
                conn2 = _get_trade_conn()
                conn2.execute(
                    "UPDATE trade_orders SET trigger2=?, trigger3=? WHERE symbol=? AND alert_date=?",
                    (t2, t3, symbol, today)
                )
                conn2.commit()
                conn2.close()

            cash -= actual_entry * qty
            ordered += 1

            # 3번: 매수 직후 손절가 도달 여부 즉시 확인
            cur_price = client.get_price(symbol)
            if cur_price and cur_price <= stop:
                print(f"[자동매매] {name} 매수 직후 손절가 도달 감지 → 즉시 매도")
                sell_result = client.sell_order(symbol, stop, qty, market=True)
                if sell_result["success"]:
                    ret = (cur_price - actual_entry) / actual_entry * 100
                    conn3 = _get_trade_conn()
                    conn3.execute(
                        "UPDATE trade_orders SET status='hit_stop', exit_price=?, exit_date=?, return_pct=? WHERE symbol=? AND alert_date=?",
                        (int(cur_price), today, round(ret, 2), symbol, today)
                    )
                    conn3.commit()
                    conn3.close()
                    _send_admin(
                        f"🛑 <b>매수 직후 손절</b>\n"
                        f"<b>{name}</b>\n"
                        f"매수 ₩{actual_entry:,} → 즉시 손절 ₩{cur_price:,.0f}\n"
                        f"손실 <b>{ret:.1f}%</b>"
                    )
                    cash += cur_price * qty  # 예수금 복구
                    ordered -= 1
                    continue

            # 텔레그램 알림 (실제 체결가 기준)
            try:
                from telegram_alert import send_telegram
                mock_tag = "[모의] " if cfg["mock"] else ""
                t2_pct = (t2 / actual_entry - 1) * 100 if actual_entry else 0
                t3_pct = (t3 / actual_entry - 1) * 100 if actual_entry else 0
                _send_admin(
                    f"🤖 {mock_tag}<b>자동매수 체결</b>\n"
                    f"<b>{name}</b> ({symbol})\n"
                    f"📍 1차 매수: ₩{actual_entry:,}  ×  {qty}주\n"
                    f"🎯 목표가: ₩{target:,}\n"
                    f"🛑 손절가: ₩{stop:,}\n"
                    f"💰 체결금액: ₩{actual_entry * qty:,}\n"
                    f"\n📋 <b>분할매수 미리보기</b>\n"
                    f"  2차: ₩{t2:,} ({t2_pct:.1f}%)\n"
                    f"  3차: ₩{t3:,} ({t3_pct:.1f}%)"
                )
                _invalidate_balance_cache()  # 매수 후 잔고 캐시 무효화
            except:
                pass
        else:
            print(f"[자동매매] {name} 주문 실패: {result.get('error')}")


def morning_reorder():
    """
    매일 09:05 실행 - 미체결 pending 주문 재주문
    - 전날 미체결이면 취소 후 오늘 다시 지정가 주문
    - max_days 초과 시 포기
    """
    if not is_enabled():
        return

    # ── 재시작 중복 실행 방지 (오늘 이미 실행됐으면 스킵) ─────────
    import os as _os
    lock_file = "/data/.morning_reorder_lock" if _os.path.isdir("/data") else ".morning_reorder_lock"
    today_str = date.today().isoformat()
    try:
        if _os.path.exists(lock_file):
            with open(lock_file) as f:
                last_run = f.read().strip()
            if last_run == today_str:
                print(f"[자동매매] morning_reorder 오늘 이미 실행됨 ({today_str}) - 스킵")
                return
    except Exception:
        pass
    try:
        with open(lock_file, "w") as f:
            f.write(today_str)
    except Exception:
        pass

    cfg    = _cfg()
    client = KISClient()
    today  = date.today().isoformat()
    pending = _get_pending_orders()

    for order in pending:
        if order["status"] != "pending":
            continue

        alert_dt = date.fromisoformat(order["alert_date"])
        days_elapsed = (date.today() - alert_dt).days

        if days_elapsed >= cfg["max_days"]:
            # 만료 처리 - 거래일 기준
            trading_days = 0
            cur_day = alert_dt
            while cur_day < date.today():
                cur_day += timedelta(days=1)
                if cur_day.weekday() < 5:
                    trading_days += 1
            if trading_days < cfg["max_days"]:
                continue
            # 만료 처리
            if order.get("order_no"):
                client.cancel_order(order["order_no"], order["symbol"], order["qty"])
            _update_order(order["id"], status="expired", exit_date=today)
            print(f"[자동매매] {order['name']} {cfg['max_days']}일 경과 → 만료")
            try:
                from telegram_alert import send_telegram
                _send_admin(f"⏰ <b>자동매매 만료</b>\n<b>{order['name']}</b> - {cfg['max_days']}일 미체결로 주문 취소")
            except:
                pass
            continue

        if days_elapsed == 0:
            # 오늘 처음 주문한 것 - 체결 여부 확인
            if order.get("order_no"):
                status = client.get_order_status(order["order_no"], order["symbol"])
                if status == "filled":
                    # 실제 체결가 조회 (2가지 방법)
                    filled_price = client.get_filled_price(order["order_no"], order["symbol"])
                    actual_price = int(filled_price) if filled_price > 0 else 0
                    if actual_price == 0:
                        try:
                            bal = client.get_balance()
                            code = order["symbol"].replace(".KS","").replace(".KQ","")
                            h = bal.get("holdings",{}).get(code)
                            if h and h.get("avg_price",0) > 0:
                                actual_price = int(h["avg_price"])
                        except:
                            pass
                    if actual_price == 0:
                        actual_price = order["entry_price"]
                    # 트리거 재계산
                    ma240 = _get_ma240(order["symbol"])
                    t2, t3 = _calc_split_triggers(actual_price, ma240) if ma240 else (int(actual_price*0.98), int(actual_price*0.96))
                    _update_order(order["id"], status="active",
                                  entry_price=actual_price,
                                  avg_price=float(actual_price),
                                  base_price=actual_price,
                                  trigger2=t2, trigger3=t3)
                    print(f"[자동매매] {order['name']} 체결 확인 → active (체결가 ₩{actual_price:,.0f})")
                    _send_admin(f"✅ <b>매수 체결 확인</b>\n<b>{order['name']}</b> ₩{actual_price:,.0f} × {order['qty']}주")
                elif status == "partial":
                    # 부분 체결 → 실제 체결 수량으로 DB 업데이트
                    try:
                        bal = client.get_balance()
                        code = order["symbol"].replace(".KS","").replace(".KQ","")
                        h = bal.get("holdings",{}).get(code)
                        if h and h.get("qty", 0) > 0:
                            actual_qty = h["qty"]
                            actual_price = int(h.get("avg_price", order["entry_price"]))
                            _update_order(order["id"],
                                status="active", qty=actual_qty,
                                entry_price=actual_price, avg_price=float(actual_price),
                                base_price=actual_price
                            )
                            _send_admin(
                                f"⚠️ <b>부분 체결</b>\n"
                                f"<b>{order['name']}</b>\n"
                                f"주문 {order['qty']}주 → 체결 {actual_qty}주\n"
                                f"체결가 ₩{actual_price:,.0f}"
                            )
                            print(f"[자동매매] {order['name']} 부분 체결 {actual_qty}주 → active")
                    except Exception as _e:
                        print(f"[자동매매] {order['name']} 부분 체결 처리 오류: {_e}")
                elif status in ("cancelled", "expired"):
                    _update_order(order["id"], status="expired", exit_date=today)
                    _send_admin(f"⚠️ <b>주문 취소됨</b>\n<b>{order['name']}</b> 주문이 취소/만료됨")
            continue

        # 전날 주문 체결 여부 먼저 확인
        if order.get("order_no"):
            status = client.get_order_status(order["order_no"], order["symbol"])
            if status == "filled":
                filled_price = client.get_filled_price(order["order_no"], order["symbol"])
                actual_price = int(filled_price) if filled_price > 0 else 0
                if actual_price == 0:
                    try:
                        bal = client.get_balance()
                        code = order["symbol"].replace(".KS","").replace(".KQ","")
                        h = bal.get("holdings",{}).get(code)
                        if h and h.get("avg_price",0) > 0:
                            actual_price = int(h["avg_price"])
                    except:
                        pass
                if actual_price == 0:
                    actual_price = order["entry_price"]
                ma240 = _get_ma240(order["symbol"])
                t2, t3 = _calc_split_triggers(actual_price, ma240) if ma240 else (int(actual_price*0.98), int(actual_price*0.96))
                _update_order(order["id"], status="active",
                              entry_price=actual_price,
                              avg_price=float(actual_price),
                              base_price=actual_price,
                              trigger2=t2, trigger3=t3)
                print(f"[자동매매] {order['name']} 전날 체결 확인 → active (체결가 ₩{actual_price:,.0f})")
                _send_admin(f"✅ <b>매수 체결 확인</b>\n<b>{order['name']}</b> ₩{actual_price:,.0f} × {order['qty']}주")
                continue
            # 미체결이면 취소 후 재주문
            client.cancel_order(order["order_no"], order["symbol"], order["qty"])

        result = client.buy_order(order["symbol"], order["entry_price"], order["qty"], market=True)
        if result["success"]:
            new_order_no = result.get("order_no", "")
            _update_order(order["id"],
                alert_date=today,
                order_no=new_order_no,
            )
            # 재주문도 시장가 → 잠시 후 실제 체결가 조회 (2가지 방법 병행)
            time.sleep(2)
            actual_price = order["entry_price"]  # 기본값

            filled_price = client.get_filled_price(new_order_no, order["symbol"]) if new_order_no else 0
            if filled_price > 0:
                actual_price = int(filled_price)
            else:
                # 잔고 조회에서 평균매수가 (더 신뢰도 높음)
                try:
                    balance = client.get_balance()
                    code = order["symbol"].replace(".KS", "").replace(".KQ", "")
                    holding = balance.get("holdings", {}).get(code)
                    if holding and holding.get("avg_price", 0) > 0:
                        actual_price = int(holding["avg_price"])
                except:
                    pass

            if actual_price != order["entry_price"]:
                ma240 = _get_ma240(order["symbol"])
                t2, t3 = _calc_split_triggers(actual_price, ma240) if ma240 else (int(actual_price * 0.98), int(actual_price * 0.96))
                _update_order(order["id"],
                    status="active",
                    entry_price=actual_price,
                    avg_price=float(actual_price),
                    base_price=actual_price,
                    trigger2=t2, trigger3=t3,
                )
                _send_admin(f"✅ <b>재주문 체결</b>\n<b>{order['name']}</b> ₩{actual_price:,.0f} × {order['qty']}주")
                print(f"[자동매매] {order['name']} 재주문 체결 ₩{actual_price:,.0f}")
            else:
                # 체결가 조회 실패해도 active로는 전환
                _update_order(order["id"], status="active")
                print(f"[자동매매] {order['name']} 재주문 완료 (체결가 조회 실패 - 예상가 사용)")
        else:
            print(f"[자동매매] {order['name']} 재주문 실패")

    # ── 7번: 갭하락 손절 체크 (장 시작 직후 09:00~09:15) ─────────
    # 전날 손절가 아래에서 갭하락 시작 시 즉시 손절
    now_kst = datetime.now(KST)
    is_gap_check_time = (now_kst.hour == 9 and now_kst.minute <= 15)
    if is_gap_check_time and is_trading_day():
        try:
            _gap_client = KISClient()
            _gap_orders = _get_pending_orders()
            _gap_today  = date.today().isoformat()
            for _go in _gap_orders:
                if _go["status"] != "active":
                    continue
                _gsym  = _go["symbol"]
                _gcur  = _gap_client.get_price(_gsym)
                _gstop = _go["stop_price"]
                _gavg  = _go.get("avg_price") or _go["entry_price"]
                _gqty  = _go["qty"]
                if _gcur and _gstop and _gcur <= _gstop * 0.99:  # 손절가 -1% 이하 갭하락
                    print(f"[자동매매] {_go['name']} 갭하락 감지 ₩{_gcur:,.0f} (손절가 ₩{_gstop:,}) → 즉시 손절")
                    _gr = _gap_client.sell_order(_gsym, int(_gcur), _gqty, market=True)
                    if _gr["success"]:
                        _gret = (_gcur - _gavg) / _gavg * 100 if _gavg else 0
                        _update_order(_go["id"],
                            status="hit_stop", exit_price=int(_gcur),
                            exit_date=_gap_today, return_pct=round(_gret, 2)
                        )
                        _send_admin(
                            f"🚨 <b>갭하락 손절</b>\n"
                            f"<b>{_go['name']}</b>\n"
                            f"갭하락 ₩{_gcur:,.0f} (손절가 ₩{_gstop:,})\n"
                            f"손실 <b>{_gret:.1f}%</b>"
                        )
                    else:
                        _send_admin(
                            f"🚨 <b>갭하락 손절 실패!</b>\n"
                            f"<b>{_go['name']}</b> ₩{_gcur:,.0f}\n"
                            f"⚠️ 즉시 수동 매도 필요!"
                        )
        except Exception as _ge:
            print(f"[자동매매] 갭하락 체크 오류: {_ge}")


def monitor_positions():
    """
    장중 모니터링 - 1분 간격 호출
    - active 종목: 목표가/손절가 도달 시 매도
    - pending 종목: 현재가 <= 매수가면 active로 전환
    """
    if not is_enabled():
        return

    # ── 장 시간 체크 ──────────────────────────────────────────────
    if not is_market_open():
        return

    client  = KISClient()
    today   = date.today().isoformat()
    orders  = _get_pending_orders()

    if not orders:
        return

    # 4번: 이번 사이클에서 이미 매도 처리된 종목 추적 (중복 매도 방지)
    _sold_this_cycle = set()

    # ── 실제 잔고 조회 (유저 임의 매도 감지용, 5분 캐시) ────────
    balance = _get_cached_balance(client)
    actual_holdings = balance.get("holdings", {})  # {code: {qty, avg_price, ...}}

    # ── 잔고 조회 실패 감지 ───────────────────────────────────────
    # holdings가 비어있으면 API 오류 가능성 → 수동매도 감지 로직 비활성화
    # (장 시작 직후, 모의투자 등에서 잔고 조회가 빈 응답 반환하는 경우 방지)
    _holdings_valid = bool(actual_holdings)

    for order in orders:
        symbol = order["symbol"]
        code   = symbol.replace(".KS", "").replace(".KQ", "")
        cur    = _get_price_yfinance_first(symbol, client)
        if cur is None:
            # 가격 조회 완전 실패 → 거래정지/상장폐지 가능성 알림
            print(f"[자동매매] {order['name']} 가격 조회 실패 - 거래정지 가능성")
            _send_admin(
                f"⚠️ <b>가격 조회 실패</b>\n"
                f"<b>{order['name']}</b> ({symbol})\n"
                f"KIS/yfinance 모두 가격 조회 불가\n"
                f"거래정지 또는 상장폐지 여부 확인 필요"
            )
            continue

        # pending 종목은 morning_reorder()에서 체결 확인 처리
        # monitor_positions()에서는 active 종목만 처리
        if order["status"] != "active":
            continue

        # 4번: 이번 사이클에서 이미 매도 처리된 종목 중복 처리 방지
        if symbol in _sold_this_cycle:
            print(f"[자동매매] {order['name']} 이번 사이클 이미 처리됨 - 스킵")
            continue

        entry      = order["entry_price"]
        target     = order["target_price"]
        stop       = order["stop_price"]
        qty        = order["qty"]
        split_step = order.get("split_step", 1)
        base_price = order.get("base_price", entry) or entry
        avg_price  = order.get("avg_price", entry) or entry
        trigger2   = order.get("trigger2") or int(base_price * 0.98)
        trigger3   = order.get("trigger3") or int(base_price * 0.96)

        # ── 실제 보유 수량 확인 (유저 임의 매도 대비) ────────────
        actual_qty = actual_holdings.get(code, {}).get("qty", 0)

        # ── 매도 미체결 확인 (이전 사이클에서 매도 주문 넣은 경우) ──
        _sell_ono = order.get("sell_order_no", "")
        _sell_ots = order.get("sell_order_ts", "")
        if _sell_ono and _sell_ots:
            try:
                _elapsed = (datetime.now(KST) - datetime.fromisoformat(_sell_ots).replace(tzinfo=KST)).total_seconds()
                if _elapsed >= 300:  # 5분 이상 미체결
                    _sell_status = client.get_order_status(_sell_ono, symbol)
                    if _sell_status == "filled":
                        # 체결됨 → DB 업데이트
                        ret = (cur - avg_price) / avg_price * 100 if avg_price else 0
                        _update_order(order["id"],
                            status="hit_target" if cur >= target else "hit_stop",
                            exit_price=int(cur), exit_date=today,
                            return_pct=round(ret, 2),
                            sell_order_no="", sell_order_ts=""
                        )
                        print(f"[자동매매] {order['name']} 매도 지연 체결 확인")
                        continue
                    elif _sell_status in ("pending", "partial"):
                        # 아직 미체결 → 취소 후 시장가 재주문
                        print(f"[자동매매] {order['name']} 매도 미체결 5분 경과 → 취소 후 시장가 재주문")
                        client.cancel_order(_sell_ono, symbol, qty)
                        time.sleep(1)
                        _r2 = client.sell_order(symbol, int(cur), qty, market=True)
                        if _r2["success"]:
                            ret = (cur - avg_price) / avg_price * 100 if avg_price else 0
                            _update_order(order["id"],
                                status="hit_target" if cur >= target else "hit_stop",
                                exit_price=int(cur), exit_date=today,
                                return_pct=round(ret, 2),
                                sell_order_no="", sell_order_ts=""
                            )
                            _send_admin(f"🔄 <b>매도 재주문 체결</b>\n<b>{order['name']}</b> {ret:+.1f}%")
                        else:
                            _send_admin(f"🚨 <b>매도 재주문 실패!</b>\n<b>{order['name']}</b> 수동 매도 필요")
                        continue
                    else:
                        # 취소됨 → sell_order_no 초기화 (다음 사이클에서 재시도)
                        _update_order(order["id"], sell_order_no="", sell_order_ts="")
            except Exception as _se:
                print(f"[자동매매] {order['name']} 매도 미체결 확인 오류: {_se}")

        if actual_qty == 0 and cur is not None and _holdings_valid:
            # 가격은 조회되는데 잔고가 0 → 전량 수동 매도된 경우
            # (_holdings_valid=False면 잔고 조회 실패이므로 스킵)
            ret = (cur - avg_price) / avg_price * 100 if avg_price else 0
            _update_order(order["id"],
                status="expired", exit_price=int(cur),
                exit_date=today, return_pct=round(ret, 2)
            )
            print(f"[자동매매] {order['name']} 실제 잔고 0 감지 → expired 처리")
            _send_admin(
                f"⚠️ <b>수동 매도 감지</b>\n"
                f"<b>{order['name']}</b> ({symbol})\n"
                f"실제 잔고 0주 → 자동매매 종료 처리\n"
                f"현재가 ₩{cur:,.0f} / 평단가 ₩{avg_price:,.0f}\n"
                f"수익률 {ret:+.1f}%"
            )
            continue

        if actual_qty < qty and _holdings_valid:
            # 일부 매도된 경우 → DB qty를 실제 수량으로 업데이트
            print(f"[자동매매] {order['name']} 수량 불일치 DB:{qty}주 → 실제:{actual_qty}주 보정")
            _update_order(order["id"], qty=actual_qty)
            qty = actual_qty
            _send_admin(
                f"⚠️ <b>수량 불일치 보정</b>\n"
                f"<b>{order['name']}</b> ({symbol})\n"
                f"DB {order['qty']}주 → 실제 {actual_qty}주로 업데이트\n"
                f"(일부 수동 매도 감지)"
            )
        elif actual_qty > qty and _holdings_valid:
            # 분할매수 직후 잔고 캐시 지연으로 인한 오탐 방지:
            # split_step > 1이면 분할매수로 인한 정상 증가 → DB만 보정, 알림 생략
            actual_avg = actual_holdings.get(code, {}).get("avg_price", avg_price)
            print(f"[자동매매] {order['name']} 수량 증가 DB:{qty}주 → 실제:{actual_qty}주 (step={split_step})")
            _update_order(order["id"], qty=actual_qty, avg_price=round(actual_avg, 2))
            qty = actual_qty
            avg_price = actual_avg
            if split_step <= 1:
                # 분할매수가 아닌 외부 추가 매수인 경우만 알림
                _send_admin(
                    f"ℹ️ <b>추가 매수 감지</b>\n"
                    f"<b>{order['name']}</b> ({symbol})\n"
                    f"DB {order['qty']}주 → 실제 {actual_qty}주로 업데이트\n"
                    f"평단가 ₩{actual_avg:,.0f}"
                )

        # ── 손절가 도달 시 분할매수 트리거보다 우선 처리 ────────────
        cfg = _cfg()
        split_budget = cfg["budget_per"] // 3

        if cur <= stop:
            result = client.sell_order(symbol, stop, qty, market=True)
            if result["success"]:
                ret = (cur - avg_price) / avg_price * 100
                _update_order(order["id"],
                    status="hit_stop", exit_price=int(cur),
                    exit_date=today, return_pct=round(ret, 2)
                )
                print(f"[자동매매] {order['name']} 손절가 도달 (분할매수 중단) → 전량 매도 {ret:.1f}%")
                _send_admin(
                    f"🛑 <b>손절 실행</b> (분할매수 중단)\n"
                    f"<b>{order['name']}</b>\n"
                    f"평단가 ₩{avg_price:,.0f} → 손절 ₩{cur:,.0f}\n"
                    f"손실 <b>{ret:.1f}%</b>"
                )
                time.sleep(1)
            else:
                err = result.get("error", "")
                time.sleep(3)
                result2 = client.sell_order(symbol, stop, qty, market=True)
                if result2["success"]:
                    ret = (cur - avg_price) / avg_price * 100
                    _update_order(order["id"],
                        status="hit_stop", exit_price=int(cur),
                        exit_date=today, return_pct=round(ret, 2)
                    )
                    _send_admin(f"🛑 <b>손절 실행 (재시도 성공)</b>\n<b>{order['name']}</b> {ret:.1f}%")
                else:
                    _send_admin(
                        f"🚨 <b>손절 매도 실패!</b>\n"
                        f"<b>{order['name']}</b> 손절가 도달했으나 매도 실패\n"
                        f"오류: {err}\n⚠️ 즉시 수동 매도 필요!"
                    )
            continue  # 손절 처리 후 분할매수 트리거 체크 건너뜀

        # ── 분할매수 2/3차 트리거 ──────────────────────────────────
        if split_step == 1 and cur <= trigger2:
            # 3번: 분할매수 전 예수금 재확인
            _bal2 = client.get_balance()
            _cash2 = _bal2.get("cash", 0)
            add_qty = max(1, int(split_budget / cur))
            if int(cur) * add_qty > _cash2:
                print(f"[자동매매] {order['name']} 2차 매수 예수금 부족 ({_cash2:,.0f}원) - 스킵")
                _send_admin(f"⚠️ <b>2차 매수 예수금 부족</b>\n<b>{order['name']}</b>\n필요: ₩{int(cur)*add_qty:,} / 보유: ₩{_cash2:,.0f}")
                continue
            result  = client.buy_order(order["symbol"], int(cur), add_qty, market=True)
            if result["success"]:
                new_avg = (avg_price * qty + cur * add_qty) / (qty + add_qty)
                _update_order(order["id"],
                    split_step=2, split_qty=qty + add_qty,
                    avg_price=round(new_avg, 2), qty=qty + add_qty,
                    step2_price=round(cur, 2), step2_qty=add_qty,
                )
                _invalidate_balance_cache()  # 분할매수 후 잔고 캐시 즉시 무효화
                print(f"[자동매매] {order['name']} 2차 매수 {add_qty}주 @{cur:,.0f}")
                _send_admin(
                    f"📥 <b>2차 분할매수</b>  <b>{order['name']}</b>\n"
                    f"  1차 ₩{base_price:,.0f} × {qty}주\n"
                    f"  2차 ₩{cur:,.0f} × {add_qty}주\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"  평단가 ₩{new_avg:,.0f} × {qty + add_qty}주\n"
                    f"  🛑 손절 ₩{stop:,}"
                )
            continue

        elif split_step == 2 and cur <= trigger3:
            # 3번: 3차 분할매수 전 예수금 재확인
            _bal3 = client.get_balance()
            _cash3 = _bal3.get("cash", 0)
            add_qty = max(1, int(split_budget / cur))
            if int(cur) * add_qty > _cash3:
                print(f"[자동매매] {order['name']} 3차 매수 예수금 부족 ({_cash3:,.0f}원) - 스킵")
                _send_admin(f"⚠️ <b>3차 매수 예수금 부족</b>\n<b>{order['name']}</b>\n필요: ₩{int(cur)*add_qty:,} / 보유: ₩{_cash3:,.0f}")
                continue
            result  = client.buy_order(order["symbol"], int(cur), add_qty, market=True)
            if result["success"]:
                new_avg     = (avg_price * qty + cur * add_qty) / (qty + add_qty)
                step2_price = order.get("step2_price") or trigger2
                step2_qty   = order.get("step2_qty") or 0
                step1_qty   = qty - step2_qty
                _update_order(order["id"],
                    split_step=3, split_qty=qty + add_qty,
                    avg_price=round(new_avg, 2), qty=qty + add_qty,
                    step3_price=round(cur, 2), step3_qty=add_qty,
                )
                _invalidate_balance_cache()  # 분할매수 후 잔고 캐시 즉시 무효화
                print(f"[자동매매] {order['name']} 3차 매수 {add_qty}주 @{cur:,.0f}")
                _send_admin(
                    f"📥 <b>3차 분할매수 완료</b>  <b>{order['name']}</b>\n"
                    f"  1차 ₩{base_price:,.0f} × {step1_qty}주\n"
                    f"  2차 ₩{step2_price:,.0f} × {step2_qty}주\n"
                    f"  3차 ₩{cur:,.0f} × {add_qty}주\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"  평단가 ₩{new_avg:,.0f} × {qty + add_qty}주\n"
                    f"  🎯 목표 ₩{target:,}  🛑 손절 ₩{stop:,}"
                )
            continue

        # 목표가 도달
        if cur >= target:
            result = client.sell_order(symbol, target, qty, market=True)
            if result["success"]:
                ret = (cur - avg_price) / avg_price * 100
                _sell_no = result.get("order_no", "")
                _sell_ts = datetime.now(KST).isoformat()
                _update_order(order["id"],
                    status="hit_target", exit_price=int(cur),
                    exit_date=today, return_pct=round(ret, 2),
                    sell_order_no=_sell_no, sell_order_ts=_sell_ts
                )
                _sold_this_cycle.add(symbol)  # 4번: 중복 매도 방지
                print(f"[자동매매] {order['name']} 목표가 도달 → 매도 +{ret:.1f}%")
                # ── 매도 체결 확인 ──────────────────────────────
                time.sleep(2)
                _invalidate_balance_cache()  # 매도 후 잔고 캐시 무효화
                _verify_sell_filled(client, order, code, cur, avg_price)
                _send_admin(
                    f"🎯 <b>목표가 달성!</b>\n"
                    f"<b>{order['name']}</b>\n"
                    f"평단가 ₩{avg_price:,.0f} → 매도 ₩{cur:,.0f}\n"
                    f"수익률 <b>+{ret:.1f}%</b> 🎉"
                )
                time.sleep(1)  # 동시 주문 몰림 방지
            else:
                # ── 매도 실패 처리 ──────────────────────────────
                err = result.get("error", "")
                # 거래정지/상한가 등으로 시장가 불가 → 재시도 1회
                print(f"[자동매매] {order['name']} 목표가 매도 실패: {err}")
                time.sleep(3)
                result2 = client.sell_order(symbol, target, qty, market=True)
                if result2["success"]:
                    ret = (cur - avg_price) / avg_price * 100
                    _update_order(order["id"],
                        status="hit_target", exit_price=int(cur),
                        exit_date=today, return_pct=round(ret, 2)
                    )
                    _send_admin(f"🎯 <b>목표가 달성 (재시도 성공)</b>\n<b>{order['name']}</b> +{ret:.1f}%")
                else:
                    _send_admin(
                        f"⚠️ <b>매도 주문 실패</b>\n"
                        f"<b>{order['name']}</b> 목표가 도달했으나 매도 실패\n"
                        f"오류: {err}\n수동 매도 필요"
                    )

        # 손절가 도달
        elif cur <= stop:
            result = client.sell_order(symbol, stop, qty, market=True)
            if result["success"]:
                ret = (cur - avg_price) / avg_price * 100
                _sell_no = result.get("order_no", "")
                _sell_ts = datetime.now(KST).isoformat()
                _update_order(order["id"],
                    status="hit_stop", exit_price=int(cur),
                    exit_date=today, return_pct=round(ret, 2),
                    sell_order_no=_sell_no, sell_order_ts=_sell_ts
                )
                _sold_this_cycle.add(symbol)  # 4번: 중복 매도 방지
                print(f"[자동매매] {order['name']} 손절가 도달 → 시장가 매도 {ret:.1f}%")
                # ── 매도 체결 확인 ──────────────────────────────
                time.sleep(2)
                _invalidate_balance_cache()  # 매도 후 잔고 캐시 무효화
                _verify_sell_filled(client, order, code, cur, avg_price)
                _send_admin(
                    f"🛑 <b>손절 실행</b>\n"
                    f"<b>{order['name']}</b>\n"
                    f"평단가 ₩{avg_price:,.0f} → 손절 ₩{cur:,.0f}\n"
                    f"손실 <b>{ret:.1f}%</b>"
                )
                time.sleep(1)  # 동시 손절 몰림 방지
            else:
                # ── 손절 매도 실패 → 즉시 알림 (손실 확대 방지) ──
                err = result.get("error", "")
                print(f"[자동매매] {order['name']} 손절 매도 실패: {err}")
                time.sleep(3)
                result2 = client.sell_order(symbol, stop, qty, market=True)
                if result2["success"]:
                    ret = (cur - avg_price) / avg_price * 100
                    _update_order(order["id"],
                        status="hit_stop", exit_price=int(cur),
                        exit_date=today, return_pct=round(ret, 2)
                    )
                    _send_admin(f"🛑 <b>손절 실행 (재시도 성공)</b>\n<b>{order['name']}</b> {ret:.1f}%")
                else:
                    _send_admin(
                        f"🚨 <b>손절 매도 실패!</b>\n"
                        f"<b>{order['name']}</b> 손절가 도달했으나 매도 실패\n"
                        f"오류: {err}\n⚠️ 즉시 수동 매도 필요!"
                    )


# ── 안전장치 헬퍼 함수들 ─────────────────────────────────────────

def _verify_sell_filled(client, order: dict, code: str, cur: float, avg_price: float):
    """1번: 매도 주문 후 실제 체결 여부 확인 - 잔고에 아직 남아있으면 경고"""
    try:
        bal = client.get_balance()
        remaining = bal.get("holdings", {}).get(code, {}).get("qty", 0)
        if remaining > 0:
            _send_admin(
                f"⚠️ <b>매도 미체결 의심</b>\n"
                f"<b>{order['name']}</b> ({order['symbol']})\n"
                f"매도 주문 후 잔고 {remaining}주 남아있음\n"
                f"실제 체결 여부 확인 필요"
            )
            print(f"[자동매매] {order['name']} 매도 후 잔고 {remaining}주 남음 - 미체결 의심")
    except Exception as e:
        print(f"[자동매매] 매도 체결 확인 오류: {e}")


def _is_recently_sold(symbol: str, days: int = 3) -> bool:
    """6번: 최근 N일 내 손절/목표가 도달로 매도된 종목인지 확인 (재매수 방지)"""
    try:
        conn = _get_trade_conn()
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        row = conn.execute(
            "SELECT id FROM trade_orders WHERE symbol=? AND status IN ('hit_target','hit_stop') AND exit_date >= ?",
            (symbol, cutoff)
        ).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def scheduler_heartbeat():
    """7번: 스케줄러 heartbeat 기록 - scheduler.py에서 매 루프마다 호출"""
    try:
        hb_file = "/data/.scheduler_heartbeat" if os.path.isdir("/data") else ".scheduler_heartbeat"
        with open(hb_file, "w") as f:
            f.write(datetime.now(KST).isoformat())
    except Exception:
        pass


def check_scheduler_alive(max_minutes: int = 10) -> bool:
    """스케줄러가 살아있는지 확인"""
    try:
        hb_file = "/data/.scheduler_heartbeat" if os.path.isdir("/data") else ".scheduler_heartbeat"
        if not os.path.exists(hb_file):
            return False
        with open(hb_file) as f:
            last_hb = datetime.fromisoformat(f.read().strip())
        if last_hb.tzinfo is None:
            last_hb = last_hb.replace(tzinfo=KST)
        return (datetime.now(KST) - last_hb).total_seconds() / 60 <= max_minutes
    except Exception:
        return False


def send_trade_report():
    """자동매매 전용 일일 리포트 - 가독성 최적화"""
    if not is_enabled():
        return
    try:
        client    = KISClient()
        conn      = _get_trade_conn()
        today     = date.today().isoformat()
        today_fmt = date.today().strftime("%Y.%m.%d")
        cfg       = _cfg()
        mock_tag  = "[모의] " if cfg["mock"] else ""

        # ── DB 조회 ───────────────────────────────────────────────
        closed_today = conn.execute("""
            SELECT name, symbol, avg_price, exit_price, return_pct, status, split_step, qty
            FROM trade_orders WHERE exit_date=? AND status IN ('hit_target','hit_stop')
        """, (today,)).fetchall()

        active_rows = conn.execute("""
            SELECT id, name, symbol, avg_price, target_price, stop_price,
                   qty, split_step, entry_price, alert_date
            FROM trade_orders WHERE status='active'
        """).fetchall()

        pending_rows = conn.execute("""
            SELECT name, symbol, entry_price, target_price, alert_date
            FROM trade_orders WHERE status='pending'
        """).fetchall()

        all_closed = conn.execute("""
            SELECT name, symbol, return_pct, status, exit_date
            FROM trade_orders
            WHERE status IN ('hit_target','hit_stop') AND return_pct IS NOT NULL
        """).fetchall()

        # 이번 달 손익
        month_start = date.today().strftime("%Y-%m-01")
        month_closed = conn.execute("""
            SELECT return_pct, avg_price, qty FROM trade_orders
            WHERE status IN ('hit_target','hit_stop')
              AND exit_date >= ? AND return_pct IS NOT NULL
        """, (month_start,)).fetchall()
        conn.close()

        # ── 잔고 조회 ─────────────────────────────────────────────
        balance      = client.get_balance()
        cash         = balance.get("cash", 0)

        # ── KOSPI 조회 ────────────────────────────────────────────
        kospi_str = ""
        try:
            import yfinance as yf
            k = yf.Ticker("^KS11").history(period="2d")["Close"]
            if len(k) >= 2:
                chg = (k.iloc[-1] - k.iloc[-2]) / k.iloc[-2] * 100
                arrow = "▲" if chg >= 0 else "▼"
                kospi_str = f"KOSPI {k.iloc[-1]:,.0f} {arrow}{abs(chg):.2f}%"
        except:
            pass

        # ── 포트폴리오 계산 ───────────────────────────────────────
        total_invest = 0
        total_eval   = 0
        active_data  = []
        for row in active_rows:
            rid, name, sym, avg_p, target, stop, qty, step, entry, alert_date = row
            avg_p = float(avg_p or entry or 0)
            cur   = client.get_price(sym)
            # 현재가 조회 실패 시 yfinance 폴백
            if cur is None:
                import time as _time
                _time.sleep(0.5)
                cur = client.get_price(sym)
            if cur is None:
                try:
                    import yfinance as _yf
                    _d = _yf.Ticker(sym).history(period="2d")
                    if len(_d) > 0:
                        cur = float(_d["Close"].iloc[-1])
                except Exception:
                    pass
            days  = (date.today() - date.fromisoformat(alert_date)).days if alert_date else 0
            invest = avg_p * qty if avg_p and qty else 0
            eval_  = (cur * qty) if cur and qty else invest
            total_invest += invest
            total_eval   += eval_
            active_data.append({
                "name": name, "sym": sym, "avg_p": avg_p, "cur": cur,
                "target": target, "stop": stop, "qty": qty,
                "step": step or 1, "days": days, "invest": invest, "eval": eval_
            })

        total_pnl     = total_eval - total_invest
        total_pnl_pct = (total_pnl / total_invest * 100) if total_invest > 0 else 0
        total_asset   = total_eval + cash

        # 전날 대비 손익 변화
        prev_eval_file = "/data/.prev_eval" if os.path.isdir("/data") else ".prev_eval"
        prev_eval = 0
        try:
            with open(prev_eval_file) as f:
                prev_eval = float(f.read().strip())
        except:
            pass
        daily_chg = total_eval - prev_eval if prev_eval > 0 else None
        # 오늘 평가금액 저장
        try:
            with open(prev_eval_file, "w") as f:
                f.write(str(total_eval))
        except:
            pass

        # 이번 달 손익 금액
        month_pnl = sum(
            int(r[1] * r[2] * r[0] / 100) for r in month_closed
            if r[1] and r[2] and r[0]
        )

        # ── 메시지 구성 ───────────────────────────────────────────
        SEP  = "━" * 20
        SEP2 = "─" * 16

        lines = [
            f"🤖 {mock_tag}<b>자동매매 리포트</b>",
            f"<i>{today_fmt}  {kospi_str}</i>",
            SEP,
        ]

        # 1. 포트폴리오 요약
        pnl_icon = "📈" if total_pnl >= 0 else "📉"
        pnl_sign = "+" if total_pnl >= 0 else ""
        port_bar_filled = round(min(max(total_pnl_pct / 20, 0), 1) * 8)  # 0~+20% 범위, 0에서 시작
        port_bar = ("🟩" if total_pnl >= 0 else "🟥") * port_bar_filled + "⬜" * (8 - port_bar_filled)
        lines += [
            f"\n💼 <b>포트폴리오 현황</b>",
            f"  총 자산    ₩{total_asset:,.0f}",
            f"  투자금     ₩{total_invest:,.0f}  ({len(active_data)}종목)",
            f"  평가손익   {pnl_icon} <b>{pnl_sign}₩{int(total_pnl):,}  ({pnl_sign}{total_pnl_pct:.1f}%)</b>",
            f"  예수금     ₩{cash:,.0f}",
            f"  {port_bar}",
        ]
        if daily_chg is not None:
            d_sign = "+" if daily_chg >= 0 else ""
            d_icon = "📈" if daily_chg >= 0 else "📉"
            lines.append(f"  전일 대비  {d_icon} <b>{d_sign}₩{int(daily_chg):,}</b>")
        if month_pnl != 0:
            m_sign = "+" if month_pnl >= 0 else ""
            lines.append(f"  이번 달 손익  <b>{m_sign}₩{month_pnl:,}</b>")

        # 2. 오늘 청산
        if closed_today:
            lines += [f"\n{SEP2}", "🔔 <b>오늘 청산</b>"]
            for row in closed_today:
                name, sym, avg_p, exit_p, ret, status, step, qty = row
                icon     = "✅" if status == "hit_target" else "🛑"
                step_str = f" ({step}차)" if step and step > 1 else ""
                pnl      = int((exit_p - avg_p) * qty) if avg_p and exit_p and qty else 0
                p_sign   = "+" if pnl >= 0 else ""
                lines.append(
                    f"\n{icon} <b>{name}</b>{step_str}\n"
                    f"   ₩{avg_p:,.0f} → ₩{exit_p:,.0f}\n"
                    f"   <b>{ret:+.1f}%  {p_sign}₩{pnl:,}</b>"
                )

        # 3. 보유 중
        if active_data:
            lines += [f"\n{SEP2}", f"🟢 <b>보유 중</b>  ({len(active_data)}종목)"]
            for d in active_data:
                step = d["step"] or 1
                # 분할매수 진행 상황: 매수된 차수는 🔵, 대기는 ⚪
                split_icons = ""
                for i in range(1, 4):
                    split_icons += "🔵" if i <= step else "⚪"
                split_remain = ""
                if step == 1:   split_remain = "  <i>2·3차 대기</i>"
                elif step == 2: split_remain = "  <i>3차 대기</i>"

                cur_line = "  현재가 조회 불가"
                display_cur = d["cur"] if d["cur"] else d["avg_p"]
                if display_cur and d["avg_p"]:
                    ret    = (display_cur - d["avg_p"]) / d["avg_p"] * 100
                    pnl    = int((display_cur - d["avg_p"]) * d["qty"])
                    p_sign = "+" if pnl >= 0 else ""
                    if d["target"] and d["stop"] and d["target"] > d["stop"]:
                        if ret >= 0:
                            ratio  = min((display_cur - d["avg_p"]) / (d["target"] - d["avg_p"]), 1.0)
                            filled = round(ratio * 8)
                            bar    = "🟩" * filled + "⬜" * (8 - filled)
                        else:
                            ratio  = min((d["avg_p"] - display_cur) / (d["avg_p"] - d["stop"]), 1.0)
                            filled = round(ratio * 8)
                            bar    = "🟥" * filled + "⬜" * (8 - filled)
                    else:
                        bar = "⬜" * 8
                    to_stop = (display_cur - d["stop"]) / display_cur * 100 if d["stop"] else 0
                    price_str = f"₩{d['cur']:,.0f}" if d["cur"] else "조회불가(평단기준)"
                    cur_line = (
                        f"\n  {bar}  <b>{ret:+.1f}%  {p_sign}₩{pnl:,}</b>"
                        f"\n  현재가  {price_str}"
                        f"\n  🎯 ₩{d['target']:,}  🛑 ₩{d['stop']:,}  (손절까지 {to_stop:.1f}%)"
                    )

                lines.append(
                    f"\n📌 <b>{d['name']}</b>  <i>{d['days']}일째</i>  {split_icons}{split_remain}"
                    f"\n  평단가  ₩{d['avg_p']:,.0f} × {d['qty']}주"
                    f"\n  투자금    ₩{int(d['invest']):,}"
                    + cur_line
                )

        # 4. 대기 중
        if pending_rows:
            lines += [f"\n{SEP2}", f"⏳ <b>매수 대기</b>  ({len(pending_rows)}종목)"]
            for row in pending_rows:
                name, sym, entry, target, alert_date = row
                days = (date.today() - date.fromisoformat(alert_date)).days if alert_date else 0
                lines.append(
                    f"🔵 <b>{name}</b>  <i>{days}일째</i>\n"
                    f"   📍₩{entry:,}  🎯₩{target:,}"
                )

        # 5. 누적 성과
        if all_closed:
            wins   = [(r[0], r[2]) for r in all_closed if r[3]=="hit_target" and r[2] is not None]
            losses = [(r[0], r[2]) for r in all_closed if r[3]=="hit_stop"   and r[2] is not None]
            all_ret = [r[2] for r in all_closed if r[2] is not None]
            total  = len(all_closed)
            wr     = round(len(wins) / total * 100, 1) if total else 0
            avg    = round(sum(all_ret) / len(all_ret), 1) if all_ret else 0
            wr_filled = round(wr / 10)
            wr_bar    = "🟩" * wr_filled + "⬜" * (10 - wr_filled)
            wr_label  = "우수" if wr >= 60 else "보통" if wr >= 40 else "부진"
            lines += [
                f"\n{SEP2}",
                f"📊 <b>누적 성과</b>  ({total}건)",
                f"  {wr_bar}  {wr}%  <i>{wr_label}</i>",
                f"  ✅{len(wins)}건  🛑{len(losses)}건  평균 <b>{avg:+.1f}%</b>",
            ]
            if wins:
                best = max(wins, key=lambda x: x[1])
                lines.append(f"  🏆 최고  <b>{best[0]}</b>  +{best[1]:.1f}%")
            if losses:
                worst = min(losses, key=lambda x: x[1])
                lines.append(f"  💔 최대손실  <b>{worst[0]}</b>  {worst[1]:.1f}%")

        lines += [f"\n{SEP}", "⚠️ <i>자동매매 참고용 정보입니다</i>"]

        # 4000자 초과 시 분할 전송
        msg = "\n".join(lines)
        if len(msg) > 4000:
            chunks, cur_chunk = [], []
            for line in lines:
                if sum(len(l) for l in cur_chunk) + len(line) > 3800:
                    _send_admin("\n".join(cur_chunk))
                    cur_chunk = [line]
                else:
                    cur_chunk.append(line)
            if cur_chunk:
                _send_admin("\n".join(cur_chunk))
        else:
            _send_admin(msg)

        print("[자동매매] 리포트 전송 완료")

    except Exception as e:
        print(f"[자동매매] 리포트 오류: {e}")
        import traceback; traceback.print_exc()


def verify_positions():
    """
    실제 KIS 잔고 vs DB 상태 검증 (매일 09:10 실행)
    불일치 발견 시 DB 자동 수정 + 개인 알림
    케이스:
      1) DB active/pending인데 실제 미보유 → DB를 cancelled로 수정
      2) DB pending인데 실제 보유 중 → DB를 active로 수정 + 평단가 동기화
      3) DB 수량 vs 실제 수량 불일치 → DB 수량 동기화
    """
    if not is_enabled():
        return

    try:
        client = KISClient()
        balance = client.get_balance()
        holdings = balance.get("holdings", {})  # {code: {qty, avg_price, ...}}

        # ── 잔고 조회 실패 시 검증 중단 (오탐 방지) ──────────────
        # holdings가 비어있고 cash도 0이면 API 오류로 판단
        if not holdings and balance.get("cash", 0) == 0:
            print("[잔고검증] 잔고 조회 결과 없음 - API 오류 가능성, 검증 중단")
            _send_admin("⚠️ <b>잔고검증 스킵</b>\n잔고 조회 결과가 없어 검증을 중단했습니다.\n(모의투자 장외시간 또는 API 오류)")
            return

        conn = _get_trade_conn()
        db_orders = conn.execute(
            "SELECT id, symbol, name, status, qty, avg_price, entry_price FROM trade_orders "
            "WHERE status IN ('pending', 'active')"
        ).fetchall()

        issues = []
        today = date.today().isoformat()

        for row in db_orders:
            oid, symbol, name, status, db_qty, db_avg, db_entry = row
            code = symbol.replace(".KS", "").replace(".KQ", "")
            real = holdings.get(code)

            # ── 케이스 1: DB active인데 실제 미보유 ──────────────
            if status == "active" and not real:
                conn.execute(
                    "UPDATE trade_orders SET status='cancelled' WHERE id=?", (oid,)
                )
                issues.append(
                    f"⚠️ <b>{name}</b>\n"
                    f"  DB: active → 실제: 미보유\n"
                    f"  → DB를 cancelled로 수정"
                )

            # ── 케이스 2: DB pending인데 실제 보유 중 ────────────
            elif status == "pending" and real:
                real_qty = int(real.get("qty", 0))
                real_avg = float(real.get("avg_price", db_entry or 0))
                conn.execute(
                    "UPDATE trade_orders SET status='active', qty=?, avg_price=?, entry_price=? WHERE id=?",
                    (real_qty, real_avg, int(real_avg), oid)
                )
                issues.append(
                    f"✅ <b>{name}</b>\n"
                    f"  DB: pending → 실제: 보유 {real_qty}주 @₩{real_avg:,.0f}\n"
                    f"  → DB를 active로 수정"
                )

            # ── 케이스 3: DB active + 실제 보유 but 수량 불일치 ──
            elif status == "active" and real:
                real_qty = int(real.get("qty", 0))
                real_avg = float(real.get("avg_price", db_avg or db_entry or 0))
                if real_qty != db_qty:
                    conn.execute(
                        "UPDATE trade_orders SET qty=?, avg_price=? WHERE id=?",
                        (real_qty, real_avg, oid)
                    )
                    issues.append(
                        f"🔧 <b>{name}</b>\n"
                        f"  수량 불일치: DB {db_qty}주 → 실제 {real_qty}주\n"
                        f"  평단가: ₩{real_avg:,.0f}\n"
                        f"  → DB 수량/단가 동기화"
                    )
                elif abs((real_avg or 0) - (db_avg or db_entry or 0)) > 10:
                    # 평단가만 불일치
                    conn.execute(
                        "UPDATE trade_orders SET avg_price=? WHERE id=?",
                        (real_avg, oid)
                    )
                    issues.append(
                        f"🔧 <b>{name}</b>\n"
                        f"  평단가 불일치: DB ₩{db_avg:,.0f} → 실제 ₩{real_avg:,.0f}\n"
                        f"  → DB 단가 동기화"
                    )

        conn.commit()
        conn.close()

        # ── 결과 알림 ─────────────────────────────────────────────
        if issues:
            msg = (
                f"🔍 <b>잔고 검증 완료</b>  {today}\n"
                f"{'━'*20}\n"
                f"불일치 {len(issues)}건 발견 → 자동 수정\n\n"
                + "\n\n".join(issues)
            )
            _send_admin(msg)
            print(f"[잔고검증] {len(issues)}건 불일치 수정 완료")
        else:
            print(f"[잔고검증] 이상 없음 (DB ↔ 실제 잔고 일치)")

    except Exception as e:
        print(f"[잔고검증] 오류: {e}")
        import traceback; traceback.print_exc()
        _send_admin(f"⚠️ <b>잔고검증 오류</b>\n{e}")
