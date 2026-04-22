"""
자동매매 리포트 재전송 - KIS API 실패 시 yfinance로 현재가 조회
"""
import os, sys
os.chdir('/app')
sys.path.insert(0, '/app')
if os.path.isdir('/data'):
    os.environ['DB_PATH'] = '/data/scan_cache.db'

import yfinance as yf
from auto_trader import _get_trade_conn, _send_admin, _cfg
from datetime import date

cfg = _cfg()
mock_tag = "[모의] " if cfg["mock"] else ""
today = date.today().isoformat()
month_start = date.today().strftime("%Y-%m-01")

conn = _get_trade_conn()

active_rows = conn.execute("""
    SELECT id, name, symbol, avg_price, target_price, stop_price,
           qty, split_step, entry_price, alert_date
    FROM trade_orders WHERE status='active'
""").fetchall()

pending_rows = conn.execute("""
    SELECT name, symbol, entry_price, target_price, alert_date
    FROM trade_orders WHERE status='pending'
""").fetchall()

all_closed = conn.execute("""
    SELECT name, symbol, return_pct, status, exit_date
    FROM trade_orders
    WHERE status IN ('hit_target','hit_stop') AND return_pct IS NOT NULL
""").fetchall()

month_closed = conn.execute("""
    SELECT return_pct FROM trade_orders
    WHERE status IN ('hit_target','hit_stop')
      AND exit_date >= ? AND return_pct IS NOT NULL
""", (month_start,)).fetchall()

conn.close()

# yfinance로 현재가 조회
def get_price_yf(symbol):
    try:
        d = yf.Ticker(symbol).history(period='2d')
        if len(d) > 0:
            return float(d['Close'].iloc[-1])
    except:
        pass
    return None

SEP  = "━" * 22
SEP2 = "─" * 18
lines = [f"🤖 {mock_tag}<b>자동매매 현황</b>  {today}", SEP]

# 활성 종목
if active_rows:
    lines.append(f"\n📊 <b>보유 중</b>  ({len(active_rows)}종목)")
    for row in active_rows:
        rid, name, sym, avg_p, target, stop, qty, step, entry, alert_date = row
        avg_p = float(avg_p or entry or 0)
        cur = get_price_yf(sym)
        days = (date.today() - date.fromisoformat(alert_date)).days if alert_date else 0
        invest = avg_p * qty if avg_p and qty else 0
        lines.append(f"\n{SEP2}")
        step_icon = f"({step}차)" if step and step > 1 else ""
        lines.append(f"📌 <b>{name}</b> {step_icon}  <i>{days}일째</i>")
        if cur and avg_p:
            ret = (cur - avg_p) / avg_p * 100
            pnl = int((cur - avg_p) * qty)
            p_sign = "+" if pnl >= 0 else ""
            to_stop = (cur - stop) / cur * 100 if stop else 0
            # 게이지 바
            if target and stop and target > stop:
                if ret >= 0:
                    ratio = min((cur - avg_p) / (target - avg_p), 1.0) if target > avg_p else 0
                    filled = round(ratio * 8)
                    bar = "🟩" * filled + "⬜" * (8 - filled)
                else:
                    ratio = min((avg_p - cur) / (avg_p - stop), 1.0) if avg_p > stop else 0
                    filled = round(ratio * 8)
                    bar = "🟥" * filled + "⬜" * (8 - filled)
            else:
                bar = "⬜" * 8
            lines.append(
                f"  평단 ₩{avg_p:,.0f} × {qty}주\n"
                f"  {bar}  <b>{ret:+.1f}%  {p_sign}₩{pnl:,}</b>\n"
                f"  현재 ₩{cur:,.0f}\n"
                f"  🎯 ₩{target:,}  🛑 ₩{stop:,}  (손절까지 {to_stop:.1f}%)"
            )
        else:
            lines.append(f"  평단 ₩{avg_p:,.0f} × {qty}주  (현재가 조회 중)")

# 대기 종목
if pending_rows:
    lines += [f"\n{SEP2}", f"⏳ <b>매수 대기</b>  ({len(pending_rows)}종목)"]
    for row in pending_rows:
        name, sym, entry, target, alert_date = row
        days = (date.today() - date.fromisoformat(alert_date)).days if alert_date else 0
        lines.append(f"🔵 <b>{name}</b>  <i>{days}일째</i>\n   📍₩{entry:,}  🎯₩{target:,}")

# 이달 성과
if month_closed:
    rets = [r[0] for r in month_closed if r[0] is not None]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    avg = sum(rets)/len(rets) if rets else 0
    wr = len(wins)/len(rets)*100 if rets else 0
    lines += [f"\n{SEP2}", f"📅 <b>이달 성과</b>  ({len(rets)}건)"]
    lines.append(f"  승률 {wr:.0f}%  평균 {avg:+.1f}%  ✅{len(wins)} 🛑{len(losses)}")

# 누적 성과
if all_closed:
    wins_all = [(r[0],r[2]) for r in all_closed if r[2]=='hit_target' and r[2] is not None]
    all_ret = [r[2] for r in all_closed if r[2] is not None]
    # fix: return_pct is index 2 but status is index 3
    wins_all = [r for r in all_closed if r[3]=='hit_target' and r[2] is not None]
    losses_all = [r for r in all_closed if r[3]=='hit_stop' and r[2] is not None]
    all_ret2 = [r[2] for r in all_closed if r[2] is not None]
    total = len(all_ret2)
    wr2 = len(wins_all)/total*100 if total else 0
    avg2 = sum(all_ret2)/len(all_ret2) if all_ret2 else 0
    lines += [f"\n{SEP2}", f"📊 <b>누적 성과</b>  ({total}건)"]
    lines.append(f"  승률 {wr2:.0f}%  평균 {avg2:+.1f}%  ✅{len(wins_all)} 🛑{len(losses_all)}")

lines += [f"\n{SEP}", "⚠️ <i>자동매매 참고용 정보입니다</i>"]

msg = "\n".join(lines)
_send_admin(msg)
print("자동매매 리포트 전송 완료")
print(f"활성: {len(active_rows)}개, 대기: {len(pending_rows)}개")

# 채널 주간보고서
print("\n[채널] 성과 업데이트 알림 전송 중...")
try:
    import sqlite3 as _sq
    from telegram_alert import send_telegram, get_financial_data
    from datetime import date as _date

    _conn = _sq.connect('/data/scan_cache.db')
    history = []
    rows_h = _conn.execute("""
        SELECT id, alert_date, symbol, name, score,
               entry_price, entry_label, target_price, stop_price, rr_ratio,
               status, exit_price, exit_date, return_pct, created_at,
               avg_price, split_step
        FROM alert_history ORDER BY alert_date DESC, score DESC LIMIT 200
    """).fetchall()
    keys = ["id","alert_date","symbol","name","score","entry_price","entry_label",
            "target_price","stop_price","rr_ratio","status","exit_price","exit_date",
            "return_pct","created_at","avg_price","split_step"]
    history = [dict(zip(keys, r)) for r in rows_h]

    active_list = [h for h in history if h["status"] in ("active","pending")]
    hit_target  = [h for h in history if h["status"] == "hit_target"]
    hit_stop    = [h for h in history if h["status"] == "hit_stop"]
    _conn.close()

    if not history:
        print("  성과 데이터 없음")
    else:
        total_closed = len(hit_target) + len(hit_stop)
        wr = round(len(hit_target)/total_closed*100,1) if total_closed else 0
        all_ret = [h["return_pct"] for h in hit_target+hit_stop if h["return_pct"] is not None]
        avg_ret = round(sum(all_ret)/len(all_ret),2) if all_ret else 0

        lines = [
            f"📊 <b>성과 추적 업데이트</b>  {_date.today()}",
            "━"*22,
            f"✅ 목표가 달성: <b>{len(hit_target)}건</b>",
            f"🛑 손절: <b>{len(hit_stop)}건</b>",
            f"📈 승률: <b>{wr}%</b>  평균수익: <b>{avg_ret:+.2f}%</b>",
        ]
        if active_list:
            lines.append(f"\n🔄 추적 중: {len(active_list)}종목")
            for h in active_list[:5]:
                lines.append(f"  • {h['name']} ({h['alert_date']})")

        send_telegram("\n".join(lines))
        print(f"  완료 (총 {total_closed}건, 승률 {wr}%)")
except Exception as e:
    print(f"  오류: {e}")
    import traceback; traceback.print_exc()
