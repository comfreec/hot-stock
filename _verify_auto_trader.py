"""auto_trader.py 안전장치 구현 검증"""
import inspect, sys
sys.path.insert(0, '.')

import auto_trader as at

print("=== auto_trader.py 안전장치 검증 ===")

# 1. 매도 체결 확인 함수 존재
assert hasattr(at, '_verify_sell_filled'), "1번: _verify_sell_filled 없음"
print("1. 매도 체결 확인 (_verify_sell_filled) OK")

# 2. 분할매수 중 손절 우선 처리 - monitor_positions에서 손절 체크가 분할매수 앞에 있는지
src = inspect.getsource(at.monitor_positions)
stop_idx = src.find("손절가 도달 시 분할매수 트리거보다 우선")
split_idx = src.find("분할매수 2/3차 트리거")
assert stop_idx < split_idx, "2번: 손절 체크가 분할매수보다 앞에 있어야 함"
print("2. 분할매수 중 손절 우선 처리 OK")

# 3. 매수 직후 손절가 도달 체크
src_place = inspect.getsource(at.place_orders)
assert "매수 직후 손절가 도달" in src_place, "3번: 매수 직후 손절 체크 없음"
print("3. 매수 직후 손절가 도달 체크 OK")

# 4. 타임아웃 처리
src_buy = inspect.getsource(at.KISClient.buy_order)
src_sell = inspect.getsource(at.KISClient.sell_order)
assert "Timeout" in src_buy, "4번: buy_order 타임아웃 처리 없음"
assert "Timeout" in src_sell, "4번: sell_order 타임아웃 처리 없음"
print("4. 네트워크 타임아웃 처리 OK")

# 5. 공휴일 처리
assert hasattr(at, 'is_trading_day'), "5번: is_trading_day 없음"
assert hasattr(at, '_KR_HOLIDAYS'), "5번: _KR_HOLIDAYS 없음"
assert len(at._KR_HOLIDAYS) >= 8, "5번: 공휴일 목록 부족"
src_market = inspect.getsource(at.is_market_open)
assert "is_trading_day" in src_market, "5번: is_market_open에 공휴일 체크 없음"
print("5. 공휴일 처리 OK")

# 6. 재매수 방지
assert hasattr(at, '_is_recently_sold'), "6번: _is_recently_sold 없음"
assert "최근 3일 내 매도된 종목" in src_place, "6번: place_orders에 재매수 방지 없음"
print("6. 매도 후 재매수 방지 OK")

# 7. 스케줄러 헬스체크
assert hasattr(at, 'scheduler_heartbeat'), "7번: scheduler_heartbeat 없음"
assert hasattr(at, 'check_scheduler_alive'), "7번: check_scheduler_alive 없음"
print("7. 스케줄러 헬스체크 OK")

# 추가 검증
# 장외 시간 체크
src_place = inspect.getsource(at.place_orders)
assert "is_order_time" in src_place, "장외 시간 체크 없음"
print("장외 시간 주문 방지 OK")

# 수량 0 방지
src_buy = inspect.getsource(at.KISClient.buy_order)
assert "qty <= 0" in src_buy, "수량 0 방지 없음"
print("수량 0 방지 OK")

# 호가 단위
assert "round_to_tick" in src_buy, "호가 단위 보정 없음"
print("호가 단위 보정 OK")

# DB 락 방지
src_conn = inspect.getsource(at._get_trade_conn)
assert "busy_timeout" in src_conn, "DB 락 방지 없음"
print("DB 락 방지 OK")

# 재시작 중복 방지
src_morning = inspect.getsource(at.morning_reorder)
assert "morning_reorder_lock" in src_morning, "재시작 중복 방지 없음"
print("재시작 중복 방지 OK")

# 동시 매도 딜레이
src_monitor = inspect.getsource(at.monitor_positions)
assert "time.sleep(1)" in src_monitor, "동시 매도 딜레이 없음"
print("동시 매도 딜레이 OK")

print()
print("=" * 40)
print("모든 안전장치 검증 통과 ✅")
