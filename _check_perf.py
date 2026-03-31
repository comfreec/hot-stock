from cache_db import update_alert_status, get_alert_history
from datetime import date

update_alert_status()
today = date.today().isoformat()
history = get_alert_history(200)

newly_active     = [h for h in history if h["status"] == "active"     and h.get("exit_date") is None and h["alert_date"] == today]
hit_target_today = [h for h in history if h["status"] == "hit_target" and h.get("exit_date") == today]
hit_stop_today   = [h for h in history if h["status"] == "hit_stop"   and h.get("exit_date") == today]
still_pending    = [h for h in history if h["status"] == "pending"]

print(f"오늘({today}) 성과 업데이트 미리보기:")
print(f"  목표가 달성: {len(hit_target_today)}개")
print(f"  손절 이탈:   {len(hit_stop_today)}개")
print(f"  매수가 진입: {len(newly_active)}개")
print(f"  매수 대기:   {len(still_pending)}개")
print()

for h in hit_target_today:
    print(f"  [목표달성] {h['name']} -> {h['exit_price']:,.0f}원 (+{h['return_pct']:.1f}%)")
for h in hit_stop_today:
    print(f"  [손절이탈] {h['name']} -> {h['exit_price']:,.0f}원 ({h['return_pct']:.1f}%)")
for h in newly_active:
    print(f"  [매수진입] {h['name']} -> {h['entry_price']:,.0f}원 터치")
for h in still_pending[:10]:
    print(f"  [대기중]   {h['name']} (알림일: {h['alert_date']}, 매수가: {h['entry_price']:,.0f}원)")
