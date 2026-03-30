import sqlite3, os
from datetime import date
db = os.path.join('.', 'scan_cache.db')
conn = sqlite3.connect(db)
today = date.today().isoformat()
conn.execute("DELETE FROM scan_results WHERE scan_date=?", (today,))
conn.commit()
conn.close()
print(f'오늘({today}) 캐시 삭제 완료')
