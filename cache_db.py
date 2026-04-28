"""
SQLite 기반 스캔 결과 캐싱 + 스케줄러
- 장 마감 후 자동 스캔 결과 저장
- 앱에서 캐시된 결과 즉시 로드 (yfinance 재호출 없음)
"""
import sqlite3
import json
import os
from datetime import datetime, date
import threading

import os as _os
_data_path = "/data/scan_cache.db"
_local_path = _os.path.join(_os.path.dirname(__file__), "scan_cache.db")
DB_PATH = _os.environ.get("DB_PATH",
    _data_path if _os.path.isdir("/data") else _local_path
)

# 테이블 초기화 1회만 수행 (WAL 모드 포함)
_init_lock = threading.Lock()
_db_initialized = False

def _get_conn():
    """매번 새 연결 반환 (안전) + 최초 1회 테이블 초기화"""
    global _db_initialized
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-8000")

    if not _db_initialized:
        with _init_lock:
            if not _db_initialized:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS scan_results (
                        scan_date TEXT PRIMARY KEY,
                        results   TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS favorites (
                        symbol TEXT PRIMARY KEY,
                        name   TEXT,
                        added_at TEXT
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS alert_history (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        alert_date  TEXT NOT NULL,
                        symbol      TEXT NOT NULL,
                        name        TEXT NOT NULL,
                        score       INTEGER,
                        entry_price REAL,
                        entry_label TEXT,
                        target_price REAL,
                        stop_price  REAL,
                        rr_ratio    REAL,
                        status      TEXT DEFAULT 'active',
                        exit_price  REAL,
                        exit_date   TEXT,
                        return_pct  REAL,
                        created_at  TEXT NOT NULL,
                        avg_price   REAL,
                        split_step  INTEGER DEFAULT 1
                    )
                """)
                conn.commit()
                existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(alert_history)").fetchall()]
                for col, default in [("avg_price", "NULL"), ("split_step", "1")]:
                    if col not in existing_cols:
                        conn.execute(f"ALTER TABLE alert_history ADD COLUMN {col} {'REAL' if col == 'avg_price' else 'INTEGER'} DEFAULT {default}")
                conn.commit()
                _db_initialized = True
    return conn

# ── 스캔 결과 저장/로드 ───────────────────────────────────────────
def save_scan(results: list, scan_date: str = None):
    """스캔 결과 저장 (날짜별 1개)"""
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
    """저장된 스캔 결과 로드"""
    if scan_date is None:
        scan_date = date.today().isoformat()
    conn = _get_conn()
    row = conn.execute(
        "SELECT results FROM scan_results WHERE scan_date=?", (scan_date,)
    ).fetchone()
    conn.close()
    return json.loads(row[0]) if row else []

def list_scan_dates() -> list:
    """저장된 스캔 날짜 목록"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT scan_date, created_at FROM scan_results ORDER BY scan_date DESC LIMIT 30"
    ).fetchall()
    conn.close()
    return [{"date": r[0], "created_at": r[1]} for r in rows]

# ── 즐겨찾기 ─────────────────────────────────────────────────────
def add_favorite(symbol: str, name: str):
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO favorites VALUES (?,?,?)",
            (symbol, name, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def remove_favorite(symbol: str):
    try:
        conn = _get_conn()
        conn.execute("DELETE FROM favorites WHERE symbol=?", (symbol,))
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_favorites() -> list:
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT symbol, name, added_at FROM favorites ORDER BY added_at DESC"
        ).fetchall()
        conn.close()
        return [{"symbol": r[0], "name": r[1], "added_at": r[2]} for r in rows]
    except Exception:
        return []

def is_favorite(symbol: str) -> bool:
    try:
        conn = _get_conn()
        row = conn.execute("SELECT 1 FROM favorites WHERE symbol=?", (symbol,)).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False

# ── 성과 추적 ────────────────────────────────────────────────────
def save_alert_history(results: list, price_levels_map: dict = None):
    """알림 발송 종목을 성과 추적 DB에 저장 (같은 날 중복 방지)"""
    today = date.today().isoformat()
    conn = _get_conn()
    for r in results:
        sym = r.get("symbol", "")
        # 오늘 이미 저장됐거나 현재 active/pending 상태인 종목이면 스킵
        existing = conn.execute(
            "SELECT id FROM alert_history WHERE symbol=? AND (alert_date=? OR status IN ('pending','active'))",
            (sym, today)
        ).fetchone()
        if existing:
            continue
        lv  = (price_levels_map or {}).get(sym, {})
        # 레벨 없으면 yfinance로 직접 계산 재시도
        if not lv or not lv.get("entry"):
            try:
                from telegram_alert import calc_price_levels
                lv = calc_price_levels(sym) or {}
            except Exception:
                lv = {}
        conn.execute("""
            INSERT INTO alert_history
            (alert_date, symbol, name, score, entry_price, entry_label,
             target_price, stop_price, rr_ratio, status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,'pending',?)
        """, (
            today, sym, r.get("name", sym),
            r.get("total_score", 0),
            lv.get("entry"), lv.get("entry_label", ""),
            lv.get("target"), lv.get("stop"),
            lv.get("rr"), datetime.now().isoformat()
        ))
    conn.commit()
    conn.close()

def get_alert_history(limit: int = 60) -> list:
    """성과 추적 내역 조회"""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT id, alert_date, symbol, name, score,
               entry_price, entry_label, target_price, stop_price, rr_ratio,
               status, exit_price, exit_date, return_pct, created_at,
               avg_price, split_step
        FROM alert_history
        ORDER BY alert_date DESC, score DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    keys = ["id","alert_date","symbol","name","score",
            "entry_price","entry_label","target_price","stop_price","rr_ratio",
            "status","exit_price","exit_date","return_pct","created_at",
            "avg_price","split_step"]
    return [dict(zip(keys, r)) for r in rows]

def update_alert_status():
    """pending/active 종목들의 현재가 확인 → 상태 업데이트"""
    try:
        import yfinance as yf
        conn = _get_conn()

        # ── trade_orders에서 avg_price / split_step 동기화 ──────────
        try:
            trade_rows = conn.execute("""
                SELECT symbol, avg_price, split_step, stop_price FROM trade_orders
                WHERE status IN ('active','hit_target','hit_stop')
                  AND avg_price > 0
            """).fetchall()
            for sym, avg_p, step, stop_p in trade_rows:
                conn.execute("""
                    UPDATE alert_history SET avg_price=?, split_step=?, stop_price=?
                    WHERE symbol=? AND status IN ('pending','active')
                """, (avg_p, step or 1, stop_p, sym))
            conn.commit()
        except Exception:
            pass  # trade_orders 없는 환경(스캔 전용)이면 스킵

        # ── trade_orders_multi에서도 동기화 ─────────────────────────
        try:
            multi_rows = conn.execute("""
                SELECT symbol, avg_price, split_step FROM trade_orders_multi
                WHERE status IN ('active','hit_target','hit_stop')
                  AND avg_price > 0
            """).fetchall()
            for sym, avg_p, step in multi_rows:
                conn.execute("""
                    UPDATE alert_history SET avg_price=?, split_step=?
                    WHERE symbol=? AND status IN ('pending','active')
                      AND (avg_price IS NULL OR avg_price = 0)
                """, (avg_p, step or 1, sym))
            conn.commit()
        except Exception:
            pass

        rows = conn.execute("""
            SELECT id, symbol, entry_price, target_price, stop_price, alert_date, status,
                   avg_price
            FROM alert_history WHERE status IN ('pending', 'active')
        """).fetchall()

        today = date.today().isoformat()
        for row in rows:
            rid, sym, entry, target, stop, alert_date, status, avg_p = row
            # 실제 평단가 우선, 없으면 entry_price 사용
            base = avg_p if avg_p and avg_p > 0 else entry

            # pending 종목만 거래일 기준 5일 경과 시 만료
            if status == 'pending':
                try:
                    from datetime import datetime as dt, timedelta
                    alert_dt = dt.fromisoformat(alert_date).date()
                    trading_days = 0
                    cur_day = alert_dt
                    while cur_day < date.today():
                        cur_day += timedelta(days=1)
                        if cur_day.weekday() < 5:
                            trading_days += 1
                    if trading_days >= 7:
                        conn.execute("UPDATE alert_history SET status='expired', exit_date=? WHERE id=?",
                                     (today, rid))
                        continue
                except:
                    pass

            if not entry or not target or not stop:
                continue
            try:
                df = yf.Ticker(sym).history(period="5d").dropna(subset=["Close","Low","High"])
                if len(df) == 0:
                    continue

                cur      = float(df["Close"].iloc[-1])
                day_low  = float(df["Low"].iloc[-1])
                day_high = float(df["High"].iloc[-1])

                if status == 'pending':
                    # 전날 저가가 매수가 이하면 진입 확인
                    prev_low = float(df["Low"].iloc[-1])
                    if prev_low <= entry:
                        conn.execute("UPDATE alert_history SET status='active' WHERE id=?", (rid,))
                        status = 'active'

                if status == 'active':
                    if day_high >= target:
                        exit_price = target
                        ret = (exit_price - base) / base * 100 if base else 0
                        conn.execute("""UPDATE alert_history
                            SET status='hit_target', exit_price=?, exit_date=?, return_pct=?
                            WHERE id=?""", (exit_price, today, ret, rid))
                    elif day_low <= stop:
                        exit_price = stop
                        ret = (exit_price - base) / base * 100 if base else 0
                        conn.execute("""UPDATE alert_history
                            SET status='hit_stop', exit_price=?, exit_date=?, return_pct=?
                            WHERE id=?""", (exit_price, today, ret, rid))
            except:
                pass

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[성과추적] 업데이트 오류: {e}")

def get_performance_summary(date_from: str = None, date_to: str = None) -> dict:
    """성과 요약 통계 (기간 필터 지원)"""
    conn = _get_conn()
    params = []
    where = "WHERE status IN ('hit_target','hit_stop')"
    if date_from:
        where += " AND alert_date >= ?"; params.append(date_from)
    if date_to:
        where += " AND alert_date <= ?"; params.append(date_to)

    closed_rows = conn.execute(f"SELECT status, return_pct FROM alert_history {where}", params).fetchall()

    count_where = ""
    count_params = []
    if date_from or date_to:
        count_where = "WHERE 1=1"
        if date_from:
            count_where += " AND alert_date >= ?"; count_params.append(date_from)
        if date_to:
            count_where += " AND alert_date <= ?"; count_params.append(date_to)
    counts = dict(conn.execute(f"SELECT status, COUNT(*) FROM alert_history {count_where} GROUP BY status", count_params).fetchall())

    wins    = [r[1] for r in closed_rows if r[0] == 'hit_target' and r[1] is not None]
    losses  = [r[1] for r in closed_rows if r[0] == 'hit_stop'   and r[1] is not None]
    all_ret = [r[1] for r in closed_rows if r[1] is not None]
    total   = len(closed_rows)
    conn.close()
    return {
        "total":      total,
        "win":        len(wins),
        "loss":       len(losses),
        "expired":    counts.get("expired", 0),
        "active":     counts.get("active", 0),
        "pending":    counts.get("pending", 0),
        "win_rate":   round(len(wins) / total * 100, 1) if total else 0,
        "avg_return": round(sum(all_ret) / len(all_ret), 2) if all_ret else 0,
        "avg_win":    round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss":   round(sum(losses) / len(losses), 2) if losses else 0,
    }

def get_alert_history_range(date_from: str = None, date_to: str = None, limit: int = 500) -> list:
    """기간 필터 적용된 알림 내역 조회"""
    conn = _get_conn()
    where = "WHERE 1=1"
    params = []
    if date_from:
        where += " AND alert_date >= ?"; params.append(date_from)
    if date_to:
        where += " AND alert_date <= ?"; params.append(date_to)
    params.append(limit)
    rows = conn.execute(f"""
        SELECT id, alert_date, symbol, name, score,
               entry_price, entry_label, target_price, stop_price, rr_ratio,
               status, exit_price, exit_date, return_pct, created_at,
               avg_price, split_step
        FROM alert_history {where}
        ORDER BY alert_date DESC, score DESC
        LIMIT ?
    """, params).fetchall()
    conn.close()
    keys = ["id","alert_date","symbol","name","score",
            "entry_price","entry_label","target_price","stop_price","rr_ratio",
            "status","exit_price","exit_date","return_pct","created_at",
            "avg_price","split_step"]
    return [dict(zip(keys, r)) for r in rows]

def get_monthly_stats() -> list:
    """월별 성과 통계 반환"""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT
            strftime('%Y-%m', alert_date) AS month,
            COUNT(*) AS total,
            SUM(CASE WHEN status='hit_target' THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN status='hit_stop'   THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN status='expired'    THEN 1 ELSE 0 END) AS expired,
            AVG(CASE WHEN status IN ('hit_target','hit_stop') AND return_pct IS NOT NULL THEN return_pct END) AS avg_return,
            SUM(CASE WHEN status IN ('hit_target','hit_stop') AND return_pct IS NOT NULL THEN return_pct ELSE 0 END) AS total_return
        FROM alert_history
        WHERE alert_date IS NOT NULL
        GROUP BY month
        ORDER BY month ASC
    """).fetchall()
    result = []
    for r in rows:
        month, total, wins, losses, expired, avg_ret, total_ret = r
        closed = (wins or 0) + (losses or 0)
        result.append({
            "month":        month,
            "total":        total or 0,
            "wins":         wins or 0,
            "losses":       losses or 0,
            "expired":      expired or 0,
            "win_rate":     round((wins or 0) / closed * 100, 1) if closed > 0 else 0,
            "avg_return":   round(avg_ret, 2) if avg_ret is not None else 0,
            "total_return": round(total_ret, 2) if total_ret is not None else 0,
        })
    conn.close()
    return result

def get_available_date_range() -> tuple:
    conn = _get_conn()
    row = conn.execute("SELECT MIN(alert_date), MAX(alert_date) FROM alert_history").fetchone()
    conn.close()
    return row[0], row[1]

def get_recent_closed(limit: int = 5) -> list:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT name, status, return_pct, exit_date, entry_price, target_price
        FROM alert_history
        WHERE status IN ('hit_target', 'hit_stop') AND exit_date IS NOT NULL
        ORDER BY exit_date DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [{"name": r[0], "status": r[1], "return_pct": r[2],
             "exit_date": r[3], "entry_price": r[4], "target_price": r[5]} for r in rows]


# ── 앱 설정 저장/로드 ─────────────────────────────────────────────
def save_app_setting(key: str, value: str):
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)
    conn.execute(
        "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?,?,?)",
        (key, value, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def load_app_setting(key: str, default: str = "") -> str:
    try:
        conn = _get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
            )
        """)
        row = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        conn.close()
        return row[0] if row else default
    except Exception:
        return default

# ── 백그라운드 자동 스캔 스케줄러 ────────────────────────────────
def _run_scan_job():
    """장 마감 후 자동 스캔 실행 (별도 스레드)"""
    try:
        from stock_surge_detector import KoreanStockSurgeDetector
        from telegram_alert import send_scan_alert
        det = KoreanStockSurgeDetector(max_gap_pct=7, min_below_days=60, max_cross_days=90)
        det._ob_days = 180  # 70이탈 후 사이클 만료 기간
        results = det.analyze_all_stocks()
        results = [r for r in results if r.get("total_score", 0) >= 40]
        if results:
            save_scan(results)
            send_scan_alert(results)
            print(f"[스케줄러] {date.today()} 스캔 완료: {len(results)}개 종목 → 텔레그램 전송")
    except Exception as e:
        print(f"[스케줄러] 오류: {e}")

def start_scheduler():
    """
    장 마감 후 15:40 자동 스캔 스케줄러 시작
    앱 시작 시 1회 호출
    """
    import time

    def _loop():
        while True:
            now = datetime.now()
            # 평일 15:40 이후 & 오늘 스캔 없으면 실행
            is_weekday = now.weekday() < 5
            after_close = now.hour == 15 and now.minute >= 40
            today_cached = bool(load_scan())

            if is_weekday and after_close and not today_cached:
                _run_scan_job()

            time.sleep(60)  # 1분마다 체크

    t = threading.Thread(target=_loop, daemon=True)
    t.start()

