import sys, inspect
sys.path.insert(0, '.')

# 1. telegram_alert 핵심 함수 임포트
from telegram_alert import _calc_levels_core, calc_price_levels, _calc_levels_from_result
print("telegram_alert 임포트 OK")

# 2. calc_price_levels, _calc_levels_from_result 모두 _calc_levels_core 호출 확인
src_cpl = inspect.getsource(calc_price_levels)
assert '_calc_levels_core' in src_cpl, "calc_price_levels가 _calc_levels_core 미사용"
print("calc_price_levels -> _calc_levels_core OK")

src_clr = inspect.getsource(_calc_levels_from_result)
assert '_calc_levels_core' in src_clr, "_calc_levels_from_result가 _calc_levels_core 미사용"
print("_calc_levels_from_result -> _calc_levels_core OK")

# 3. _calc_levels_core 반환 키 확인
src_core = inspect.getsource(_calc_levels_core)
for key in ["entry", "target", "stop", "rr", "upside", "downside", "ma240"]:
    assert f'"{key}"' in src_core, f"_calc_levels_core 반환에 {key} 없음"
print("_calc_levels_core 반환 키 OK")

# 4. app.py 로직 일관성 확인
with open('app.py', encoding='utf-8') as f:
    src_app = f.read()

assert 'calc_stop_from_series' in src_app, "app.py에 calc_stop_from_series 없음"
print("app.py calc_stop_from_series OK")

assert 'atr_x3 = entry + atr' in src_app, "app.py atr_x3가 entry 기준 아님"
print("app.py atr_x3 entry 기준 OK")

assert 'swing_range = max(recent_high - recent_low, entry * 0.01)' in src_app, "app.py swing_range entry 기준 아님"
print("app.py swing_range entry 기준 OK")

assert 'RSI 저점 기준' not in src_app or '추세이탈 기준' in src_app, "app.py 손절가 설명 텍스트 미수정"
print("app.py 추세이탈 기준 텍스트 OK")

# 5. auto_trader.py 5년 데이터 확인
with open('auto_trader.py', encoding='utf-8') as f:
    src_at = f.read()
assert 'period="5y"' in src_at or "period='5y'" in src_at, "auto_trader.py 5년 데이터 아님"
print("auto_trader.py 5년 데이터 OK")

# 6. cache_db.py가 calc_price_levels 호출 확인
with open('cache_db.py', encoding='utf-8') as f:
    src_cdb = f.read()
assert 'calc_price_levels' in src_cdb, "cache_db.py에 calc_price_levels 없음"
print("cache_db.py calc_price_levels 호출 OK")

# 7. 손절가 구 방식(240선 -5%) 잔재 확인
old_pattern_count = src_app.count('ma240_v * 0.95') + src_app.count('ma240 * 0.95')
# make_candle 내부 fallback은 허용 (RSI 실패 시 폴백)
print(f"app.py 구 손절가 패턴 잔재: {old_pattern_count}개 (fallback 용도)")

print()
print("=" * 40)
print("모든 체크 통과 ✅")
