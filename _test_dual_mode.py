"""모의/실전 동시 운영 검증 스크립트"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

errors = []

# 1. import 검증
try:
    from auto_trader import (
        _cfg, is_enabled, get_active_modes, KISClient,
        _get_pending_orders, _save_order,
        place_orders, morning_reorder, monitor_positions,
        verify_positions, send_trade_report
    )
    print("✅ import OK", flush=True)
except Exception as e:
    errors.append(f"❌ import 실패: {e}")
    print(errors[-1], flush=True)
    sys.exit(1)

# 2. _cfg mode 파라미터 검증
try:
    m = _cfg("mock")
    r = _cfg("real")
    assert m["mock"] == True,  f"mock cfg mock 플래그 오류: {m['mock']}"
    assert r["mock"] == False, f"real cfg mock 플래그 오류: {r['mock']}"
    print(f"✅ _cfg: mock key={bool(m['app_key'])} / real key={bool(r['app_key'])}", flush=True)
except Exception as e:
    errors.append(f"❌ _cfg 오류: {e}")
    print(errors[-1], flush=True)

# 3. is_enabled 검증
try:
    em = is_enabled("mock")
    er = is_enabled("real")
    print(f"✅ is_enabled: mock={em} real={er}", flush=True)
except Exception as e:
    errors.append(f"❌ is_enabled 오류: {e}")
    print(errors[-1], flush=True)

# 4. get_active_modes 검증
try:
    modes = get_active_modes()
    assert isinstance(modes, list), "list 타입이어야 함"
    print(f"✅ get_active_modes: {modes}", flush=True)
except Exception as e:
    errors.append(f"❌ get_active_modes 오류: {e}")
    print(errors[-1], flush=True)

# 5. KISClient mode 검증
try:
    cm = KISClient("mock")
    cr = KISClient("real")
    assert cm.mock == True,  f"mock client mock 플래그 오류"
    assert cr.mock == False, f"real client mock 플래그 오류"
    assert cm.mode == "mock"
    assert cr.mode == "real"
    print(f"✅ KISClient: mock base={cm.base[:30]} / real base={cr.base[:30]}", flush=True)
except Exception as e:
    errors.append(f"❌ KISClient 오류: {e}")
    print(errors[-1], flush=True)

# 6. _get_pending_orders mode 파라미터 검증
try:
    om = _get_pending_orders("mock")
    or_ = _get_pending_orders("real")
    print(f"✅ _get_pending_orders: mock={len(om)}개 real={len(or_)}개", flush=True)
except Exception as e:
    errors.append(f"❌ _get_pending_orders 오류: {e}")
    print(errors[-1], flush=True)

# 7. trade_orders 테이블 mode 컬럼 존재 확인
try:
    from auto_trader import _get_trade_conn
    conn = _get_trade_conn()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(trade_orders)").fetchall()]
    conn.close()
    assert "mode" in cols, f"mode 컬럼 없음. 현재 컬럼: {cols}"
    print(f"✅ trade_orders mode 컬럼 존재: {cols}", flush=True)
except Exception as e:
    errors.append(f"❌ trade_orders 컬럼 오류: {e}")
    print(errors[-1], flush=True)

# 8. 함수 시그니처 검증 (mode 파라미터 있는지)
import inspect
for fn_name, fn in [
    ("place_orders", place_orders),
    ("morning_reorder", morning_reorder),
    ("monitor_positions", monitor_positions),
    ("verify_positions", verify_positions),
    ("send_trade_report", send_trade_report),
]:
    sig = inspect.signature(fn)
    if "mode" in sig.parameters:
        print(f"✅ {fn_name}(mode=...) OK", flush=True)
    else:
        errors.append(f"❌ {fn_name} mode 파라미터 없음")
        print(errors[-1], flush=True)

# 9. scheduler.py get_active_modes 사용 확인
try:
    with open("scheduler.py", encoding="utf-8") as f:
        sched_src = f.read()
    assert "get_active_modes" in sched_src, "scheduler.py에 get_active_modes 없음"
    assert "morning_reorder(_mode)" in sched_src, "morning_reorder(_mode) 없음"
    assert "monitor_positions(_mode)" in sched_src, "monitor_positions(_mode) 없음"
    print("✅ scheduler.py get_active_modes 사용 확인", flush=True)
except Exception as e:
    errors.append(f"❌ scheduler.py 검증 오류: {e}")
    print(errors[-1], flush=True)

print(f"\n{'='*40}", flush=True)
if errors:
    print(f"❌ 오류 {len(errors)}개 발견:", flush=True)
    for e in errors: print(f"  {e}", flush=True)
else:
    print("✅ 모든 검증 통과 - 배포 가능", flush=True)
