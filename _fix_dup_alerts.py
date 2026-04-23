"""
alert_history 중복 pending 레코드 정리
각 종목의 active 또는 가장 오래된 pending만 남기고 나머지 삭제
"""
import sqlite3
conn = sqlite3.connect('/data/scan_cache.db')

# 중복 종목 확인
rows = conn.execute(
    'SELECT symbol, COUNT(*) as cnt FROM alert_history '
    'WHERE status IN ("pending","active") GROUP BY symbol HAVING cnt > 1'
).fetchall()
print(f'중복 종목: {len(rows)}개')

deleted = 0
for sym, cnt in rows:
    # active 우선, 없으면 가장 오래된 pending 1개만 남김
    all_rows = conn.execute(
        'SELECT id, status, alert_date FROM alert_history '
        'WHERE symbol=? AND status IN ("pending","active") ORDER BY status DESC, alert_date ASC',
        (sym,)
    ).fetchall()
    keep_id = all_rows[0][0]  # 첫 번째(active 우선, 오래된 것) 유지
    for row in all_rows[1:]:
        conn.execute('DELETE FROM alert_history WHERE id=?', (row[0],))
        deleted += 1
        print(f'  삭제: {sym} id={row[0]} {row[1]} [{row[2]}]')

conn.commit()
conn.close()
print(f'\n완료: {deleted}개 중복 레코드 삭제')
