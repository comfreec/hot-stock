"""
멀티유저 자동매매 모듈 v1.0
- 유저별 KIS API 키 암호화 저장 (DB)
- 텔레그램 봇 커맨드로 등록/관리
- 기존 auto_trader.py는 그대로 유지 (1인용 폴백)

텔레그램 커맨드:
  /register <app_key> <app_secret> <계좌번호> [mock=1]
  /settings [budget=300000] [max_stocks=3] [mock=0]
  /status   → 내 포트폴리오 조회
  /stop     → 자동매매 중지
  /resume   → 자동매매 재개
  /unregister → 계정 삭제
"""
import os
import sqlite3
import requests
import json
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# ── 암호화 ────────────────────────────────────────────────────────
def _get_cipher():
    """Fernet 대칭 암호화 - ENCRYPT_KEY 환경변수 필수"""
    try:
        from cryptography.fernet import Fernet
        key = os.environ.get("ENCRYPT_KEY", "")
        if not key:
            # 키 없으면 자동 생성 후 출력 (최초 1회)
            key = Fernet.generate_key().decode()
            print(f"[멀티유저] ENCRYPT_KEY 없음 - 생성된 키를 환경변수에 등록하세요:\nENCRYPT_KEY={key}")
            return None
        return Fernet(key.encode() if isinstance(key, str) else key)
    except ImportError:
        print("[멀티유저] cryptography 패키지 없음: pip install cryptography")
        return None


def _encrypt(text: str) -> str:
    cipher = _get_cipher()
    if not cipher or not text:
        return text
    return cipher.encrypt(text.encode()).decode()


def _decrypt(token: str) -> str:
    cipher = _get_cipher()
    if not cipher or not token:
        return token
    try:
        return cipher.decrypt(token.encode()).decode()
    except Exception:
        return ""


# ── DB ────────────────────────────────────────────────────────────
def _get_db_path() -> str:
    env_path = os.environ.get("DB_PATH", "")
    if env_path:
        return env_path
    if os.path.isdir("/data"):
        return "/data/scan_cache.db"
    # 항상 이 파일 기준 절대경로로 고정
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan_cache.db")


def _get_conn():
    conn = sqlite3.connect(_get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _migrate(conn)
    return conn


def _migrate(conn):
    """테이블 생성 및 마이그레이션"""
    # users 테이블
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trader_users (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id       TEXT NOT NULL UNIQUE,
            app_key_enc   TEXT NOT NULL,
            app_secret_enc TEXT NOT NULL,
            account       TEXT NOT NULL,
            mock          INTEGER DEFAULT 1,
            budget_per    INTEGER DEFAULT 300000,
            max_stocks    INTEGER DEFAULT 3,
            max_days      INTEGER DEFAULT 5,
            is_active     INTEGER DEFAULT 1,
            created_at    TEXT NOT NULL,
            updated_at    TEXT
        )
    """)
    # trade_orders_multi 테이블 (기존 trade_orders와 분리)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_orders_multi (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            alert_date    TEXT NOT NULL,
            symbol        TEXT NOT NULL,
            name          TEXT NOT NULL,
            entry_price   INTEGER NOT NULL,
            target_price  INTEGER NOT NULL,
            stop_price    INTEGER NOT NULL,
            qty           INTEGER NOT NULL,
            order_no      TEXT,
            status        TEXT DEFAULT 'pending',
            exit_price    INTEGER,
            exit_date     TEXT,
            return_pct    REAL,
            created_at    TEXT NOT NULL,
            split_step    INTEGER DEFAULT 1,
            split_qty     INTEGER DEFAULT 0,
            avg_price     REAL DEFAULT 0,
            base_price    INTEGER DEFAULT 0,
            trigger2      INTEGER DEFAULT 0,
            trigger3      INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES trader_users(user_id)
        )
    """)
    conn.commit()


# ── 유저 관리 ─────────────────────────────────────────────────────
def register_user(chat_id: str, app_key: str, app_secret: str, account: str, mock: bool = True) -> str:
    """유저 등록 또는 업데이트"""
    conn = _get_conn()
    try:
        enc_key    = _encrypt(app_key)
        enc_secret = _encrypt(app_secret)
        now        = datetime.now(KST).isoformat()
        existing   = conn.execute(
            "SELECT user_id FROM trader_users WHERE chat_id=?", (chat_id,)
        ).fetchone()
        if existing:
            conn.execute("""
                UPDATE trader_users
                SET app_key_enc=?, app_secret_enc=?, account=?, mock=?,
                    is_active=1, updated_at=?
                WHERE chat_id=?
            """, (enc_key, enc_secret, account, int(mock), now, chat_id))
            conn.commit()
            return "updated"
        else:
            conn.execute("""
                INSERT INTO trader_users
                (chat_id, app_key_enc, app_secret_enc, account, mock, created_at)
                VALUES (?,?,?,?,?,?)
            """, (chat_id, enc_key, enc_secret, account, int(mock), now))
            conn.commit()
            return "created"
    finally:
        conn.close()


def get_user(chat_id: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM trader_users WHERE chat_id=?", (chat_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    u = dict(row)
    u["app_key"]    = _decrypt(u.pop("app_key_enc", ""))
    u["app_secret"] = _decrypt(u.pop("app_secret_enc", ""))
    return u


def get_active_users() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM trader_users WHERE is_active=1"
    ).fetchall()
    conn.close()
    users = []
    for row in rows:
        u = dict(row)
        u["app_key"]    = _decrypt(u.pop("app_key_enc", ""))
        u["app_secret"] = _decrypt(u.pop("app_secret_enc", ""))
        users.append(u)
    return users


def update_user_settings(chat_id: str, **kwargs) -> bool:
    allowed = {"budget_per", "max_stocks", "max_days", "mock", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    conn = _get_conn()
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [datetime.now(KST).isoformat(), chat_id]
    conn.execute(f"UPDATE trader_users SET {sets}, updated_at=? WHERE chat_id=?", vals)
    conn.commit()
    conn.close()
    return True


def delete_user(chat_id: str):
    conn = _get_conn()
    conn.execute("UPDATE trader_users SET is_active=0 WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()


# ── KIS 클라이언트 (유저별) ───────────────────────────────────────
from auto_trader import KISClient as _BaseKISClient, round_to_tick, _calc_split_triggers, _get_ma240


class UserKISClient(_BaseKISClient):
    """유저 dict 기반 KIS 클라이언트"""
    def __init__(self, user: dict):
        self.app_key    = user["app_key"]
        self.app_secret = user["app_secret"]
        self.account    = user["account"]
        self.mock       = bool(user.get("mock", 1))
        self.base       = self.MOCK_BASE if self.mock else self.REAL_BASE
        self._token     = None
        self._token_exp = None


def _send_user(chat_id: str, message: str):
    """특정 유저에게 텔레그램 DM"""
    try:
        token = os.environ.get("TELEGRAM_TOKEN", "")
        if not token:
            return
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"[멀티유저] 텔레그램 오류 ({chat_id}): {e}")


# ── 주문 관리 ─────────────────────────────────────────────────────
def _get_pending_orders(user_id: int) -> list:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT id, alert_date, symbol, name, entry_price, target_price, stop_price,
               qty, order_no, status, split_step, split_qty, avg_price, base_price,
               trigger2, trigger3
        FROM trade_orders_multi
        WHERE user_id=? AND status IN ('pending', 'active')
        ORDER BY alert_date ASC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _save_order(user_id, alert_date, symbol, name, entry_price, target_price,
                stop_price, qty, order_no, split_step=1, base_price=0, trigger2=0, trigger3=0):
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM trade_orders_multi WHERE user_id=? AND symbol=? AND status IN ('pending','active')",
        (user_id, symbol)
    ).fetchone()
    if existing:
        conn.close()
        return
    conn.execute("""
        INSERT INTO trade_orders_multi
        (user_id, alert_date, symbol, name, entry_price, target_price, stop_price,
         qty, order_no, status, split_step, split_qty, avg_price, base_price,
         trigger2, trigger3, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,'pending',?,?,?,?,?,?,?)
    """, (user_id, alert_date, symbol, name, entry_price, target_price, stop_price,
          qty, order_no, split_step, qty, float(entry_price),
          base_price or entry_price, int(trigger2), int(trigger3),
          datetime.now(KST).isoformat()))
    conn.commit()
    conn.close()


def _update_order(order_id: int, **kwargs):
    conn = _get_conn()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [order_id]
    conn.execute(f"UPDATE trade_orders_multi SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


# ── 핵심 함수 (유저별) ────────────────────────────────────────────
def place_orders(results: list, user: dict):
    """스캔 결과 기반 유저별 매수 주문"""
    user_id  = user["user_id"]
    chat_id  = user["chat_id"]
    mock     = bool(user.get("mock", 1))
    mock_tag = "[모의] " if mock else ""
    budget   = int(user.get("budget_per", 300000))
    max_s    = int(user.get("max_stocks", 3))
    today    = date.today().isoformat()

    client  = UserKISClient(user)
    pending = _get_pending_orders(user_id)
    active_count = len(pending)

    if active_count >= max_s:
        return

    balance  = client.get_balance()
    cash     = balance.get("cash", 0)
    holdings = balance.get("holdings", {})

    if cash < budget * 0.8:
        _send_user(chat_id, f"⚠️ 예수금 부족 (₩{cash:,.0f}) - 자동매매 중단")
        return

    slots  = max_s - active_count
    budget = min(budget, int(cash / slots)) if slots > 0 else budget
    ordered = 0

    for r in results:
        if ordered >= slots:
            break

        symbol = r.get("symbol", "")
        name   = r.get("name", symbol)
        code   = symbol.replace(".KS", "").replace(".KQ", "")

        if code in holdings:
            continue
        if any(o["symbol"] == symbol for o in pending):
            continue

        # 가격 레벨 조회
        lv = {}
        try:
            from cache_db import _get_conn as _db_conn
            _conn = _db_conn()
            _row = _conn.execute(
                "SELECT entry_price, target_price, stop_price FROM alert_history "
                "WHERE symbol=? ORDER BY id DESC LIMIT 1", (symbol,)
            ).fetchone()
            _conn.close()
            if _row:
                lv = {"entry": _row[0], "target": _row[1], "stop": _row[2]}
        except:
            pass

        if not all(lv.get(k) for k in ("entry", "target", "stop")):
            continue

        entry  = int(lv["entry"])
        target = int(lv["target"])
        stop   = int(lv["stop"])
        qty    = max(1, int(budget / entry) // 3)
        actual_cost = entry * qty

        if actual_cost > cash:
            continue

        result = client.buy_order(symbol, entry, qty, market=True)
        if result["success"]:
            order_no = result.get("order_no", "")
            ma240    = _get_ma240(symbol)
            t2, t3   = _calc_split_triggers(entry, ma240) if ma240 else (int(entry * 0.98), int(entry * 0.96))
            _save_order(user_id, today, symbol, name, entry, target, stop, qty, order_no,
                        split_step=1, base_price=entry, trigger2=t2, trigger3=t3)
            conn = _get_conn()
            conn.execute(
                "UPDATE trade_orders_multi SET status='active' WHERE user_id=? AND symbol=? AND alert_date=?",
                (user_id, symbol, today)
            )
            conn.commit()
            conn.close()
            cash -= actual_cost
            ordered += 1

            t2_pct = (t2 / entry - 1) * 100
            t3_pct = (t3 / entry - 1) * 100
            _send_user(chat_id,
                f"🤖 {mock_tag}<b>자동매수 주문</b>\n"
                f"<b>{name}</b> ({symbol})\n"
                f"📍 1차 매수: ₩{entry:,} × {qty}주\n"
                f"🎯 목표가: ₩{target:,}\n"
                f"🛑 손절가: ₩{stop:,}\n"
                f"💰 주문금액: ₩{actual_cost:,}\n"
                f"\n📋 <b>분할매수 미리보기</b>\n"
                f"  2차: ₩{t2:,} ({t2_pct:.1f}%)\n"
                f"  3차: ₩{t3:,} ({t3_pct:.1f}%)"
            )


def morning_reorder(user: dict):
    """미체결 재주문 (유저별)"""
    user_id = user["user_id"]
    chat_id = user["chat_id"]
    max_days = int(user.get("max_days", 5))
    today   = date.today().isoformat()
    client  = UserKISClient(user)
    pending = _get_pending_orders(user_id)

    for order in pending:
        if order["status"] != "pending":
            continue

        alert_dt     = date.fromisoformat(order["alert_date"])
        days_elapsed = (date.today() - alert_dt).days

        # 만료 처리
        if days_elapsed >= max_days:
            if order.get("order_no"):
                client.cancel_order(order["order_no"], order["symbol"], order["qty"])
            _update_order(order["id"], status="expired", exit_date=today)
            _send_user(chat_id, f"⏰ <b>자동매매 만료</b>\n<b>{order['name']}</b> - {max_days}일 미체결로 주문 취소")
            continue

        # 당일 체결 확인
        if days_elapsed == 0:
            if order.get("order_no"):
                status = client.get_order_status(order["order_no"], order["symbol"])
                if status == "filled":
                    _update_order(order["id"], status="active")
                    _send_user(chat_id, f"✅ <b>매수 체결 확인</b>\n<b>{order['name']}</b> ₩{order['entry_price']:,} × {order['qty']}주")
            continue

        # 전날 미체결 → 재주문
        if order.get("order_no"):
            status = client.get_order_status(order["order_no"], order["symbol"])
            if status == "filled":
                _update_order(order["id"], status="active")
                _send_user(chat_id, f"✅ <b>매수 체결 확인</b>\n<b>{order['name']}</b> ₩{order['entry_price']:,} × {order['qty']}주")
                continue
            client.cancel_order(order["order_no"], order["symbol"], order["qty"])

        result = client.buy_order(order["symbol"], order["entry_price"], order["qty"], market=True)
        if result["success"]:
            _update_order(order["id"], alert_date=today, order_no=result.get("order_no", ""))


def monitor_positions(user: dict):
    """장중 모니터링 (유저별)"""
    user_id   = user["user_id"]
    chat_id   = user["chat_id"]
    budget    = int(user.get("budget_per", 300000))
    today     = date.today().isoformat()
    client    = UserKISClient(user)
    orders    = _get_pending_orders(user_id)

    if not orders:
        return

    split_budget = budget // 3

    for order in orders:
        if order["status"] != "active":
            continue

        symbol     = order["symbol"]
        cur        = client.get_price(symbol)
        if cur is None:
            continue

        entry      = order["entry_price"]
        target     = order["target_price"]
        stop       = order["stop_price"]
        qty        = order["qty"]
        split_step = order.get("split_step", 1)
        avg_price  = order.get("avg_price", entry) or entry
        trigger2   = order.get("trigger2") or int(entry * 0.98)
        trigger3   = order.get("trigger3") or int(entry * 0.96)

        # 2차 분할매수
        if split_step == 1 and cur <= trigger2:
            add_qty = max(1, int(split_budget / cur))
            result  = client.buy_order(symbol, int(cur), add_qty, market=True)
            if result["success"]:
                new_avg = (avg_price * qty + cur * add_qty) / (qty + add_qty)
                _update_order(order["id"], split_step=2, split_qty=qty + add_qty,
                              avg_price=round(new_avg, 2), qty=qty + add_qty)
                _send_user(chat_id,
                    f"📥 <b>2차 분할매수</b>\n<b>{order['name']}</b> ₩{cur:,.0f} × {add_qty}주\n"
                    f"평균단가 ₩{new_avg:,.0f} | 손절 ₩{stop:,}")
            continue

        # 3차 분할매수
        elif split_step == 2 and cur <= trigger3:
            add_qty = max(1, int(split_budget / cur))
            result  = client.buy_order(symbol, int(cur), add_qty, market=True)
            if result["success"]:
                new_avg = (avg_price * qty + cur * add_qty) / (qty + add_qty)
                _update_order(order["id"], split_step=3, split_qty=qty + add_qty,
                              avg_price=round(new_avg, 2), qty=qty + add_qty)
                _send_user(chat_id,
                    f"📥 <b>3차 분할매수 완료</b>\n<b>{order['name']}</b> ₩{cur:,.0f} × {add_qty}주\n"
                    f"평균단가 ₩{new_avg:,.0f} | 손절 ₩{stop:,}")
            continue

        # 목표가 도달
        if cur >= target:
            result = client.sell_order(symbol, target, qty, market=True)
            if result["success"]:
                ret = (cur - avg_price) / avg_price * 100
                _update_order(order["id"], status="hit_target", exit_price=int(cur),
                              exit_date=today, return_pct=round(ret, 2))
                _send_user(chat_id,
                    f"🎯 <b>목표가 달성!</b>\n<b>{order['name']}</b>\n"
                    f"평균단가 ₩{avg_price:,.0f} → 매도 ₩{cur:,.0f}\n"
                    f"수익률 <b>+{ret:.1f}%</b> 🎉")

        # 손절가 도달
        elif cur <= stop:
            result = client.sell_order(symbol, stop, qty, market=True)
            if result["success"]:
                ret = (cur - avg_price) / avg_price * 100
                _update_order(order["id"], status="hit_stop", exit_price=int(cur),
                              exit_date=today, return_pct=round(ret, 2))
                _send_user(chat_id,
                    f"🛑 <b>손절 실행</b>\n<b>{order['name']}</b>\n"
                    f"평균단가 ₩{avg_price:,.0f} → 손절 ₩{cur:,.0f}\n"
                    f"손실 <b>{ret:.1f}%</b>")


# ── 텔레그램 봇 커맨드 처리 ──────────────────────────────────────
def handle_bot_command(chat_id: str, text: str):
    """
    텔레그램 봇 메시지 처리
    scheduler.py의 봇 폴링 루프에서 호출
    """
    text = text.strip()
    parts = text.split()
    cmd = parts[0].lower() if parts else ""

    # /register <app_key> <app_secret> <계좌번호> [mock=1]
    if cmd == "/register":
        if len(parts) < 4:
            _send_user(chat_id,
                "📋 <b>등록 방법</b>\n"
                "/register <b>앱키</b> <b>앱시크릿</b> <b>계좌번호</b> [mock=1]\n\n"
                "예시:\n"
                "<code>/register PSabc123... xyzSecret... 50123456-01 mock=0</code>\n\n"
                "⚠️ 계좌번호 형식: 12345678-01")
            return

        app_key    = parts[1]
        app_secret = parts[2]
        account    = parts[3]
        mock       = True
        for p in parts[4:]:
            if p.startswith("mock="):
                mock = p.split("=")[1] != "0"

        result = register_user(chat_id, app_key, app_secret, account, mock)
        mode   = "모의투자" if mock else "실전투자"
        action = "업데이트" if result == "updated" else "등록"
        _send_user(chat_id,
            f"✅ <b>자동매매 {action} 완료</b>\n"
            f"계좌: {account}\n"
            f"모드: {mode}\n\n"
            f"설정 변경: /settings budget=300000 max_stocks=3\n"
            f"현황 조회: /status\n"
            f"중지: /stop")

    # /settings [key=value ...]
    elif cmd == "/settings":
        user = get_user(chat_id)
        if not user:
            _send_user(chat_id, "❌ 먼저 /register 로 등록해주세요.")
            return

        updates = {}
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                if k in ("budget", "budget_per"):
                    updates["budget_per"] = int(v)
                elif k in ("max_stocks", "stocks"):
                    updates["max_stocks"] = int(v)
                elif k in ("max_days", "days"):
                    updates["max_days"] = int(v)
                elif k == "mock":
                    updates["mock"] = int(v)

        if not updates:
            # 현재 설정 표시
            mode = "모의투자" if user.get("mock") else "실전투자"
            _send_user(chat_id,
                f"⚙️ <b>현재 설정</b>\n"
                f"모드: {mode}\n"
                f"종목당 예산: ₩{user.get('budget_per', 300000):,}\n"
                f"최대 보유 종목: {user.get('max_stocks', 3)}개\n"
                f"미체결 만료: {user.get('max_days', 5)}일\n\n"
                f"변경 예시:\n"
                f"<code>/settings budget=500000 max_stocks=5 mock=0</code>")
            return

        update_user_settings(chat_id, **updates)
        lines = []
        if "budget_per"  in updates: lines.append(f"종목당 예산: ₩{updates['budget_per']:,}")
        if "max_stocks"  in updates: lines.append(f"최대 종목: {updates['max_stocks']}개")
        if "max_days"    in updates: lines.append(f"만료일: {updates['max_days']}일")
        if "mock"        in updates: lines.append(f"모드: {'모의' if updates['mock'] else '실전'}투자")
        _send_user(chat_id, "✅ <b>설정 업데이트</b>\n" + "\n".join(lines))

    # /status
    elif cmd == "/status":
        user = get_user(chat_id)
        if not user:
            _send_user(chat_id, "❌ 먼저 /register 로 등록해주세요.")
            return
        if not user.get("is_active"):
            _send_user(chat_id, "⏸ 자동매매가 중지 상태입니다. /resume 으로 재개하세요.")
            return

        try:
            client  = UserKISClient(user)
            balance = client.get_balance()
            cash    = balance.get("cash", 0)
            orders  = _get_pending_orders(user["user_id"])
            active  = [o for o in orders if o["status"] == "active"]
            pending = [o for o in orders if o["status"] == "pending"]
            mode    = "모의" if user.get("mock") else "실전"

            lines = [f"📊 <b>내 자동매매 현황</b>  [{mode}]", f"예수금: ₩{cash:,.0f}"]
            if active:
                lines.append(f"\n🟢 <b>보유 중</b> ({len(active)}종목)")
                for o in active:
                    cur = client.get_price(o["symbol"])
                    avg = o.get("avg_price") or o["entry_price"]
                    if cur and avg:
                        ret = (cur - avg) / avg * 100
                        lines.append(f"  📌 {o['name']}  {ret:+.1f}%  (₩{cur:,.0f})")
                    else:
                        lines.append(f"  📌 {o['name']}  ₩{o['entry_price']:,}")
            if pending:
                lines.append(f"\n⏳ <b>매수 대기</b> ({len(pending)}종목)")
                for o in pending:
                    lines.append(f"  🔵 {o['name']}  ₩{o['entry_price']:,}")
            if not active and not pending:
                lines.append("\n보유/대기 종목 없음")

            _send_user(chat_id, "\n".join(lines))
        except Exception as e:
            _send_user(chat_id, f"❌ 조회 오류: {e}")

    # /stop
    elif cmd == "/stop":
        user = get_user(chat_id)
        if not user:
            _send_user(chat_id, "❌ 등록된 계정이 없습니다.")
            return
        update_user_settings(chat_id, is_active=0)
        _send_user(chat_id, "⏸ <b>자동매매 중지</b>\n기존 보유 종목 모니터링은 계속됩니다.\n재개: /resume")

    # /resume
    elif cmd == "/resume":
        user = get_user(chat_id)
        if not user:
            _send_user(chat_id, "❌ 먼저 /register 로 등록해주세요.")
            return
        update_user_settings(chat_id, is_active=1)
        _send_user(chat_id, "▶️ <b>자동매매 재개</b>\n다음 스캔 결과부터 자동 매수됩니다.")

    # /unregister
    elif cmd == "/unregister":
        user = get_user(chat_id)
        if not user:
            _send_user(chat_id, "❌ 등록된 계정이 없습니다.")
            return
        delete_user(chat_id)
        _send_user(chat_id, "🗑 <b>계정 삭제 완료</b>\n자동매매가 중지되었습니다.")

    # /help
    elif cmd in ("/help", "/start"):
        _send_user(chat_id,
            "🤖 <b>자동매매 봇 커맨드</b>\n\n"
            "/register - KIS API 키 등록\n"
            "/settings - 설정 조회/변경\n"
            "/status   - 포트폴리오 현황\n"
            "/stop     - 자동매매 중지\n"
            "/resume   - 자동매매 재개\n"
            "/unregister - 계정 삭제")


# ── 스케줄러용 진입점 ─────────────────────────────────────────────
def run_all_users_morning_reorder():
    """09:05 - 전체 활성 유저 재주문"""
    for user in get_active_users():
        try:
            morning_reorder(user)
        except Exception as e:
            print(f"[멀티유저] morning_reorder 오류 ({user.get('chat_id')}): {e}")


def run_all_users_place_orders(results: list):
    """스캔 결과 → 전체 활성 유저 매수 주문"""
    for user in get_active_users():
        try:
            place_orders(results, user)
        except Exception as e:
            print(f"[멀티유저] place_orders 오류 ({user.get('chat_id')}): {e}")


def run_all_users_monitor():
    """장중 모니터링 - 전체 활성 유저"""
    for user in get_active_users():
        try:
            monitor_positions(user)
        except Exception as e:
            print(f"[멀티유저] monitor 오류 ({user.get('chat_id')}): {e}")


def poll_bot_commands():
    """
    텔레그램 봇 업데이트 폴링 (스케줄러 루프에서 30초마다 호출)
    getUpdates long-polling 방식
    """
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not token:
        return

    offset_file = "/data/.bot_offset" if os.path.isdir("/data") else ".bot_offset"
    offset = 0
    try:
        with open(offset_file) as f:
            offset = int(f.read().strip())
    except:
        pass

    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": offset, "timeout": 5, "limit": 20},
            timeout=10
        )
        if not resp.ok:
            return
        updates = resp.json().get("result", [])
        for upd in updates:
            offset = upd["update_id"] + 1
            msg = upd.get("message", {})
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text    = msg.get("text", "")
            if chat_id and text and text.startswith("/"):
                handle_bot_command(chat_id, text)

        if updates:
            with open(offset_file, "w") as f:
                f.write(str(offset))
    except Exception as e:
        print(f"[멀티유저] 봇 폴링 오류: {e}")
