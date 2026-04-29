"""DB 상태를 텔레그램으로 전송"""
import sqlite3, os
from telegram_alert import send_telegram

db = "/data/scan_cache.db"
if not os.path.exists(db):
    db = "scan_cache.db"

conn = sqlite3.connect(db)

r1 = conn.execute("SELECT symbol, name, status FROM alert_history WHERE status IN ('active','pending') ORDER BY alert_date DESC").fetchall()
r2 = conn.execute("SELECT symbol, name, status FROM trade_orders WHERE status IN ('active','pending') ORDER BY created_at DESC").fetchall()
conn.close()

msg = f"📊 <b>DB 상태 확인</b>\n\n"
msg += f"🔵 alert_history active/pending: {len(r1)}개\n"
for s, n, st in r1:
    msg += f"  • {n} ({s}) [{st}]\n"

msg += f"\n🟢 trade_orders active/pending: {len(r2)}개\n"
for s, n, st in r2:
    msg += f"  • {n} ({s}) [{st}]\n"

send_telegram(msg)
print("전송 완료")
print(msg)
