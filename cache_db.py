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

DB_PATH = os.path.join(os.path.dirname(__file__), "scan_cache.db")

def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
    conn.commit()
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
    except:
        pass  # DB 없으면 session_state로 폴백 (호출부에서 처리)

def remove_favorite(symbol: str):
    try:
        conn = _get_conn()
        conn.execute("DELETE FROM favorites WHERE symbol=?", (symbol,))
        conn.commit()
        conn.close()
    except:
        pass

def get_favorites() -> list:
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT symbol, name, added_at FROM favorites ORDER BY added_at DESC"
        ).fetchall()
        conn.close()
        return [{"symbol": r[0], "name": r[1], "added_at": r[2]} for r in rows]
    except:
        return []

def is_favorite(symbol: str) -> bool:
    try:
        conn = _get_conn()
        row = conn.execute("SELECT 1 FROM favorites WHERE symbol=?", (symbol,)).fetchone()
        conn.close()
        return row is not None
    except:
        return False

# ── 백그라운드 자동 스캔 스케줄러 ────────────────────────────────
def _run_scan_job():
    """장 마감 후 자동 스캔 실행 (별도 스레드)"""
    try:
        from stock_surge_detector import KoreanStockSurgeDetector
        from telegram_alert import send_scan_alert
        det = KoreanStockSurgeDetector(max_gap_pct=15, min_below_days=60, max_cross_days=90)
        results = det.analyze_all_stocks()
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
