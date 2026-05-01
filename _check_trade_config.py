"""자동매매 설정 및 주문 가능 여부 진단"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_trader import _cfg, _get_pending_orders, KISClient, is_enabled, is_order_time
from datetime import datetime
from zoneinfo import ZoneInfo
KST = ZoneInfo("Asia/Seoul")

cfg = _cfg()
print("=== 자동매매 설정 ===", flush=True)
for k, v in cfg.items():
    print(f"  {k}: {v}", flush=True)

print(f"\n=== 현재 시각 ===", flush=True)
print(f"  {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')}", flush=True)
print(f"  주문 가능 시간: {is_order_time()}", flush=True)

print(f"\n=== DB 주문 현황 ===", flush=True)
pending = _get_pending_orders()
active_count = len([o for o in pending if o["status"] in ("pending", "active")])
print(f"  active/pending 종목: {active_count}개 (max_stocks={cfg['max_stocks']})", flush=True)
for o in pending:
    print(f"  [{o['status']}] {o['name']}({o['symbol']}) qty={o['qty']} avg={o['avg_price']}", flush=True)

print(f"\n=== KIS 잔고 ===", flush=True)
if is_enabled():
    client = KISClient()
    balance = client.get_balance()
    cash = balance.get("cash", 0)
    holdings = balance.get("holdings", {})
    print(f"  예수금: ₩{cash:,.0f}", flush=True)
    print(f"  보유 종목: {len(holdings)}개", flush=True)
    print(f"  종목당 예산(budget_per): ₩{cfg['budget_per']:,.0f}", flush=True)
    print(f"  슬롯 여유: {cfg['max_stocks'] - active_count}개", flush=True)
    if active_count >= cfg["max_stocks"]:
        print(f"\n  ⚠️ 최대 보유 종목 수 도달 → 신규 주문 불가", flush=True)
    elif cash < cfg["budget_per"]:
        print(f"\n  ⚠️ 예수금 부족 → 신규 주문 불가", flush=True)
    else:
        print(f"\n  ✅ 신규 주문 가능", flush=True)
else:
    print("  KIS_APP_KEY 없음", flush=True)
