import os
os.environ['TELEGRAM_TOKEN'] = '8686257393:AAGWPuisi_qy995cKC7pIWnCGqpQMljQxgc'
os.environ['TELEGRAM_CHAT_ID'] = '-1003815975342'

from cache_db import get_performance_summary, get_alert_history
from datetime import date, timedelta
from telegram_alert import send_telegram
import yfinance as yf

perf       = get_performance_summary()
history    = get_alert_history(200)
today      = date.today()
week_start = today - timedelta(days=today.weekday())
this_week  = [h for h in history if h["alert_date"] >= week_start.isoformat()]
active_list  = [h for h in this_week if h["status"] == "active"]
closed_list  = [h for h in this_week if h["status"] in ("hit_target","hit_stop","expired")]
pending_list = [h for h in this_week if h["status"] == "pending"]

win_rate = perf["win_rate"]
avg_ret  = perf["avg_return"]
period   = f"{week_start.strftime('%m/%d')} ~ {today.strftime('%m/%d')}"

lines = [f"📅 <b>주간 리포트</b>  {period}", "─"*16]

# 매수 중
if active_list:
    lines.append(f"\n🟢 <b>매수 중</b>  ({len(active_list)}종목)")
    lines.append("─"*16)
    for h in active_list:
        entry_str  = f"₩{h['entry_price']:,.0f}"  if h.get("entry_price")  else "미정"
        target_str = f"₩{h['target_price']:,.0f}" if h.get("target_price") else "?"
        stop_str   = f"₩{h['stop_price']:,.0f}"   if h.get("stop_price")   else "?"
        cur_line = ""
        try:
            if h.get("entry_price"):
                cur = float(yf.Ticker(h["symbol"]).history(period="1d")["Close"].iloc[-1])
                ret = (cur - h["entry_price"]) / h["entry_price"] * 100
                filled = min(int(abs(ret)/2), 8)
                bar = ("🟩" if ret>=0 else "🟥")*filled + "⬜"*(8-filled)
                cur_line = f"\n   {bar}  ₩{cur:,.0f}  <b>({ret:+.1f}%)</b>"
        except:
            pass
        lines.append(
            f"📌 <b>{h['name']}</b>\n"
            f"   매수 {entry_str}  →  목표 {target_str}  /  손절 {stop_str}"
            + cur_line
        )

# 청산 성과
lines.append("\n📊 <b>청산 성과</b>")
lines.append("─"*16)
if perf["total"] > 0:
    filled = round(win_rate/10)
    bar = "🟩"*filled + "⬜"*(10-filled)
    wr_label = "우수" if win_rate>=60 else "보통" if win_rate>=40 else "부진"
    lines.append(f"  {bar}  {win_rate}%  <i>{wr_label}</i>")
    lines.append(f"  ✅ {perf['win']}건  🛑 {perf['loss']}건  ⌛ {perf.get('expired',0)}건")
    ret_arrow = "📈" if avg_ret>=0 else "📉"
    lines.append(f"  {ret_arrow} 평균 수익률  <b>{avg_ret:+.1f}%</b>")
    for h in closed_list:
        icon = "✅" if h["status"]=="hit_target" else ("🛑" if h["status"]=="hit_stop" else "⌛")
        ret_str = f"  <b>{h['return_pct']:+.1f}%</b>" if h.get("return_pct") is not None else ""
        entry_str = f"₩{h['entry_price']:,.0f}" if h.get("entry_price") else "미정"
        lines.append(f"  {icon} {h['name']}{ret_str}  진입 {entry_str}")
else:
    lines.append("  이번 주 청산 없음")

# 매수 대기
if pending_list:
    lines.append(f"\n⏳ <b>매수 대기</b>  ({len(pending_list)}종목)")
    lines.append("─"*16)
    for h in pending_list:
        days = (today - date.fromisoformat(h["alert_date"])).days
        entry_str  = f"₩{h['entry_price']:,.0f}"  if h.get("entry_price")  else "미정"
        target_str = f"₩{h['target_price']:,.0f}" if h.get("target_price") else "?"
        lines.append(
            f"🔵 <b>{h['name']}</b>  <i>{days}일째</i>\n"
            f"   진입가 {entry_str}  →  목표 {target_str}"
        )

lines.append(f"\n🟢 매수 중 {perf.get('active',0)}종목  ·  ⏳ 대기 {perf.get('pending',0)}종목")
lines.append("─"*16)
lines.append("⚠️ <i>투자 참고용 정보입니다</i>")

msg = "\n".join(lines)
print(msg)
print("\n전송:", send_telegram(msg))
