"""셀바스AI 평단가 및 trigger 수정"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
DB = "/data/scan_cache.db"
conn = sqlite3.connect(DB)

# 현재 상태 조회
row = conn.execute("""
    SELECT id, qty, avg_price, base_price, trigger2, trigger3,
           step2_price, step2_qty, step3_price, step3_qty, entry_price
    FROM trade_orders WHERE symbol='108860.KQ' AND status='active'
    ORDER BY id DESC LIMIT 1
""").fetchone()

if not row:
    print("셀바스AI active 종목 없음", flush=True)
    conn.close()
    exit()

(oid, qty, avg_p, base, t2, t3, s2p, s2q, s3p, s3q, entry) = row
print(f"현재 DB: id={oid} qty={qty} avg={avg_p}", flush=True)
print(f"  base={base} t2={t2} t3={t3}", flush=True)
print(f"  1차: @{base} × {qty-(s2q or 0)-(s3q or 0)}주", flush=True)
print(f"  2차: @{s2p} × {s2q}주", flush=True)
print(f"  3차: @{s3p} × {s3q}주", flush=True)

# 평단가 재계산
q1 = qty - (s2q or 0) - (s3q or 0)
q2 = s2q or 0
q3 = s3q or 0
p1 = float(base or entry)
p2 = float(s2p or p1)
p3 = float(s3p or p1)

if q1 + q2 + q3 > 0:
    correct_avg = (p1*q1 + p2*q2 + p3*q3) / (q1 + q2 + q3)
    print(f"\n올바른 평단가: ({p1}×{q1} + {p2}×{q2} + {p3}×{q3}) / {q1+q2+q3} = {correct_avg:.2f}", flush=True)
else:
    correct_avg = p1
    print(f"수량 0 → 평단가 = {p1}", flush=True)

# trigger 재계산 (base_price 기준 -2%/-4%)
correct_t2 = int(p1 * 0.98)
correct_t3 = int(p1 * 0.96)
print(f"올바른 trigger2: {correct_t2} (현재: {t2})", flush=True)
print(f"올바른 trigger3: {correct_t3} (현재: {t3})", flush=True)

# DB 수정
conn.execute("""
    UPDATE trade_orders
    SET avg_price=?, trigger2=?, trigger3=?
    WHERE id=?
""", (round(correct_avg, 2), correct_t2, correct_t3, oid))
conn.commit()
print(f"\n✅ 수정 완료: avg_price={correct_avg:.2f}, trigger2={correct_t2}, trigger3={correct_t3}", flush=True)

# alert_history도 동기화
conn.execute("""
    UPDATE alert_history SET avg_price=?
    WHERE symbol='108860.KQ' AND status IN ('active','pending')
""", (round(correct_avg, 2),))
conn.commit()
print("✅ alert_history 동기화 완료", flush=True)

conn.close()
