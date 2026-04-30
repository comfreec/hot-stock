"""셀바스AI 분할매수 상태 및 평단가 계산 검증"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
DB = "/data/scan_cache.db"
conn = sqlite3.connect(DB)

print("=== 셀바스AI trade_orders 전체 이력 ===", flush=True)
rows = conn.execute("""
    SELECT id, symbol, name, status, qty, avg_price, split_step,
           entry_price, target_price, stop_price,
           base_price, trigger2, trigger3,
           step2_price, step2_qty, step3_price, step3_qty,
           split_qty, alert_date
    FROM trade_orders WHERE symbol LIKE '%108860%' OR name LIKE '%셀바스%'
    ORDER BY id
""").fetchall()

for r in rows:
    (oid, sym, name, status, qty, avg_p, step,
     entry, target, stop, base, t2, t3,
     s2p, s2q, s3p, s3q, split_qty, adate) = r
    print(f"\n[id={oid}] {name}({sym})", flush=True)
    print(f"  status={status}  split_step={step}  alert={adate}", flush=True)
    print(f"  entry={entry}  target={target}  stop={stop}", flush=True)
    print(f"  base_price={base}  trigger2={t2}  trigger3={t3}", flush=True)
    print(f"  1차: qty={qty - (s2q or 0) - (s3q or 0)}주 @{base}", flush=True)
    if s2p:
        print(f"  2차: qty={s2q}주 @{s2p}", flush=True)
    if s3p:
        print(f"  3차: qty={s3q}주 @{s3p}", flush=True)
    print(f"  총 qty={qty}  split_qty={split_qty}  avg_price(DB)={avg_p}", flush=True)

    # 평단가 직접 계산
    if s2p and s2q:
        q1 = qty - (s2q or 0) - (s3q or 0)
        q2 = s2q or 0
        q3 = s3q or 0
        p1 = float(base or entry)
        p2 = float(s2p)
        p3 = float(s3p) if s3p else 0
        total_qty = q1 + q2 + q3
        if total_qty > 0:
            if q3 > 0 and p3 > 0:
                calc_avg = (p1*q1 + p2*q2 + p3*q3) / total_qty
            else:
                calc_avg = (p1*q1 + p2*q2) / (q1 + q2)
            print(f"\n  ▶ 평단가 직접계산: ({p1}×{q1} + {p2}×{q2}" +
                  (f" + {p3}×{q3}" if q3 > 0 else "") +
                  f") / {total_qty} = {calc_avg:.1f}", flush=True)
            print(f"  ▶ DB avg_price: {avg_p}", flush=True)
            diff = abs(float(avg_p or 0) - calc_avg)
            if diff > 10:
                print(f"  ⚠️ 차이 {diff:.1f}원 → 불일치!", flush=True)
            else:
                print(f"  ✅ 일치 (차이 {diff:.1f}원)", flush=True)

conn.close()
