import sqlite3
conn = sqlite3.connect('scan_cache.db')
conn.execute("DELETE FROM alert_history WHERE symbol='086520.KQ'")
conn.execute("DELETE FROM scan_results WHERE scan_date=date('now')")
conn.commit()
conn.close()
print('삭제 완료')
