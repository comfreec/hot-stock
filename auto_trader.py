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
        """액세스 토큰 발급 (캐시)"""
        now = datetime.now(KST)
        if self._token and self._token_exp and now < self._token_exp:
            return self._token
        resp = requests.post(f"{self.base}/oauth2/tokenP", json={
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_exp = now + timedelta(hours=23)
        return self._token

    def _headers(self, tr_id: str, extra: dict = None) -> dict:
        acct = self.account.replace("-", "")
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
            # symbol에서 .KS/.KQ 제거
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
        code  = symbol.replace(".KS", "").replace(".KQ", "")
        acct_no = self.account.split("-")[0]
        acct_cd = self.account.split("-")[1] if "-" in self.account else "01"
        tr_id = "VTTC0802U" if self.mock else "TTTC0802U"
        ord_dvsn  = "01" if market else "00"
        ord_price = "0"  if market else str(price)
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
            order_no = result.get("output", {}).get("ODNO", "")
            kind = "시장가" if market else f"@{price:,}원"
            print(f"[KIS] 매수 주문 {code} {qty}주 {kind} → 주문번호 {order_no}")
            return {"success": True, "order_no": order_no}
        except Exception as e:
            print(f"[KIS] 매수 주문 오류 {code}: {e}")
            return {"success": False, "error": str(e)}

    def sell_order(self, symbol: str, price: int, qty: int, market: bool = False) -> dict:
        """매도 주문 (지정가 or 시장가)"""
        code  = symbol.replace(".KS", "").replace(".KQ", "")
        acct_no = self.account.split("-")[0]
        acct_cd = self.account.split("-")[1] if "-" in self.account else "01"
        tr_id = "VTTC0801U" if self.mock else "TTTC0801U"
        ord_dvsn = "01" if market else "00"  # 01=시장가, 00=지정가
        ord_price = "0" if market else str(price)
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
            order_no = result.get("output", {}).get("ODNO", "")
            kind = "시장가" if market else f"@{price:,}원"
            print(f"[KIS] 매도 주문 {code} {qty}주 {kind} → 주문번호 {order_no}")
            return {"success": True, "order_no": order_no}
        except Exception as e:
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
    conn = sqlite3.connect(db_path, check_same_thread=False)
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
            base_price  INTEGER DEFAULT 0    -- 1차 매수가 (2/3차 트리거 기준)
        )
    """)
    conn.commit()
    # 기존 DB에 분할매수 컬럼 없으면 추가 (마이그레이션)
    existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(trade_orders)").fetchall()]
    for col, default in [("split_step","1"),("split_qty","0"),("avg_price","0"),("base_price","0")]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE trade_orders ADD COLUMN {col} INTEGER DEFAULT {default}")
    conn.commit()
    return conn


def _get_pending_orders() -> list:
    conn = _get_trade_conn()
    # trigger2/trigger3 컬럼 없으면 추가
    existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(trade_orders)").fetchall()]
    for col in ["trigger2", "trigger3"]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE trade_orders ADD COLUMN {col} INTEGER DEFAULT 0")
    conn.commit()
    rows = conn.execute("""
        SELECT id, alert_date, symbol, name, entry_price, target_price, stop_price,
               qty, order_no, status, split_step, split_qty, avg_price, base_price,
               trigger2, trigger3
        FROM trade_orders WHERE status IN ('pending', 'active')
        ORDER BY alert_date ASC
    """).fetchall()
    conn.close()
    keys = ["id","alert_date","symbol","name","entry_price","target_price","stop_price",
            "qty","order_no","status","split_step","split_qty","avg_price","base_price",
            "trigger2","trigger3"]
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
    1차 매수가 ~ 240선 구간을 3등분한 2/3차 트리거 계산
    base_price: 1차 매수가
    ma240: 240일선 가격
    returns: (trigger2, trigger3)
    """
    if ma240 >= base_price:
        # 240선이 매수가보다 높으면 기존 방식(-2%, -4%) 사용
        return base_price * 0.98, base_price * 0.96
    gap = base_price - ma240
    trigger2 = base_price - gap / 3
    trigger3 = base_price - gap * 2 / 3
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

        # 이미 대기 주문 있으면 스킵
        if any(o["symbol"] == symbol for o in pending):
            print(f"[자동매매] {name} 이미 대기 주문 있음 - 스킵")
            continue

        # 가격 레벨 - alert_history에서 조회 (전날 스캔 기준)
        from cache_db import _get_conn as _db_conn
        lv = {}
        try:
            _conn = _db_conn()
            # 오늘 또는 어제 날짜로 조회 (스캔 날짜 기준)
            _row = _conn.execute(
                "SELECT entry_price, target_price, stop_price FROM alert_history "
                "WHERE symbol=? ORDER BY id DESC LIMIT 1",
                (symbol,)
            ).fetchone()
            _conn.close()
            if _row:
                lv = {"entry": _row[0], "target": _row[1], "stop": _row[2]}
        except:
            pass

        if not lv.get("entry") or not lv.get("target") or not lv.get("stop"):
            print(f"[자동매매] {name} 가격 레벨 없음 - 스킵")
            continue

        entry  = int(lv["entry"])
        target = int(lv["target"])
        stop   = int(lv["stop"])

        if cash < budget * 0.8:
            print(f"[자동매매] 예수금 부족 ({cash:,.0f}원) - 주문 중단")
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
            cash -= actual_cost
            ordered += 1

            # 텔레그램 알림
            try:
                from telegram_alert import send_telegram
                mock_tag = "[모의] " if cfg["mock"] else ""
                t2_pct = (t2 / entry - 1) * 100 if entry else 0
                t3_pct = (t3 / entry - 1) * 100 if entry else 0
                _send_admin(
                    f"🤖 {mock_tag}<b>자동매수 주문</b>\n"
                    f"<b>{name}</b> ({symbol})\n"
                    f"📍 1차 매수: ₩{entry:,}  ×  {qty}주\n"
                    f"🎯 목표가: ₩{target:,}\n"
                    f"🛑 손절가: ₩{stop:,}\n"
                    f"💰 주문금액: ₩{actual_cost:,}\n"
                    f"\n📋 <b>분할매수 미리보기</b>\n"
                    f"  2차: ₩{t2:,} ({t2_pct:.1f}%)\n"
                    f"  3차: ₩{t3:,} ({t3_pct:.1f}%)"
                )
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
                    _update_order(order["id"], status="active")
                    print(f"[자동매매] {order['name']} 체결 확인 → active")
                    _send_admin(f"✅ <b>매수 체결 확인</b>\n<b>{order['name']}</b> ₩{order['entry_price']:,} × {order['qty']}주")
                elif status == "partial":
                    print(f"[자동매매] {order['name']} 부분 체결 - 대기 유지")
            continue

        # 전날 주문 체결 여부 먼저 확인
        if order.get("order_no"):
            status = client.get_order_status(order["order_no"], order["symbol"])
            if status == "filled":
                _update_order(order["id"], status="active")
                print(f"[자동매매] {order['name']} 전날 체결 확인 → active")
                _send_admin(f"✅ <b>매수 체결 확인</b>\n<b>{order['name']}</b> ₩{order['entry_price']:,} × {order['qty']}주")
                continue
            # 미체결이면 취소 후 재주문
            client.cancel_order(order["order_no"], order["symbol"], order["qty"])

        result = client.buy_order(order["symbol"], order["entry_price"], order["qty"], market=True)
        if result["success"]:
            _update_order(order["id"],
                alert_date=today,
                order_no=result.get("order_no", ""),
            )
            print(f"[자동매매] {order['name']} 재주문 완료 (시장가)")
        else:
            print(f"[자동매매] {order['name']} 재주문 실패")


def monitor_positions():
    """
    장중 모니터링 - 1분 간격 호출
    - active 종목: 목표가/손절가 도달 시 매도
    - pending 종목: 현재가 <= 매수가면 active로 전환
    """
    if not is_enabled():
        return

    client  = KISClient()
    today   = date.today().isoformat()
    orders  = _get_pending_orders()

    if not orders:
        return

    for order in orders:
        symbol = order["symbol"]
        cur    = client.get_price(symbol)
        if cur is None:
            continue

        # pending 종목은 morning_reorder()에서 체결 확인 처리
        # monitor_positions()에서는 active 종목만 처리
        if order["status"] != "active":
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

        # ── 분할매수 2/3차 트리거 ──────────────────────────────────
        cfg = _cfg()
        split_budget = cfg["budget_per"] // 3

        if split_step == 1 and cur <= trigger2:
            add_qty = max(1, int(split_budget / cur))
            result  = client.buy_order(order["symbol"], int(cur), add_qty, market=True)
            if result["success"]:
                new_avg = (avg_price * qty + cur * add_qty) / (qty + add_qty)
                _update_order(order["id"],
                    split_step=2, split_qty=qty + add_qty,
                    avg_price=round(new_avg, 2), qty=qty + add_qty,
                )
                print(f"[자동매매] {order['name']} 2차 매수 {add_qty}주 @{cur:,.0f}")
                _send_admin(f"📥 <b>2차 분할매수</b>\n<b>{order['name']}</b> ₩{cur:,.0f} × {add_qty}주\n평균단가 ₩{new_avg:,.0f} | 손절 ₩{stop:,}")
            continue  # 분할매수 후 이번 루프는 매도 체크 스킵

        elif split_step == 2 and cur <= trigger3:
            add_qty = max(1, int(split_budget / cur))
            result  = client.buy_order(order["symbol"], int(cur), add_qty, market=True)
            if result["success"]:
                new_avg = (avg_price * qty + cur * add_qty) / (qty + add_qty)
                _update_order(order["id"],
                    split_step=3, split_qty=qty + add_qty,
                    avg_price=round(new_avg, 2), qty=qty + add_qty,
                )
                print(f"[자동매매] {order['name']} 3차 매수 {add_qty}주 @{cur:,.0f}")
                _send_admin(f"📥 <b>3차 분할매수 완료</b>\n<b>{order['name']}</b> ₩{cur:,.0f} × {add_qty}주\n평균단가 ₩{new_avg:,.0f} | 손절 ₩{stop:,}")
            continue  # 분할매수 후 이번 루프는 매도 체크 스킵

        # 목표가 도달
        if cur >= target:
            result = client.sell_order(symbol, target, qty, market=True)
            if result["success"]:
                ret = (cur - avg_price) / avg_price * 100  # 평균단가 기준 수익률
                _update_order(order["id"],
                    status="hit_target", exit_price=int(cur),
                    exit_date=today, return_pct=round(ret, 2)
                )
                print(f"[자동매매] {order['name']} 목표가 도달 → 매도 +{ret:.1f}%")
                _send_admin(
                    f"🎯 <b>목표가 달성!</b>\n"
                    f"<b>{order['name']}</b>\n"
                    f"평균단가 ₩{avg_price:,.0f} → 매도 ₩{cur:,.0f}\n"
                    f"수익률 <b>+{ret:.1f}%</b> 🎉"
                )

        # 손절가 도달
        elif cur <= stop:
            result = client.sell_order(symbol, stop, qty, market=True)
            if result["success"]:
                ret = (cur - avg_price) / avg_price * 100  # 평균단가 기준 손실률
                _update_order(order["id"],
                    status="hit_stop", exit_price=int(cur),
                    exit_date=today, return_pct=round(ret, 2)
                )
                print(f"[자동매매] {order['name']} 손절가 도달 → 시장가 매도 {ret:.1f}%")
                _send_admin(
                    f"🛑 <b>손절 실행</b>\n"
                    f"<b>{order['name']}</b>\n"
                    f"평균단가 ₩{avg_price:,.0f} → 손절 ₩{cur:,.0f}\n"
                    f"손실 <b>{ret:.1f}%</b>"
                )


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
                if d["cur"] and d["avg_p"]:
                    ret    = (d["cur"] - d["avg_p"]) / d["avg_p"] * 100
                    pnl    = int((d["cur"] - d["avg_p"]) * d["qty"])
                    p_sign = "+" if pnl >= 0 else ""
                    if d["target"] and d["stop"] and d["target"] > d["stop"]:
                        if ret >= 0:
                            ratio  = min((d["cur"] - d["avg_p"]) / (d["target"] - d["avg_p"]), 1.0)
                            filled = round(ratio * 8)
                            bar    = "🟩" * filled + "⬜" * (8 - filled)
                        else:
                            ratio  = min((d["avg_p"] - d["cur"]) / (d["avg_p"] - d["stop"]), 1.0)
                            filled = round(ratio * 8)
                            bar    = "🟥" * filled + "⬜" * (8 - filled)
                    else:
                        bar = "⬜" * 8
                    to_stop = (d["cur"] - d["stop"]) / d["cur"] * 100 if d["stop"] else 0
                    cur_line = (
                        f"\n  {bar}  <b>{ret:+.1f}%  {p_sign}₩{pnl:,}</b>"
                        f"\n  현재가  ₩{d['cur']:,.0f}"
                        f"\n  🎯 ₩{d['target']:,}  🛑 ₩{d['stop']:,}  (손절까지 {to_stop:.1f}%)"
                    )

                lines.append(
                    f"\n📌 <b>{d['name']}</b>  <i>{d['days']}일째</i>  {split_icons}{split_remain}"
                    f"\n  평균단가  ₩{d['avg_p']:,.0f} × {d['qty']}주"
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
