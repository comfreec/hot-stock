"""
SQLite 기반 스캔 결과 캐싱
"""
import sqlite3
import json
import os
from datetime import datetime, date

_local_path = os.path.join(os.path.dirname(__file__), "scan_cache.db")
DB_PATH = os.environ.get("DB_PATH",
    "/data/crypto_scan_cache.db" if os.path.isdir("/data") else _local_path
)

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

def save_alert_history(symbol, name, score, entry, target, stop, rr):
    conn = _get_conn()
    conn.execute(
        """INSERT INTO alert_history
           (alert_date,symbol,name,score,entry_price,target_price,stop_price,rr_ratio,status,created_at)
           VALUES (?,?,?,?,?,?,?,?,'active',?)""",
        (date.today().isoformat(), symbol, name, score, entry, target, stop, rr,
         datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def update_alert_status():
    """active 종목 현재가 확인 → 상태 업데이트"""
    try:
        import ccxt
        exchange = ccxt.binance()
        conn = _get_conn()
        rows = conn.execute(
            "SELECT id,symbol,entry_price,target_price,stop_price,alert_date FROM alert_history WHERE status='active'"
        ).fetchall()
        for row in rows:
            rid, symbol, entry, target, stop, alert_date = row
            try:
                ticker = exchange.fetch_ticker(symbol)
                current = float(ticker["last"])
                ret_pct = (current - entry) / entry * 100
                status = None
                if current >= target:
                    status = "hit_target"
                elif current <= stop:
                    status = "hit_stop"
                else:
                    # 7일 경과 시 expired
                    from datetime import timedelta
                    if (date.today() - date.fromisoformat(alert_date)).days > 7:
                        status = "expired"
                if status:
                    conn.execute(
                        "UPDATE alert_history SET status=?,exit_price=?,exit_date=?,return_pct=? WHERE id=?",
                        (status, current, date.today().isoformat(), ret_pct, rid)
                    )
            except:
                pass
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[update_alert_status] {e}")

def get_performance_summary() -> dict:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT status, return_pct FROM alert_history WHERE status != 'active'"
    ).fetchall()
    conn.close()
    if not rows:
        return {}
    wins = [r[1] for r in rows if r[0] == "hit_target"]
    losses = [r[1] for r in rows if r[0] == "hit_stop"]
    total = len(rows)
    win_rate = len(wins) / total * 100 if total else 0
    avg_ret = sum(r[1] for r in rows if r[1] is not None) / total if total else 0
    return {"total": total, "win_rate": round(win_rate, 1), "avg_return": round(avg_ret, 2)}
