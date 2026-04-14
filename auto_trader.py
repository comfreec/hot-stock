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


def _send_admin(message: str):
    """관리자(본인)에게만 텔레그램 DM 전송"""
    try:
        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("KIS_ADMIN_CHAT_ID", "1663019049")
        if not token:
            return
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
    except:
        pass


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

    def buy_order(self, symbol: str, price: int, qty: int) -> dict:
        """지정가 매수 주문"""
        code  = symbol.replace(".KS", "").replace(".KQ", "")
        acct_no = self.account.split("-")[0]
        acct_cd = self.account.split("-")[1] if "-" in self.account else "01"
        tr_id = "VTTC0802U" if self.mock else "TTTC0802U"
        try:
            resp = requests.post(
                f"{self.base}/uapi/domestic-stock/v1/trading/order-cash",
                headers=self._headers(tr_id),
                json={
                    "CANO": acct_no, "ACNT_PRDT_CD": acct_cd,
                    "PDNO": code, "ORD_DVSN": "00",  # 00=지정가
                    "ORD_QTY": str(qty), "ORD_UNPR": str(price),
                },
                timeout=10
            )
            resp.raise_for_status()
            result = resp.json()
            order_no = result.get("output", {}).get("ODNO", "")
            print(f"[KIS] 매수 주문 {code} {qty}주 @{price:,}원 → 주문번호 {order_no}")
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

    def cancel_order(self, order_no: str, symbol: str, qty: int) -> bool:
        """미체결 주문 취소"""
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
            created_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _get_pending_orders() -> list:
    conn = _get_trade_conn()
    rows = conn.execute("""
        SELECT id, alert_date, symbol, name, entry_price, target_price, stop_price, qty, order_no, status
        FROM trade_orders WHERE status IN ('pending', 'active')
        ORDER BY alert_date ASC
    """).fetchall()
    conn.close()
    keys = ["id","alert_date","symbol","name","entry_price","target_price","stop_price","qty","order_no","status"]
    return [dict(zip(keys, r)) for r in rows]


def _update_order(order_id: int, **kwargs):
    conn = _get_trade_conn()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [order_id]
    conn.execute(f"UPDATE trade_orders SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def _save_order(alert_date, symbol, name, entry_price, target_price, stop_price, qty, order_no):
    conn = _get_trade_conn()
    # 이미 pending/active 상태인 종목 중복 방지
    existing = conn.execute(
        "SELECT id FROM trade_orders WHERE symbol=? AND status IN ('pending','active')", (symbol,)
    ).fetchone()
    if existing:
        conn.close()
        return
    conn.execute("""
        INSERT INTO trade_orders
        (alert_date, symbol, name, entry_price, target_price, stop_price, qty, order_no, status, created_at)
        VALUES (?,?,?,?,?,?,?,?,'pending',?)
    """, (alert_date, symbol, name, entry_price, target_price, stop_price, qty, order_no,
          datetime.now().isoformat()))
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

    slots = cfg["max_stocks"] - active_count
    budget = cfg["budget_per"]

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

        # 가격 레벨
        from cache_db import _get_conn as _db_conn
        lv = {}
        try:
            _conn = _db_conn()
            _row = _conn.execute(
                "SELECT entry_price, target_price, stop_price FROM alert_history "
                "WHERE symbol=? AND alert_date=? ORDER BY id DESC LIMIT 1",
                (symbol, today)
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

        if cash < budget * 0.5:
            print(f"[자동매매] 예수금 부족 ({cash:,.0f}원) - 주문 중단")
            break

        qty = max(1, int(budget / entry))
        actual_cost = entry * qty

        if actual_cost > cash:
            qty = max(1, int(cash / entry))
            actual_cost = entry * qty

        result = client.buy_order(symbol, entry, qty)
        if result["success"]:
            order_no = result.get("order_no", "")
            _save_order(today, symbol, name, entry, target, stop, qty, order_no)
            cash -= actual_cost
            ordered += 1

            # 텔레그램 알림
            try:
                from telegram_alert import send_telegram
                mock_tag = "[모의] " if cfg["mock"] else ""
                _send_admin(
                    f"🤖 {mock_tag}<b>자동매수 주문</b>\n"
                    f"<b>{name}</b> ({symbol})\n"
                    f"📍 매수가: ₩{entry:,}  ×  {qty}주\n"
                    f"🎯 목표가: ₩{target:,}\n"
                    f"🛑 손절가: ₩{stop:,}\n"
                    f"💰 주문금액: ₩{actual_cost:,}"
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
            # 오늘 처음 주문한 것 - 재주문 불필요
            continue

        # 전날 주문 취소 후 재주문
        if order.get("order_no"):
            client.cancel_order(order["order_no"], order["symbol"], order["qty"])

        result = client.buy_order(order["symbol"], order["entry_price"], order["qty"])
        if result["success"]:
            _update_order(order["id"],
                alert_date=today,
                order_no=result.get("order_no", ""),
            )
            print(f"[자동매매] {order['name']} 재주문 완료 @{order['entry_price']:,}원")
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

        # pending → active 전환 (현재가가 매수가 이하로 내려오면 체결로 간주)
        if order["status"] == "pending":
            if cur <= order["entry_price"]:
                _update_order(order["id"], status="active")
                order["status"] = "active"
                print(f"[자동매매] {order['name']} 체결 확인 → active")
                try:
                    from telegram_alert import send_telegram
                    _send_admin(
                        f"✅ <b>매수 체결</b>\n"
                        f"<b>{order['name']}</b> ₩{order['entry_price']:,} × {order['qty']}주"
                    )
                except:
                    pass

        if order["status"] != "active":
            continue

        entry  = order["entry_price"]
        target = order["target_price"]
        stop   = order["stop_price"]
        qty    = order["qty"]

        # 목표가 도달
        if cur >= target:
            result = client.sell_order(symbol, target, qty, market=True)  # 목표가도 시장가
            if result["success"]:
                ret = (target - entry) / entry * 100
                _update_order(order["id"],
                    status="hit_target", exit_price=target,
                    exit_date=today, return_pct=round(ret, 2)
                )
                print(f"[자동매매] {order['name']} 목표가 도달 → 매도 +{ret:.1f}%")
                try:
                    from telegram_alert import send_telegram
                    _send_admin(
                        f"🎯 <b>목표가 달성!</b>\n"
                        f"<b>{order['name']}</b>\n"
                        f"매수 ₩{entry:,} → 매도 ₩{target:,}\n"
                        f"수익률 <b>+{ret:.1f}%</b> 🎉"
                    )
                except:
                    pass

        # 손절가 도달
        elif cur <= stop:
            result = client.sell_order(symbol, stop, qty, market=True)  # 손절은 시장가
            if result["success"]:
                ret = (stop - entry) / entry * 100
                _update_order(order["id"],
                    status="hit_stop", exit_price=stop,
                    exit_date=today, return_pct=round(ret, 2)
                )
                print(f"[자동매매] {order['name']} 손절가 도달 → 시장가 매도 {ret:.1f}%")
                try:
                    from telegram_alert import send_telegram
                    _send_admin(
                        f"🛑 <b>손절 실행</b>\n"
                        f"<b>{order['name']}</b>\n"
                        f"매수 ₩{entry:,} → 손절 ₩{cur:,.0f}\n"
                        f"손실 <b>{ret:.1f}%</b>"
                    )
                except:
                    pass
