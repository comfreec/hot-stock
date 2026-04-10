"""
SQLite 기반 스캔 결과 캐싱 + 성과 추적 (주식 버전과 동일한 구조)
"""
import sqlite3
import json
import os
from datetime import datetime, date

_local_path = os.path.join(os.path.dirname(__file__), "scan_cache.db")
DB_PATH = os.environ.get("CRYPTO_DB_PATH", os.environ.get("DB_PATH",
    "/data/crypto_scan_cache.db" if os.path.isdir("/data") else _local_path
))

def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scan_results (
            scan_date  TEXT PRIMARY KEY,
            results    TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alert_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_date   TEXT NOT NULL,
            symbol       TEXT NOT NULL,
            name         TEXT NOT NULL,
            score        INTEGER,
            entry_price  REAL,
            target_price REAL,
            stop_price   REAL,
            rr_ratio     REAL,
            status       TEXT DEFAULT 'active',
            exit_price   REAL,
            exit_date    TEXT,
            return_pct   REAL,
            created_at   TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

# ── 스캔 결과 저장/로드 ───────────────────────────────────────────
def save_scan(results: list, scan_date: str = None):
    if scan_date is None:
        scan_date = date.today().isoformat()
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO scan_results VALUES (?,?,?)",
        (scan_date, json.dumps(results, ensure_ascii=False, default=str),
         datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def load_scan(scan_date: str = None) -> list:
    if scan_date is None:
        scan_date = date.today().isoformat()
    conn = _get_conn()
    row = conn.execute(
        "SELECT results FROM scan_results WHERE scan_date=?", (scan_date,)
    ).fetchone()
    conn.close()
    return json.loads(row[0]) if row else []

def list_scan_dates() -> list:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT scan_date, created_at FROM scan_results ORDER BY scan_date DESC LIMIT 30"
    ).fetchall()
    conn.close()
    return [{"date": r[0], "created_at": r[1]} for r in rows]

# ── 성과 추적 ────────────────────────────────────────────────────
def save_alert_history(results: list, price_levels_map: dict = None):
    """알림 발송 코인을 성과 추적 DB에 저장 (중복 방지)"""
    today = date.today().isoformat()
    conn = _get_conn()
    for r in results:
        sym = r.get("symbol", "")
        # 오늘 이미 저장된 종목 스킵
        if conn.execute(
            "SELECT id FROM alert_history WHERE alert_date=? AND symbol=?", (today, sym)
        ).fetchone():
            continue
        # 아직 active 상태인 종목 스킵
        if conn.execute(
            "SELECT id FROM alert_history WHERE symbol=? AND status='active'", (sym,)
        ).fetchone():
            continue
        lv = (price_levels_map or {}).get(sym, {})
        conn.execute("""
            INSERT INTO alert_history
            (alert_date, symbol, name, score, entry_price, target_price, stop_price, rr_ratio, status, created_at)
            VALUES (?,?,?,?,?,?,?,?,'active',?)
        """, (
            today, sym, r.get("name", sym),
            r.get("total_score", 0),
            lv.get("entry"), lv.get("target"), lv.get("stop"), lv.get("rr"),
            datetime.now().isoformat()
        ))
    conn.commit()
    conn.close()

def get_alert_history(limit: int = 60) -> list:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT id, alert_date, symbol, name, score,
               entry_price, target_price, stop_price, rr_ratio,
               status, exit_price, exit_date, return_pct, created_at
        FROM alert_history
        ORDER BY alert_date DESC, score DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    keys = ["id","alert_date","symbol","name","score",
            "entry_price","target_price","stop_price","rr_ratio",
            "status","exit_price","exit_date","return_pct","created_at"]
    return [dict(zip(keys, r)) for r in rows]

def update_alert_status():
    """active 종목 현재가 확인 → 상태 업데이트"""
    try:
        import ccxt
        exchange = ccxt.binance({"enableRateLimit": True})
        conn = _get_conn()
        rows = conn.execute(
            "SELECT id, symbol, entry_price, target_price, stop_price, alert_date FROM alert_history WHERE status='active'"
        ).fetchall()
        today = date.today().isoformat()
        for row in rows:
            rid, symbol, entry, target, stop, alert_date = row
            if not entry or not target or not stop:
                continue
            try:
                ticker = exchange.fetch_ticker(symbol)
                current = float(ticker["last"])
                ret_pct = (current - entry) / entry * 100
                status = None
                if current >= target:
                    status = "hit_target"
                    exit_price = target
                    ret_pct = (target - entry) / entry * 100
                elif current <= stop:
                    status = "hit_stop"
                    exit_price = stop
                    ret_pct = (stop - entry) / entry * 100
                else:
                    from datetime import timedelta
                    if (date.today() - date.fromisoformat(alert_date)).days > 14:
                        status = "expired"
                        exit_price = current
                if status:
                    conn.execute(
                        "UPDATE alert_history SET status=?,exit_price=?,exit_date=?,return_pct=? WHERE id=?",
                        (status, exit_price, today, ret_pct, rid)
                    )
            except:
                pass
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[코인 성과추적] 업데이트 오류: {e}")

def get_performance_summary() -> dict:
    conn = _get_conn()
    closed = conn.execute(
        "SELECT status, return_pct FROM alert_history WHERE status IN ('hit_target','hit_stop')"
    ).fetchall()
    counts = dict(conn.execute(
        "SELECT status, COUNT(*) FROM alert_history GROUP BY status"
    ).fetchall())
    conn.close()
    wins   = [r[1] for r in closed if r[0] == "hit_target" and r[1] is not None]
    losses = [r[1] for r in closed if r[0] == "hit_stop"   and r[1] is not None]
    all_ret = [r[1] for r in closed if r[1] is not None]
    total = len(closed)
    return {
        "total":      total,
        "win":        len(wins),
        "loss":       len(losses),
        "expired":    counts.get("expired", 0),
        "active":     counts.get("active", 0),
        "win_rate":   round(len(wins) / total * 100, 1) if total else 0,
        "avg_return": round(sum(all_ret) / len(all_ret), 2) if all_ret else 0,
        "avg_win":    round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss":   round(sum(losses) / len(losses), 2) if losses else 0,
    }

def get_recent_closed(limit: int = 5) -> list:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT name, status, return_pct, exit_date, entry_price, target_price
        FROM alert_history
        WHERE status IN ('hit_target', 'hit_stop') AND exit_date IS NOT NULL
        ORDER BY exit_date DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [{"name": r[0], "status": r[1], "return_pct": r[2],
             "exit_date": r[3], "entry_price": r[4], "target_price": r[5]} for r in rows]
