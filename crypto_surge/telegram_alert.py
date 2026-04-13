"""
텔레그램 알림 모듈 - 코인 버전 (주식 버전과 동일한 형식)
"""
import requests
import pandas as pd
import numpy as np
import io
import os
from datetime import date, datetime, timedelta


def _get_config():
    token   = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        try:
            import streamlit as st
            token   = token   or st.secrets.get("TELEGRAM_TOKEN", "")
            chat_id = chat_id or st.secrets.get("TELEGRAM_CHAT_ID", "")
        except:
            pass
    return token, chat_id


def send_telegram(message: str) -> bool:
    token, chat_id = _get_config()
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
        return resp.ok
    except:
        return False


def send_photo(image_bytes: bytes, caption: str = "") -> bool:
    token, chat_id = _get_config()
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
            files={"photo": ("chart.png", image_bytes, "image/png")},
            timeout=30
        )
        return resp.ok
    except:
        return False


def _get_usd_krw() -> float:
    """업비트 기반이므로 환율 변환 불필요 - 1 반환"""
    return 1.0


def _fmt_krw(krw_val, rate=None) -> str:
    """원화 포맷 (업비트 기준이므로 변환 없음)"""
    if krw_val is None:
        return "-"
    return f"₩{int(krw_val):,}"

        close = df["Close"]
        high  = df["High"]
        low   = df["Low"]

        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().dropna().iloc[-1])

        entry = current
        stop  = max(entry * 0.95, entry - atr * 1.5)
        risk  = entry - stop

        target_candidates = sorted([
            entry + risk * 3.0,
            entry + atr * 4.0,
            entry + atr * 6.0,
        ])
        target = next((t for t in target_candidates if t > entry * 1.05), entry + risk * 3.0)
        rr = (target - entry) / risk if risk > 0 else 0

        upside   = (target - entry) / entry * 100
        downside = (stop - entry) / entry * 100

        return {
            "entry":    round(entry, 6),
            "stop":     round(stop, 6),
            "target":   round(target, 6),
            "rr":       round(rr, 2),
            "upside":   round(upside, 2),
            "downside": round(downside, 2),
        }
    except:
        return {}


def format_signals(signals: dict) -> str:
    sig_map = {
        "vol_at_cross":       "📦 돌파 거래량",
        "vol_strong_cross":   "🔥 강한 돌파",
        "recent_vol":         "📊 거래량 급증",
        "bb_squeeze_expand":  "🔥 BB수축→확장",
        "macd_cross":         "📈 MACD골든크로스",
        "ma_align":           "⚡ 이평선 정배열",
        "obv_rising":         "💹 OBV 상승",
        "pullback_recovery":  "🔄 눌림목 반등",
        "rsi_healthy":        "💊 RSI 건강",
        "funding_negative":   "💰 숏과열 반등",
        "4h_above_ma20":      "⏱ 4H MA20 위",
    }
    active = [sig_map[k] for k, v in signals.items() if v is True and k in sig_map]
    return "  ".join(active[:6]) if active else ""


def make_chart_image(symbol: str, name: str, price_levels: dict = None, rate: float = None) -> bytes | None:
    """캔들차트 + 200일선 이미지 생성 (가격 원화 표시)"""
    if rate is None:
        rate = _get_usd_krw()
    try:
        from crypto_surge_detector import fetch_ohlcv
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        df = fetch_ohlcv(symbol, limit=120)
        if df is None or len(df) < 20:
            return None

        df2y = fetch_ohlcv(symbol, limit=300)
        ma200_full = df2y["Close"].rolling(200).mean() if df2y is not None else df["Close"].rolling(200).mean()
        ma200 = ma200_full.reindex(df.index)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7),
                                        gridspec_kw={"height_ratios": [3, 1]},
                                        facecolor="#0e1117")
        ax1.set_facecolor("#0e1117")
        ax2.set_facecolor("#0e1117")

        # Heikin-Ashi
        ha_close = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4
        ha_open  = ha_close.copy()
        for i in range(1, len(ha_open)):
            ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
        ha_high = pd.concat([df["High"], ha_open, ha_close], axis=1).max(axis=1)
        ha_low  = pd.concat([df["Low"],  ha_open, ha_close], axis=1).min(axis=1)

        x = range(len(df))
        for i, xi in enumerate(x):
            color = "#ff3355" if ha_close.iloc[i] >= ha_open.iloc[i] else "#4f8ef7"
            ax1.plot([xi, xi], [ha_low.iloc[i], ha_high.iloc[i]], color=color, linewidth=0.8)
            ax1.bar(xi, abs(ha_close.iloc[i] - ha_open.iloc[i]),
                    bottom=min(ha_open.iloc[i], ha_close.iloc[i]),
                    color=color, width=0.8, alpha=0.9)

        close = df["Close"]
        ax1.plot(x, close.rolling(20).mean().values, color="#ffd700", linewidth=1.2, label="MA20")
        ax1.plot(x, close.rolling(50).mean().values, color="#ff8c42", linewidth=1.2, label="MA50")

        ma200_vals = [float(ma200.iloc[i]) if not pd.isna(ma200.iloc[i]) else None for i in range(len(df))]
        valid_x = [xi for xi, v in zip(x, ma200_vals) if v is not None]
        valid_v = [v for v in ma200_vals if v is not None]
        if valid_x:
            ax1.plot(valid_x, valid_v, color="#ff4b6e", linewidth=2.0, label="MA200", zorder=5)

        current = float(close.iloc[-1])

        if price_levels:
            entry  = price_levels.get("entry", current)
            target = price_levels.get("target")
            stop   = price_levels.get("stop")
            upside   = price_levels.get("upside", 0)
            downside = price_levels.get("downside", 0)

            if target:
                ax1.axhline(y=target, color="#00ff88", linewidth=1.5, linestyle="--", alpha=0.9)
                ax1.text(len(df)-1, target, f" Target {_fmt_krw(target, rate)} (+{upside:.1f}%)",
                         color="#00ff88", fontsize=7, va="bottom", ha="right")
                ax1.axhspan(entry, target, alpha=0.05, color="#00ff88")
            ax1.axhline(y=entry, color="#ffd700", linewidth=1.5, linestyle="-.", alpha=0.9)
            ax1.text(len(df)-1, entry, f" Buy {_fmt_krw(entry, rate)}",
                     color="#ffd700", fontsize=7, va="bottom", ha="right")
            ax1.axhline(y=current, color="#ffffff", linewidth=1.0, linestyle="--", alpha=0.6)
            ax1.text(len(df)-1, current, f" Close {_fmt_krw(current, rate)}",
                     color="#ffffff", fontsize=7, va="bottom", ha="right")
            if stop:
                ax1.axhline(y=stop, color="#ff3355", linewidth=1.5, linestyle="--", alpha=0.9)
                ax1.text(len(df)-1, stop, f" Stop {_fmt_krw(stop, rate)} ({downside:.1f}%)",
                         color="#ff3355", fontsize=7, va="top", ha="right")
                ax1.axhspan(stop, entry, alpha=0.05, color="#ff3355")
        else:
            ax1.axhline(y=current, color="#ffffff", linewidth=0.8, linestyle="--", alpha=0.5)

        ax1.set_title(f"{name} ({symbol})", color="#e0e6f0", fontsize=12, pad=8)
        ax1.tick_params(colors="#8b92a5", labelsize=8)
        ax1.spines[:].set_color("#2d3555")
        ax1.yaxis.set_label_position("right")
        ax1.yaxis.tick_right()
        ax1.legend(loc="upper left", fontsize=7, facecolor="#1a1f35",
                   labelcolor="#8b92a5", edgecolor="#2d3555")

        vol_colors = ["#ff3355" if ha_close.iloc[i] >= ha_open.iloc[i] else "#4f8ef7" for i in range(len(df))]
        ax2.bar(x, df["Volume"].values, color=vol_colors, alpha=0.7, width=0.8)
        ax2.plot(x, df["Volume"].rolling(20).mean().values, color="#ffd700", linewidth=1.0)
        ax2.tick_params(colors="#8b92a5", labelsize=7)
        ax2.spines[:].set_color("#2d3555")
        ax2.yaxis.set_label_position("right")
        ax2.yaxis.tick_right()
        ax2.set_ylabel("Vol", color="#8b92a5", fontsize=7)

        step = max(1, len(df) // 6)
        ax1.set_xticks([])
        ax2.set_xticks(range(0, len(df), step))
        ax2.set_xticklabels(
            [df.index[i].strftime("%m/%d") for i in range(0, len(df), step)],
            color="#8b92a5", fontsize=7
        )

        plt.tight_layout(pad=0.5)
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#0e1117")
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        print(f"[코인 차트 생성 오류] {e}")
        return None


def _make_block(r: dict, lv: dict, idx: int, already_tracking: bool = False) -> str:
    """주식 버전과 동일한 종목 블록 포맷 (가격 원화 표시)"""
    sig_str    = format_signals(r.get("signals", {}))
    price      = r["current_price"]
    rsi        = r.get("rsi", 0)
    fr         = r.get("funding_rate", 0)
    days       = r.get("days_since_cross", 0)
    gap        = r.get("gap_pct", 0)

    rate = _get_usd_krw()

    entry_str  = _fmt_krw(lv['entry'], rate)  if lv else _fmt_krw(price, rate)
    target_str = f"{_fmt_krw(lv['target'], rate)} (+{lv['upside']:.1f}%)" if lv else "-"
    stop_str   = f"{_fmt_krw(lv['stop'], rate)} ({lv['downside']:.1f}%)"  if lv else "-"
    rr_str     = f"{lv['rr']:.1f} : 1" if lv else "-"

    block = (
        f"\n<b>{idx}. {r['name']} ({r['symbol']})</b> ⭐ {r['total_score']}점\n"
        f"📍 매수가:  {entry_str}\n"
        f"🎯 목표가:  {target_str}\n"
        f"🛑 손절가:  {stop_str}\n"
        f"⚖️ 손익비:  {rr_str}\n"
        f"📊 200선 이격 +{gap:.1f}%  |  RSI {rsi:.0f}  |  펀딩비 {fr:+.4f}%\n"
    )
    if sig_str:
        block += f"{sig_str}\n"
    block += "━" * 20
    return block


def send_scan_alert(results: list, send_charts: bool = True):
    """스캔 결과 텔레그램 전송 - 주식 버전과 동일한 형식"""
    if not results:
        return

    from datetime import timezone
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # 신규 / 추적 중 분류
    new_items      = []
    tracking_items = []

    price_levels_map = {}
    for r in results[:10]:
        lv = calc_price_levels(r["symbol"], r["current_price"])
        already_tracking = False
        try:
            from cache_db import _get_conn as _db_conn
            _conn = _db_conn()
            _row = _conn.execute(
                "SELECT entry_price, target_price, stop_price, rr_ratio FROM alert_history "
                "WHERE symbol=? AND status='active' ORDER BY id DESC LIMIT 1",
                (r["symbol"],)
            ).fetchone()
            _conn.close()
            if _row and _row[0]:
                lv = {
                    "entry":    _row[0], "target":   _row[1],
                    "stop":     _row[2], "rr":       _row[3],
                    "upside":   (_row[1]/_row[0]-1)*100 if _row[0] else 0,
                    "downside": (_row[2]/_row[0]-1)*100 if _row[0] else 0,
                }
                already_tracking = True
        except:
            pass
        price_levels_map[r["symbol"]] = lv
        if already_tracking:
            tracking_items.append((r, lv))
        else:
            new_items.append((r, lv))

    # 요약 메시지 구성
    summary_lines = [f"₿ <b>코인 레이더</b> ({now_utc}) — {len(results[:10])}개\n{'━'*20}"]

    idx = 1
    if new_items:
        summary_lines.append(f"\n🆕 <b>신규 탐지</b>\n{'━'*20}")
        for r, lv in new_items:
            summary_lines.append(_make_block(r, lv, idx))
            idx += 1
    else:
        summary_lines.append(f"\n🆕 <b>신규 탐지</b>  없음\n{'━'*20}")

    if tracking_items:
        summary_lines.append(f"\n🔄 <b>재탐지 (추적 중)</b>\n{'━'*20}")
        for r, lv in tracking_items:
            summary_lines.append(_make_block(r, lv, idx, already_tracking=True))
            idx += 1

    summary_lines.append("\n⚠️ 투자 참고용 정보이며 투자 권유가 아닙니다.")
    message = "\n".join(summary_lines)

    if len(message) > 4000:
        chunks = [summary_lines[0]]
        for line in summary_lines[1:]:
            if sum(len(c) for c in chunks) + len(line) > 3800:
                send_telegram("\n".join(chunks))
                chunks = [line]
            else:
                chunks.append(line)
        if chunks:
            send_telegram("\n".join(chunks))
    else:
        send_telegram(message)

    # 차트 전송 (상위 5개)
    if send_charts:
        rate = _get_usd_krw()
        for r in results[:5]:
            lv = price_levels_map.get(r["symbol"], {})
            img = make_chart_image(r["symbol"], r["name"], lv, rate=rate)
            if img:
                caption = (
                    f"<b>{r['name']}</b> ⭐{r['total_score']}점\n"
                    f"📍 매수가: {_fmt_krw(lv['entry'], rate)}\n"
                    f"🎯 목표가: {_fmt_krw(lv['target'], rate)} (+{lv['upside']:.1f}%)\n"
                    f"🛑 손절가: {_fmt_krw(lv['stop'], rate)} ({lv['downside']:.1f}%)\n"
                    f"⚖️ 손익비: {lv['rr']:.1f}:1"
                ) if lv else f"<b>{r['name']}</b>"
                send_photo(img, caption)

    # 성과 추적 DB 저장
    try:
        from cache_db import save_alert_history
        save_alert_history(results, price_levels_map)
        print(f"[코인 성과추적] {len(results)}개 저장 완료")
    except Exception as e:
        print(f"[코인 성과추적] 저장 오류: {e}")


def send_performance_update():
    """성과 업데이트 알림 - 주식 버전과 동일한 형식"""
    try:
        import ccxt
        from cache_db import update_alert_status, get_alert_history, get_performance_summary

        update_alert_status()

        today     = date.today().isoformat()
        today_fmt = date.today().strftime("%Y.%m.%d")
        history   = get_alert_history(200)

        hit_target_today = [h for h in history if h["status"] == "hit_target" and h.get("exit_date") == today]
        hit_stop_today   = [h for h in history if h["status"] == "hit_stop"   and h.get("exit_date") == today]
        active_list      = [h for h in history if h["status"] == "active"]

        if not hit_target_today and not hit_stop_today and not active_list:
            return

        lines = [f"📊 <b>코인 포트폴리오 현황</b>  {today_fmt}", "─" * 16]
        rate = _get_usd_krw()

        if hit_target_today or hit_stop_today:
            lines.append("\n🔔 <b>오늘 청산</b>")
            lines.append("─" * 16)
            for h in hit_target_today:
                ret    = h["return_pct"] or 0
                exit_p = _fmt_krw(h['exit_price'], rate) if h.get("exit_price") else "?"
                lines.append(f"✅ <b>{h['name']}</b>\n   체결가 {exit_p}  |  수익 <b>+{ret:.1f}%</b> 🎉")
            for h in hit_stop_today:
                ret    = h["return_pct"] or 0
                exit_p = _fmt_krw(h['exit_price'], rate) if h.get("exit_price") else "?"
                lines.append(f"🛑 <b>{h['name']}</b>\n   체결가 {exit_p}  |  손실 {ret:.1f}%")

        if active_list:
            lines.append(f"\n🟢 <b>보유 중</b>  ({len(active_list)}종목)")
            lines.append("─" * 16)
            exchange = ccxt.upbit({"enableRateLimit": True})
            for h in active_list:
                days       = (date.today() - date.fromisoformat(h["alert_date"])).days
                entry_str  = _fmt_krw(h['entry_price'], rate)  if h.get("entry_price")  else "미정"
                target_str = _fmt_krw(h['target_price'], rate) if h.get("target_price") else "?"
                stop_str   = _fmt_krw(h['stop_price'], rate)   if h.get("stop_price")   else "?"
                cur_line = ""
                try:
                    if h.get("entry_price"):
                        ticker = exchange.fetch_ticker(h["symbol"])
                        cur = float(ticker["last"])
                        ret = (cur - h["entry_price"]) / h["entry_price"] * 100
                        filled = min(int(abs(ret) / 2), 8)
                        bar = ("🟩" if ret >= 0 else "🟥") * filled + "⬜" * (8 - filled)
                        cur_line = f"\n   {bar}  <b>{_fmt_krw(cur, rate)}  ({ret:+.1f}%)</b>"
                except:
                    pass
                lines.append(
                    f"📌 <b>{h['name']}</b>  <i>{days}일째</i>\n"
                    f"   📍{entry_str} 🎯{target_str} 🛑{stop_str}" + cur_line
                )

        perf = get_performance_summary()
        if perf["total"] > 0:
            lines.append("\n📊 <b>누적 성과</b>")
            lines.append("─" * 16)
            wr = perf["win_rate"]
            filled = round(wr / 10)
            bar = "🟩" * filled + "⬜" * (10 - filled)
            lines.append(f"  {bar}  {wr}%")
            lines.append(f"  ✅ {perf['win']}건  🛑 {perf['loss']}건  ⌛ {perf['expired']}건")
            lines.append(f"  {'📈' if perf['avg_return'] >= 0 else '📉'} 평균 수익률  <b>{perf['avg_return']:+.1f}%</b>")

        lines.append("\n─" * 8)
        lines.append("⚠️ <i>투자 참고용 정보입니다</i>")
        send_telegram("\n".join(lines))

    except Exception as e:
        print(f"[코인 성과추적] 알림 오류: {e}")


def send_weekly_summary(force: bool = False):
    """주간 성과 요약 - 주식 버전과 동일한 형식"""
    try:
        import ccxt
        from cache_db import get_performance_summary, get_alert_history, update_alert_status, get_recent_closed

        if not force and datetime.now().weekday() != 4:
            return

        update_alert_status()

        today      = date.today()
        week_start = today - timedelta(days=today.weekday())
        period     = f"{week_start.strftime('%m/%d')} ~ {today.strftime('%m/%d')}"

        history      = get_alert_history(200)
        active_list  = [h for h in history if h["status"] == "active"]
        perf         = get_performance_summary()

        lines = [f"₿ <b>코인 주간 리포트</b>  {period}", "─" * 16]
        rate = _get_usd_krw()

        if active_list:
            lines.append(f"\n🟢 <b>보유 중</b>  ({len(active_list)}종목)")
            lines.append("─" * 16)
            exchange = ccxt.upbit({"enableRateLimit": True})
            for h in active_list:
                entry_str  = _fmt_krw(h['entry_price'], rate)  if h.get("entry_price")  else "미정"
                target_str = _fmt_krw(h['target_price'], rate) if h.get("target_price") else "?"
                stop_str   = _fmt_krw(h['stop_price'], rate)   if h.get("stop_price")   else "?"
                cur_line = ""
                try:
                    if h.get("entry_price"):
                        ticker = exchange.fetch_ticker(h["symbol"])
                        cur = float(ticker["last"])
                        ret = (cur - h["entry_price"]) / h["entry_price"] * 100
                        filled = min(int(abs(ret) / 2), 8)
                        bar = ("🟩" if ret >= 0 else "🟥") * filled + "⬜" * (8 - filled)
                        cur_line = f"\n   {bar}  {_fmt_krw(cur, rate)}  <b>({ret:+.1f}%)</b>"
                except:
                    pass
                lines.append(
                    f"📌 <b>{h['name']}</b>\n"
                    f"   📍{entry_str} 🎯{target_str} 🛑{stop_str}" + cur_line
                )

        lines.append("\n📊 <b>누적 성과</b>  <i>(전체 기간)</i>")
        lines.append("─" * 16)
        if perf["total"] > 0:
            wr = perf["win_rate"]
            filled = round(wr / 10)
            bar = "🟩" * filled + "⬜" * (10 - filled)
            wr_label = "우수" if wr >= 60 else "보통" if wr >= 40 else "부진"
            lines.append(f"  {bar}  {wr}%  <i>{wr_label}</i>")
            lines.append(f"  ✅ {perf['win']}건  🛑 {perf['loss']}건  ⌛ {perf['expired']}건")
            avg = perf["avg_return"]
            lines.append(f"  {'📈' if avg >= 0 else '📉'} 평균 수익률  <b>{avg:+.1f}%</b>")
            if perf["win"] > 0:
                lines.append(f"     수익 평균  <b>+{perf['avg_win']:.1f}%</b>")
            if perf["loss"] > 0:
                lines.append(f"     손실 평균  <b>{perf['avg_loss']:.1f}%</b>")
        else:
            lines.append("  아직 청산 데이터 없음")

        recent = get_recent_closed(5)
        if recent:
            lines.append(f"\n📋 <b>최근 청산 내역</b>")
            lines.append("─" * 16)
            for r in recent:
                icon    = "💰" if r["status"] == "hit_target" else "🛑"
                ret_str = f"  <b>{r['return_pct']:+.1f}%</b>" if r["return_pct"] is not None else ""
                date_str = r["exit_date"][5:] if r["exit_date"] else ""
                lines.append(f"  {icon} {r['name']}{ret_str}  <i>({date_str})</i>")

        lines.append(f"\n🟢 보유 중 {len(active_list)}종목")
        lines.append("─" * 16)
        lines.append("⚠️ <i>투자 참고용 정보입니다</i>")

        send_telegram("\n".join(lines))
        print("[코인 성과추적] 주간 요약 전송 완료")

    except Exception as e:
        print(f"[코인 성과추적] 주간 요약 오류: {e}")


def send_test_alert():
    return send_telegram(
        "✅ <b>코인 레이더 알림 봇 연결 완료!</b>\n"
        "4시간마다 200일선 돌파 코인을 자동으로 알려드립니다. 🪙"
    )
