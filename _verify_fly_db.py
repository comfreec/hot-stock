import sqlite3
from datetime import date, timedelta

conn = sqlite3.connect('/data/scan_cache.db')
today = date.today().isoformat()

# pending 종목 확인 및 만료 처리
rows = conn.execute(
    "SELECT id, alert_date, name, status, entry_price FROM alert_history WHERE status='pending' ORDER BY alert_date"
).fetchall()
print(f"pending 종목 {len(rows)}개:")
for r in rows:
    rid, alert_date, name, status, entry = r
    alert_dt = date.fromisoformat(alert_date)
    # 거래일 계산
    trading_days = 0
    cur = alert_dt
    while cur < date.today():
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            trading_days += 1
    expired = trading_days > 5
    print(f"  id={rid} {alert_date} {name} entry={entry} {trading_days}거래일경과 {'→만료처리' if expired else ''}")
    if expired:
        conn.execute("UPDATE alert_history SET status='expired', exit_date=? WHERE id=?", (today, rid))

conn.commit()
print("완료")
conn.close()
