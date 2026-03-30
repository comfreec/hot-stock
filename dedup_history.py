import sqlite3, os
db = os.path.join('.', 'scan_cache.db')
conn = sqlite3.connect(db)

# 같은 날짜+종목 중 id가 가장 작은 것(첫 번째)만 남기고 나머지 삭제
conn.execute("""
    DELETE FROM alert_history
    WHERE id NOT IN (
        SELECT MIN(id) FROM alert_history
        GROUP BY alert_date, symbol
    )
""")
deleted = conn.total_changes
conn.commit()
conn.close()
print(f"중복 {deleted}개 삭제 완료")
