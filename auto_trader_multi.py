"""
ë©€?°ìœ ?€ ?ë™ë§¤ë§¤ ëª¨ë“ˆ v1.0
- ? ì?ë³?KIS API ???”í˜¸???€??(DB)
- ?”ë ˆê·¸ë¨ ë´?ì»¤ë§¨?œë¡œ ?±ë¡/ê´€ë¦?
- ê¸°ì¡´ auto_trader.py??ê·¸ë?ë¡?? ì? (1?¸ìš© ?´ë°±)

?”ë ˆê·¸ë¨ ì»¤ë§¨??
  /register <app_key> <app_secret> <ê³„ì¢Œë²ˆí˜¸> [mock=1]
  /settings [budget=300000] [max_stocks=3] [mock=0]
  /status   ?????¬íŠ¸?´ë¦¬??ì¡°íšŒ
  /stop     ???ë™ë§¤ë§¤ ì¤‘ì?
  /resume   ???ë™ë§¤ë§¤ ?¬ê°œ
  /unregister ??ê³„ì • ?? œ
"""
import os
import sqlite3
import requests
import json
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# ?€?€ ?”í˜¸???€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
def _get_cipher():
    """Fernet ?€ì¹??”í˜¸??- ENCRYPT_KEY ?˜ê²½ë³€???„ìˆ˜"""
    try:
        from cryptography.fernet import Fernet
        key = os.environ.get("ENCRYPT_KEY", "")
        if not key:
            # ???†ìœ¼ë©??ë™ ?ì„± ??ì¶œë ¥ (ìµœì´ˆ 1??
            key = Fernet.generate_key().decode()
            print(f"[ë©€?°ìœ ?€] ENCRYPT_KEY ?†ìŒ - ?ì„±???¤ë? ?˜ê²½ë³€?˜ì— ?±ë¡?˜ì„¸??\nENCRYPT_KEY={key}")
            return None
        return Fernet(key.encode() if isinstance(key, str) else key)
    except ImportError:
        print("[ë©€?°ìœ ?€] cryptography ?¨í‚¤ì§€ ?†ìŒ: pip install cryptography")
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


# ?€?€ DB ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
def _get_db_path() -> str:
    env_path = os.environ.get("DB_PATH", "")
    if env_path:
        return env_path
    if os.path.isdir("/data"):
        return "/data/scan_cache.db"
    # ??ƒ ???Œì¼ ê¸°ì? ?ˆë?ê²½ë¡œë¡?ê³ ì •
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan_cache.db")


def _get_conn():
    conn = sqlite3.connect(_get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _migrate(conn)
    return conn


def _migrate(conn):
    """?Œì´ë¸??ì„± ë°?ë§ˆì´ê·¸ë ˆ?´ì…˜"""
    # users ?Œì´ë¸?
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trader_users (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id       TEXT NOT NULL UNIQUE,
            name          TEXT DEFAULT '',
            app_key_enc   TEXT NOT NULL,
            app_secret_enc TEXT NOT NULL,
            account       TEXT NOT NULL,
            mock          INTEGER DEFAULT 1,
            budget_per    INTEGER DEFAULT 300000,
            max_stocks    INTEGER DEFAULT 10,
            max_days      INTEGER DEFAULT 7,
            is_active     INTEGER DEFAULT 1,
            contact       TEXT DEFAULT '',
            created_at    TEXT NOT NULL,
            updated_at    TEXT
        )
    """)
    # ê¸°ì¡´ DB ë§ˆì´ê·¸ë ˆ?´ì…˜
    existing = [r[1] for r in conn.execute("PRAGMA table_info(trader_users)").fetchall()]
    if "contact" not in existing:
        conn.execute("ALTER TABLE trader_users ADD COLUMN contact TEXT DEFAULT ''")
    if "name" not in existing:
        conn.execute("ALTER TABLE trader_users ADD COLUMN name TEXT DEFAULT ''")
    # trade_orders_multi ?Œì´ë¸?(ê¸°ì¡´ trade_orders?€ ë¶„ë¦¬)
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
            step2_price   REAL DEFAULT 0,
            step2_qty     INTEGER DEFAULT 0,
            step3_price   REAL DEFAULT 0,
            step3_qty     INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES trader_users(user_id)
        )
    """)
    conn.commit()
    # ê¸°ì¡´ DB ë§ˆì´ê·¸ë ˆ?´ì…˜
    existing_m = [r[1] for r in conn.execute("PRAGMA table_info(trade_orders_multi)").fetchall()]
    for col, typ, default in [
        ("step2_price","REAL","0"), ("step2_qty","INTEGER","0"),
        ("step3_price","REAL","0"), ("step3_qty","INTEGER","0"),
    ]:
        if col not in existing_m:
            conn.execute(f"ALTER TABLE trade_orders_multi ADD COLUMN {col} {typ} DEFAULT {default}")
    conn.commit()


# ?€?€ ? ì? ê´€ë¦??€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
def register_user(chat_id: str, app_key: str, app_secret: str, account: str,
                  mock: bool = True, contact: str = "", name: str = "") -> str:
    """? ì? ?±ë¡ ?ëŠ” ?…ë°?´íŠ¸"""
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
                    contact=?, name=?, is_active=1, updated_at=?
                WHERE chat_id=?
            """, (enc_key, enc_secret, account, int(mock), contact, name, now, chat_id))
            conn.commit()
            return "updated"
        else:
            conn.execute("""
                INSERT INTO trader_users
                (chat_id, name, app_key_enc, app_secret_enc, account, mock, contact, created_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (chat_id, name, enc_key, enc_secret, account, int(mock), contact, now))
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
    allowed = {"budget_per", "max_stocks", "max_days", "mock", "is_active", "contact", "name"}
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


# ?€?€ KIS ?´ë¼?´ì–¸??(? ì?ë³? ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
from auto_trader import KISClient as _BaseKISClient, round_to_tick, _calc_split_triggers, _get_ma240


class UserKISClient(_BaseKISClient):
    """? ì? dict ê¸°ë°˜ KIS ?´ë¼?´ì–¸??""
    def __init__(self, user: dict):
        self.app_key    = user["app_key"]
        self.app_secret = user["app_secret"]
        self.account    = user["account"]
        self.mock       = bool(user.get("mock", 1))
        self.base       = self.MOCK_BASE if self.mock else self.REAL_BASE
        self._token     = None
        self._token_exp = None


def _send_user(chat_id: str, message: str):
    """?¹ì • ? ì??ê²Œ ?”ë ˆê·¸ë¨ DM"""
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
        print(f"[ë©€?°ìœ ?€] ?”ë ˆê·¸ë¨ ?¤ë¥˜ ({chat_id}): {e}")


# ?€?€ ì£¼ë¬¸ ê´€ë¦??€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
def _get_pending_orders(user_id: int) -> list:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT id, alert_date, symbol, name, entry_price, target_price, stop_price,
               qty, order_no, status, split_step, split_qty, avg_price, base_price,
               trigger2, trigger3, step2_price, step2_qty, step3_price, step3_qty
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


# ?€?€ ?µì‹¬ ?¨ìˆ˜ (? ì?ë³? ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
def place_orders(results: list, user: dict):
    """?¤ìº” ê²°ê³¼ ê¸°ë°˜ ? ì?ë³?ë§¤ìˆ˜ ì£¼ë¬¸"""
    user_id  = user["user_id"]
    chat_id  = user["chat_id"]
    mock     = bool(user.get("mock", 1))
    mock_tag = "[ëª¨ì˜] " if mock else ""
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
        _send_user(chat_id, f"? ï¸ ?ˆìˆ˜ê¸?ë¶€ì¡?(??cash:,.0f}) - ?ë™ë§¤ë§¤ ì¤‘ë‹¨")
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

        # ê°€ê²??ˆë²¨ ì¡°íšŒ
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
                f"?¤– {mock_tag}<b>?ë™ë§¤ìˆ˜ ì£¼ë¬¸</b>\n"
                f"<b>{name}</b> ({symbol})\n"
                f"?“ 1ì°?ë§¤ìˆ˜: ??entry:,} Ã— {qty}ì£?n"
                f"?¯ ëª©í‘œê°€: ??target:,}\n"
                f"?›‘ ?ì ˆê°€: ??stop:,}\n"
                f"?’° ì£¼ë¬¸ê¸ˆì•¡: ??actual_cost:,}\n"
                f"\n?“‹ <b>ë¶„í• ë§¤ìˆ˜ ë¯¸ë¦¬ë³´ê¸°</b>\n"
                f"  2ì°? ??t2:,} ({t2_pct:.1f}%)\n"
                f"  3ì°? ??t3:,} ({t3_pct:.1f}%)"
            )


def morning_reorder(user: dict):
    """ë¯¸ì²´ê²??¬ì£¼ë¬?(? ì?ë³?"""
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

        # ë§Œë£Œ ì²˜ë¦¬
        if days_elapsed >= max_days:
            if order.get("order_no"):
                client.cancel_order(order["order_no"], order["symbol"], order["qty"])
            _update_order(order["id"], status="expired", exit_date=today)
            _send_user(chat_id, f"??<b>?ë™ë§¤ë§¤ ë§Œë£Œ</b>\n<b>{order['name']}</b> - {max_days}??ë¯¸ì²´ê²°ë¡œ ì£¼ë¬¸ ì·¨ì†Œ")
            continue

        # ?¹ì¼ ì²´ê²° ?•ì¸
        if days_elapsed == 0:
            if order.get("order_no"):
                status = client.get_order_status(order["order_no"], order["symbol"])
                if status == "filled":
                    _update_order(order["id"], status="active")
                    _send_user(chat_id, f"??<b>ë§¤ìˆ˜ ì²´ê²° ?•ì¸</b>\n<b>{order['name']}</b> ??order['entry_price']:,} Ã— {order['qty']}ì£?)
            continue

        # ?„ë‚  ë¯¸ì²´ê²????¬ì£¼ë¬?
        if order.get("order_no"):
            status = client.get_order_status(order["order_no"], order["symbol"])
            if status == "filled":
                _update_order(order["id"], status="active")
                _send_user(chat_id, f"??<b>ë§¤ìˆ˜ ì²´ê²° ?•ì¸</b>\n<b>{order['name']}</b> ??order['entry_price']:,} Ã— {order['qty']}ì£?)
                continue
            client.cancel_order(order["order_no"], order["symbol"], order["qty"])

        result = client.buy_order(order["symbol"], order["entry_price"], order["qty"], market=True)
        if result["success"]:
            _update_order(order["id"], alert_date=today, order_no=result.get("order_no", ""))


def monitor_positions(user: dict):
    """?¥ì¤‘ ëª¨ë‹ˆ?°ë§ (? ì?ë³?"""
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
        base_price = order.get("base_price", entry) or entry
        trigger2   = order.get("trigger2") or int(entry * 0.98)
        trigger3   = order.get("trigger3") or int(entry * 0.96)

        # 2ì°?ë¶„í• ë§¤ìˆ˜
        if split_step == 1 and cur <= trigger2:
            add_qty = max(1, int(split_budget / cur))
            result  = client.buy_order(symbol, int(cur), add_qty, market=True)
            if result["success"]:
                new_avg = (avg_price * qty + cur * add_qty) / (qty + add_qty)
                _update_order(order["id"], split_step=2, split_qty=qty + add_qty,
                              avg_price=round(new_avg, 2), qty=qty + add_qty,
                              step2_price=round(cur, 2), step2_qty=add_qty)
                _send_user(chat_id,
                    f"?“¥ <b>2ì°?ë¶„í• ë§¤ìˆ˜</b>  <b>{order['name']}</b>\n"
                    f"  1ì°???base_price:,.0f} Ã— {qty}ì£?n"
                    f"  2ì°???cur:,.0f} Ã— {add_qty}ì£?n"
                    f"?â”?â”?â”?â”?â”?â”?â”\n"
                    f"  ?‰ê· ?¨ê? ??new_avg:,.0f} Ã— {qty + add_qty}ì£?n"
                    f"  ?›‘ ?ì ˆ ??stop:,}")
            continue

        # 3ì°?ë¶„í• ë§¤ìˆ˜
        elif split_step == 2 and cur <= trigger3:
            add_qty     = max(1, int(split_budget / cur))
            result      = client.buy_order(symbol, int(cur), add_qty, market=True)
            if result["success"]:
                new_avg     = (avg_price * qty + cur * add_qty) / (qty + add_qty)
                step2_price = order.get("step2_price") or trigger2
                step2_qty   = order.get("step2_qty") or 0
                step1_qty   = qty - step2_qty
                _update_order(order["id"], split_step=3, split_qty=qty + add_qty,
                              avg_price=round(new_avg, 2), qty=qty + add_qty,
                              step3_price=round(cur, 2), step3_qty=add_qty)
                _send_user(chat_id,
                    f"?“¥ <b>3ì°?ë¶„í• ë§¤ìˆ˜ ?„ë£Œ</b>  <b>{order['name']}</b>\n"
                    f"  1ì°???base_price:,.0f} Ã— {step1_qty}ì£?n"
                    f"  2ì°???step2_price:,.0f} Ã— {step2_qty}ì£?n"
                    f"  3ì°???cur:,.0f} Ã— {add_qty}ì£?n"
                    f"?â”?â”?â”?â”?â”?â”?â”\n"
                    f"  ?‰ê· ?¨ê? ??new_avg:,.0f} Ã— {qty + add_qty}ì£?n"
                    f"  ?¯ ëª©í‘œ ??target:,}  ?›‘ ?ì ˆ ??stop:,}")
            continue

        # ëª©í‘œê°€ ?„ë‹¬
        if cur >= target:
            result = client.sell_order(symbol, target, qty, market=True)
            if result["success"]:
                ret = (cur - avg_price) / avg_price * 100
                _update_order(order["id"], status="hit_target", exit_price=int(cur),
                              exit_date=today, return_pct=round(ret, 2))
                _send_user(chat_id,
                    f"?¯ <b>ëª©í‘œê°€ ?¬ì„±!</b>\n<b>{order['name']}</b>\n"
                    f"?‰ê· ?¨ê? ??avg_price:,.0f} ??ë§¤ë„ ??cur:,.0f}\n"
                    f"?˜ìµë¥?<b>+{ret:.1f}%</b> ?‰")

        # ?ì ˆê°€ ?„ë‹¬
        elif cur <= stop:
            result = client.sell_order(symbol, stop, qty, market=True)
            if result["success"]:
                ret = (cur - avg_price) / avg_price * 100
                _update_order(order["id"], status="hit_stop", exit_price=int(cur),
                              exit_date=today, return_pct=round(ret, 2))
                _send_user(chat_id,
                    f"?›‘ <b>?ì ˆ ?¤í–‰</b>\n<b>{order['name']}</b>\n"
                    f"?‰ê· ?¨ê? ??avg_price:,.0f} ???ì ˆ ??cur:,.0f}\n"
                    f"?ì‹¤ <b>{ret:.1f}%</b>")


# ?€?€ ?”ë ˆê·¸ë¨ ë´?ì»¤ë§¨??ì²˜ë¦¬ ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
def handle_bot_command(chat_id: str, text: str):
    """
    ?”ë ˆê·¸ë¨ ë´?ë©”ì‹œì§€ ì²˜ë¦¬
    scheduler.py??ë´??´ë§ ë£¨í”„?ì„œ ?¸ì¶œ
    """
    text = text.strip()
    parts = text.split()
    cmd = parts[0].lower() if parts else ""

    # /register <app_key> <app_secret> <ê³„ì¢Œë²ˆí˜¸> [mock=1]
    if cmd == "/register":
        if len(parts) < 4:
            _send_user(chat_id,
                "?“‹ <b>?±ë¡ ë°©ë²•</b>\n"
                "/register <b>?±í‚¤</b> <b>?±ì‹œ?¬ë¦¿</b> <b>ê³„ì¢Œë²ˆí˜¸</b> [mock=1]\n\n"
                "?ˆì‹œ:\n"
                "<code>/register PSabc123... xyzSecret... 50123456-01 mock=0</code>\n\n"
                "? ï¸ ê³„ì¢Œë²ˆí˜¸ ?•ì‹: 12345678-01")
            return

        app_key    = parts[1]
        app_secret = parts[2]
        account    = parts[3]
        mock       = True
        for p in parts[4:]:
            if p.startswith("mock="):
                mock = p.split("=")[1] != "0"

        result = register_user(chat_id, app_key, app_secret, account, mock)
        mode   = "ëª¨ì˜?¬ì" if mock else "?¤ì „?¬ì"
        action = "?…ë°?´íŠ¸" if result == "updated" else "?±ë¡"
        _send_user(chat_id,
            f"??<b>?ë™ë§¤ë§¤ {action} ?„ë£Œ</b>\n"
            f"ê³„ì¢Œ: {account}\n"
            f"ëª¨ë“œ: {mode}\n\n"
            f"?¤ì • ë³€ê²? /settings budget=300000 max_stocks=3\n"
            f"?„í™© ì¡°íšŒ: /status\n"
            f"ì¤‘ì?: /stop")

    # /settings [key=value ...]
    elif cmd == "/settings":
        user = get_user(chat_id)
        if not user:
            _send_user(chat_id, "??ë¨¼ì? /register ë¡??±ë¡?´ì£¼?¸ìš”.")
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
            # ?„ì¬ ?¤ì • ?œì‹œ
            mode = "ëª¨ì˜?¬ì" if user.get("mock") else "?¤ì „?¬ì"
            _send_user(chat_id,
                f"?™ï¸ <b>?„ì¬ ?¤ì •</b>\n"
                f"ëª¨ë“œ: {mode}\n"
                f"ì¢…ëª©???ˆì‚°: ??user.get('budget_per', 300000):,}\n"
                f"ìµœë? ë³´ìœ  ì¢…ëª©: {user.get('max_stocks', 3)}ê°?n"
                f"ë¯¸ì²´ê²?ë§Œë£Œ: {user.get('max_days', 5)}??n\n"
                f"ë³€ê²??ˆì‹œ:\n"
                f"<code>/settings budget=500000 max_stocks=5 mock=0</code>")
            return

        update_user_settings(chat_id, **updates)
        lines = []
        if "budget_per"  in updates: lines.append(f"ì¢…ëª©???ˆì‚°: ??updates['budget_per']:,}")
        if "max_stocks"  in updates: lines.append(f"ìµœë? ì¢…ëª©: {updates['max_stocks']}ê°?)
        if "max_days"    in updates: lines.append(f"ë§Œë£Œ?? {updates['max_days']}??)
        if "mock"        in updates: lines.append(f"ëª¨ë“œ: {'ëª¨ì˜' if updates['mock'] else '?¤ì „'}?¬ì")
        _send_user(chat_id, "??<b>?¤ì • ?…ë°?´íŠ¸</b>\n" + "\n".join(lines))

    # /status
    elif cmd == "/status":
        user = get_user(chat_id)
        if not user:
            _send_user(chat_id, "??ë¨¼ì? /register ë¡??±ë¡?´ì£¼?¸ìš”.")
            return
        if not user.get("is_active"):
            _send_user(chat_id, "???ë™ë§¤ë§¤ê°€ ì¤‘ì? ?íƒœ?…ë‹ˆ?? /resume ?¼ë¡œ ?¬ê°œ?˜ì„¸??")
            return

        try:
            client  = UserKISClient(user)
            balance = client.get_balance()
            cash    = balance.get("cash", 0)
            orders  = _get_pending_orders(user["user_id"])
            active  = [o for o in orders if o["status"] == "active"]
            pending = [o for o in orders if o["status"] == "pending"]
            mode    = "ëª¨ì˜" if user.get("mock") else "?¤ì „"

            lines = [f"?“Š <b>???ë™ë§¤ë§¤ ?„í™©</b>  [{mode}]", f"?ˆìˆ˜ê¸? ??cash:,.0f}"]
            if active:
                lines.append(f"\n?Ÿ¢ <b>ë³´ìœ  ì¤?/b> ({len(active)}ì¢…ëª©)")
                for o in active:
                    cur = client.get_price(o["symbol"])
                    avg = o.get("avg_price") or o["entry_price"]
                    split_step = o.get("split_step", 1) or 1
                    split_tag  = f" ({split_step}ì°??‰ê· )" if split_step > 1 else ""
                    if cur and avg:
                        ret = (cur - avg) / avg * 100
                        lines.append(f"  ?“Œ {o['name']}  {ret:+.1f}%  (?‰ê· ?¨ê? ??avg:,.0f}{split_tag} / ?„ì¬ ??cur:,.0f})")
                    else:
                        lines.append(f"  ?“Œ {o['name']}  ?‰ê· ?¨ê? ??avg:,.0f}{split_tag}")
            if pending:
                lines.append(f"\n??<b>ë§¤ìˆ˜ ?€ê¸?/b> ({len(pending)}ì¢…ëª©)")
                for o in pending:
                    lines.append(f"  ?”µ {o['name']}  ??o['entry_price']:,}")
            if not active and not pending:
                lines.append("\në³´ìœ /?€ê¸?ì¢…ëª© ?†ìŒ")

            _send_user(chat_id, "\n".join(lines))
        except Exception as e:
            _send_user(chat_id, f"??ì¡°íšŒ ?¤ë¥˜: {e}")

    # /stop
    elif cmd == "/stop":
        user = get_user(chat_id)
        if not user:
            _send_user(chat_id, "???±ë¡??ê³„ì •???†ìŠµ?ˆë‹¤.")
            return
        update_user_settings(chat_id, is_active=0)
        _send_user(chat_id, "??<b>?ë™ë§¤ë§¤ ì¤‘ì?</b>\nê¸°ì¡´ ë³´ìœ  ì¢…ëª© ëª¨ë‹ˆ?°ë§?€ ê³„ì†?©ë‹ˆ??\n?¬ê°œ: /resume")

    # /resume
    elif cmd == "/resume":
        user = get_user(chat_id)
        if not user:
            _send_user(chat_id, "??ë¨¼ì? /register ë¡??±ë¡?´ì£¼?¸ìš”.")
            return
        update_user_settings(chat_id, is_active=1)
        _send_user(chat_id, "?¶ï¸ <b>?ë™ë§¤ë§¤ ?¬ê°œ</b>\n?¤ìŒ ?¤ìº” ê²°ê³¼ë¶€???ë™ ë§¤ìˆ˜?©ë‹ˆ??")

    # /unregister
    elif cmd == "/unregister":
        user = get_user(chat_id)
        if not user:
            _send_user(chat_id, "???±ë¡??ê³„ì •???†ìŠµ?ˆë‹¤.")
            return
        delete_user(chat_id)
        _send_user(chat_id, "?—‘ <b>ê³„ì • ?? œ ?„ë£Œ</b>\n?ë™ë§¤ë§¤ê°€ ì¤‘ì??˜ì—ˆ?µë‹ˆ??")

    # /help
    elif cmd in ("/help", "/start"):
        _send_user(chat_id,
            "?¤– <b>?ë™ë§¤ë§¤ ë´?ì»¤ë§¨??/b>\n\n"
            "/register - KIS API ???±ë¡\n"
            "/settings - ?¤ì • ì¡°íšŒ/ë³€ê²?n"
            "/status   - ?¬íŠ¸?´ë¦¬???„í™©\n"
            "/stop     - ?ë™ë§¤ë§¤ ì¤‘ì?\n"
            "/resume   - ?ë™ë§¤ë§¤ ?¬ê°œ\n"
            "/unregister - ê³„ì • ?? œ")


# ?€?€ ?¤ì?ì¤„ëŸ¬??ì§„ì…???€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
def run_all_users_morning_reorder():
    """09:05 - ?„ì²´ ?œì„± ? ì? ?¬ì£¼ë¬?(ë³‘ë ¬ ì²˜ë¦¬)"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    users = get_active_users()
    if not users:
        return
    def _reorder(user):
        try:
            morning_reorder(user)
        except Exception as e:
            print(f"[ë©€?°ìœ ?€] morning_reorder ?¤ë¥˜ ({user.get('chat_id')}): {e}")
    with ThreadPoolExecutor(max_workers=min(len(users), 10)) as ex:
        list(ex.map(_reorder, users))


def run_all_users_place_orders(results: list):
    """?¤ìº” ê²°ê³¼ ???„ì²´ ?œì„± ? ì? ë§¤ìˆ˜ ì£¼ë¬¸ (ë³‘ë ¬ ì²˜ë¦¬)"""
    from concurrent.futures import ThreadPoolExecutor
    users = get_active_users()
    if not users:
        return
    def _place(user):
        try:
            place_orders(results, user)
        except Exception as e:
            print(f"[ë©€?°ìœ ?€] place_orders ?¤ë¥˜ ({user.get('chat_id')}): {e}")
    with ThreadPoolExecutor(max_workers=min(len(users), 10)) as ex:
        list(ex.map(_place, users))


def run_all_users_monitor():
    """?¥ì¤‘ ëª¨ë‹ˆ?°ë§ - ?„ì²´ ?œì„± ? ì? (ë³‘ë ¬ ì²˜ë¦¬)"""
    from concurrent.futures import ThreadPoolExecutor
    users = get_active_users()
    if not users:
        return
    def _monitor(user):
        try:
            monitor_positions(user)
        except Exception as e:
            print(f"[ë©€?°ìœ ?€] monitor ?¤ë¥˜ ({user.get('chat_id')}): {e}")
    with ThreadPoolExecutor(max_workers=min(len(users), 10)) as ex:
        list(ex.map(_monitor, users))


def poll_bot_commands():
    """
    ?”ë ˆê·¸ë¨ ë´??…ë°?´íŠ¸ ?´ë§ (?¤ì?ì¤„ëŸ¬ ë£¨í”„?ì„œ 30ì´ˆë§ˆ???¸ì¶œ)
    getUpdates long-polling ë°©ì‹
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
        print(f"[ë©€?°ìœ ?€] ë´??´ë§ ?¤ë¥˜: {e}")
