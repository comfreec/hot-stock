"""
2분 뒤 일일 스캔 알림 + 주간 리포트 둘 다 전송
"""
import time
from datetime import datetime, date
import sqlite3
import os

# DB pending 상태 확인 및 만료 처리
db_path = "/data/scan_cache.db" if os.path.isdir("/data") else "scan_cache.db"
try:
    conn = sqlite3.connect(db_path)
    # 5거래일 초과 pending 종목 만료 처리 (달력일 기준 7일 이상)
    r = conn.execute(
        "UPDATE alert_history SET status='expired', exit_date=date('now') "
        "WHERE status IN ('pending','active') AND (julianday('now') - julianday(alert_date)) > 7"
    )
    conn.commit()
    print(f"[DB] 만료 처리: {r.rowcount}개")
    rows = conn.execute(
        "SELECT id, alert_date, name, status, entry_price FROM alert_history WHERE status='pending' ORDER BY alert_date"
    ).fetchall()
    today = date.today()
    print(f"[DB] 남은 pending {len(rows)}개:")
    for row in rows:
        rid, alert_date, name, status, entry = row
        days = (today - date.fromisoformat(alert_date)).days
        print(f"  id={rid} {alert_date} {name} {days}일경과")
    conn.close()
except Exception as e:
    print(f"[DB] 오류: {e}")

print(f"[{datetime.now().strftime('%H:%M:%S')}] 2분 후 전송 시작...")
time.sleep(120)

print(f"[{datetime.now().strftime('%H:%M:%S')}] 전송 중...")

# 1. 일일 스캔 알림 (오늘 캐시된 결과 사용)
try:
    from cache_db import load_scan
    from telegram_alert import send_scan_alert
    results = load_scan()
    if results:
        send_scan_alert(results)
        print(f"  ✅ 일일 스캔 알림 전송 완료 ({len(results)}종목)")
    else:
        from telegram_alert import send_telegram
        send_telegram("📭 오늘 스캔 결과가 없습니다. (캐시 없음)")
        print("  ⚠️ 스캔 결과 없음 - 빈 알림 전송")
except Exception as e:
    print(f"  ❌ 일일 알림 오류: {e}")

time.sleep(3)

# 2. 주간 리포트
try:
    from telegram_alert import send_weekly_summary
    send_weekly_summary(force=True)
    print(f"  ✅ 주간 리포트 전송 완료")
except Exception as e:
    print(f"  ❌ 주간 리포트 오류: {e}")

print(f"[{datetime.now().strftime('%H:%M:%S')}] 완료")
