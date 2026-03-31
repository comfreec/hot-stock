"""
텔레그램 알림 모듈 v2.0
- 급등 예고 종목 자동 알림
- 매수가/목표가/손절가/손익비 포함
- 캔들차트 이미지 첨부
- 재무 데이터 (PER/PBR)
"""
import requests
import pandas as pd
import numpy as np
import io
from datetime import date

TELEGRAM_TOKEN   = "8686257393:AAGWPuisi_qy995cKC7pIWnCGqpQMljQxgc"
TELEGRAM_CHAT_ID = "-1003815975342"  # 주식 급등 알림 채널

def send_telegram(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        return resp.ok
    except:
        return False


def send_photo(image_bytes: bytes, caption: str = "") -> bool:
    """이미지 전송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        resp = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML"
        }, files={"photo": ("chart.png", image_bytes, "image/png")}, timeout=30)
        return resp.ok
    except:
        return False


def make_chart_image(symbol: str, name: str, price_levels: dict = None) -> bytes | None:
    """캔들차트 + 240일선 + 목표가/손절가 수평선 이미지 생성"""
    try:
        import yfinance as yf
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        df = yf.Ticker(symbol).history(period="6mo")
        df = df.dropna(subset=["Open","High","Low","Close"])
        if len(df) < 20:
            return None

        df2y = yf.Ticker(symbol).history(period="2y").dropna(subset=["Close"])
        ma240_full = df2y["Close"].rolling(240).mean()
        ma240 = ma240_full.reindex(df.index)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7),
                                        gridspec_kw={"height_ratios": [3, 1]},
                                        facecolor="#0e1117")
        ax1.set_facecolor("#0e1117")
        ax2.set_facecolor("#0e1117")

        # Heikin-Ashi 계산
        ha_close = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4
        ha_open = ha_close.copy()
        for i in range(1, len(ha_open)):
            ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
        ha_high = pd.concat([df["High"], ha_open, ha_close], axis=1).max(axis=1)
        ha_low  = pd.concat([df["Low"],  ha_open, ha_close], axis=1).min(axis=1)

        # Heikin-Ashi 캔들차트
        for i in range(len(df)):
            color = "#ff3355" if ha_close.iloc[i] >= ha_open.iloc[i] else "#4f8ef7"
            ax1.plot([i, i], [ha_low.iloc[i], ha_high.iloc[i]], color=color, linewidth=0.8)
            ax1.bar(i, abs(ha_close.iloc[i] - ha_open.iloc[i]),
                    bottom=min(ha_open.iloc[i], ha_close.iloc[i]),
                    color=color, width=0.6, alpha=0.9)

        close = df["Close"]
        x = range(len(df))
        ax1.plot(x, close.rolling(20).mean().values, color="#ffd700", linewidth=1.2, label="MA20")
        ax1.plot(x, close.rolling(60).mean().values, color="#ff8c42", linewidth=1.2, label="MA60")
        if ma240.notna().any():
            ax1.plot(x, ma240.values, color="#ff4b6e", linewidth=2.0, label="MA240")

        current = float(close.iloc[-1])

        # ── 목표가 / 현재가 / 손절가 수평선 ──
        if price_levels:
            target  = price_levels.get("target")
            stop    = price_levels.get("stop")
            entry   = price_levels.get("entry", current)
            entry_label = price_levels.get("entry_label", "매수")
            upside  = price_levels.get("upside", 0)
            downside = price_levels.get("downside", 0)

            if target:
                ax1.axhline(y=target, color="#00ff88", linewidth=1.5, linestyle="--", alpha=0.9)
                ax1.text(len(df)-1, target, f" Target ₩{target:,.0f} (+{upside:.1f}%)",
                         color="#00ff88", fontsize=7, va="bottom", ha="right")
                ax1.axhspan(entry, target, alpha=0.05, color="#00ff88")

            # 매수가 (240선 근거)
            if entry < current:
                label_en = {"240선": "MA240", "240선+버퍼": "MA240", "MA20": "MA20", "스윙저점": "SwingLow", "현재가": "Close"}.get(entry_label, entry_label)
                ax1.axhline(y=entry, color="#ffd700", linewidth=1.5, linestyle="-.", alpha=0.9)
                ax1.text(len(df)-1, entry, f" Buy ₩{entry:,.0f}",
                         color="#ffd700", fontsize=7, va="bottom", ha="right")

            ax1.axhline(y=current, color="#ffffff", linewidth=1.0, linestyle="--", alpha=0.6)
            ax1.text(len(df)-1, current, f" Close ₩{current:,.0f}",
                     color="#ffffff", fontsize=7, va="bottom", ha="right")

            if stop:
                ax1.axhline(y=stop, color="#ff3355", linewidth=1.5, linestyle="--", alpha=0.9)
                ax1.text(len(df)-1, stop, f" Stop ₩{stop:,.0f} ({downside:.1f}%)",
                         color="#ff3355", fontsize=7, va="top", ha="right")
                ax1.axhspan(stop, entry, alpha=0.05, color="#ff3355")
        else:
            ax1.axhline(y=current, color="#ffffff", linewidth=0.8, linestyle="--", alpha=0.5)

        ax1.set_title(f"{symbol}", color="#e0e6f0", fontsize=12, pad=8)
        ax1.tick_params(colors="#8b92a5", labelsize=8)
        ax1.spines[:].set_color("#2d3555")
        ax1.yaxis.set_label_position("right")
        ax1.yaxis.tick_right()
        ax1.legend(loc="upper left", fontsize=7, facecolor="#1a1f35",
                   labelcolor="#8b92a5", edgecolor="#2d3555")

        # 거래량
        vol = df["Volume"]
        vol_colors = ["#ff3355" if df["Close"].iloc[i] >= df["Open"].iloc[i]
                      else "#4f8ef7" for i in range(len(df))]
        ax2.bar(x, vol.values, color=vol_colors, alpha=0.7, width=0.6)
        ax2.plot(x, vol.rolling(20).mean().values, color="#ffd700", linewidth=1.0)
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
        print(f"차트 생성 실패 {symbol}: {e}")
        return None


def _get_korean_font():
    """한글 폰트 반환 (없으면 None)"""
    try:
        from matplotlib import font_manager
        for name in ["Malgun Gothic", "NanumGothic", "AppleGothic", "NotoSansCJK"]:
            try:
                return font_manager.FontProperties(family=name)
            except:
                pass
    except:
        pass
    return None


def round_to_tick(price: float) -> int:
    """한국 주식 호가 단위로 반올림"""
    if price < 2000:      tick = 1
    elif price < 5000:    tick = 5
    elif price < 20000:   tick = 10
    elif price < 50000:   tick = 50
    elif price < 200000:  tick = 100
    elif price < 500000:  tick = 500
    else:                 tick = 1000
    return int(round(price / tick) * tick)


def get_financial_data(symbol: str) -> dict:
    """재무 데이터 (PER, PBR) 조회"""
    try:
        import yfinance as yf
        info = yf.Ticker(symbol).info
        per = info.get("trailingPE") or info.get("forwardPE")
        pbr = info.get("priceToBook")
        eps = info.get("trailingEps")
        return {
            "per": round(per, 1) if per and per > 0 else None,
            "pbr": round(pbr, 2) if pbr and pbr > 0 else None,
            "eps": round(eps, 0) if eps else None,
        }
    except:
        return {}


def calc_price_levels(symbol: str) -> dict:
    """목표가/손절가/손익비 + 근거 있는 매수가 계산"""
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).history(period="2y")
        df = df.dropna(subset=["Open","High","Low","Close"])
        if len(df) < 30:
            return {}

        close = df["Close"]
        high  = df["High"]
        low   = df["Low"]
        current = float(close.iloc[-1])

        # ATR
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr_s = tr.rolling(14).mean().dropna()
        atr = float(atr_s.iloc[-1]) if len(atr_s) > 0 else current * 0.02

        # ── 매수가: 240선 근처 근거 있는 눌림목 진입가 ──────────────────
        ma240 = close.rolling(240).mean()
        ma20  = float(close.rolling(20).mean().iloc[-1])
        ma240_v = float(ma240.iloc[-1]) if not pd.isna(ma240.iloc[-1]) else None
        swing_low_20 = float(low.tail(20).min())

        # 우선순위: 240선 → 스윙저점 → MA20
        # 현재가 대비 2% 이상 낮고 240선 위인 것만 유효
        entry_candidates = []
        if ma240_v:
            entry_candidates.append(("240선+버퍼", ma240_v * 1.005))
        entry_candidates.append(("스윙저점", swing_low_20))
        entry_candidates.append(("MA20", ma20))

        valid = [
            (label, price) for label, price in entry_candidates
            if price < current * 0.98 and (ma240_v is None or price >= ma240_v * 0.99)
        ]
        if valid:
            entry_label, entry = max(valid, key=lambda x: x[1])  # 가장 높은 값 = 현재가에 가장 가까운 지지선
        else:
            entry_label, entry = "현재가", current

        # ── 분할매수 평균가 계산 (표시용) ───────────────────────
        entry_low_v = ma240_v if ma240_v else entry
        avg_entry = (entry_low_v + entry) / 2

        # ── 손절가: 스윙저점 - ATR*0.5 (변동성 기반, 명확한 무효화 지점) ──
        stop = swing_low_20 - atr * 0.5
        stop = max(stop, entry * 0.85)  # 안전망: -15% 이하 방지
        risk = max(entry - stop, entry * 0.01)

        # 목표가
        recent_high = float(high.tail(120).max())
        recent_low  = float(low.tail(120).min())
        swing_range = max(recent_high - recent_low, entry * 0.01)

        # 직전 저항 고점들 찾기 (20일, 60일, 120일 고점)
        resist_20  = float(high.tail(20).max())
        resist_60  = float(high.tail(60).max())
        resist_120 = recent_high

        candidates = sorted([
            x for x in [
                # 피보나치 되돌림 기반
                recent_low + swing_range * 1.272,
                recent_low + swing_range * 1.618,
                recent_low + swing_range * 2.0,
                # 직전 저항 고점 기반 (가장 현실적)
                resist_20  * 1.01,
                resist_60  * 1.01,
                resist_120 * 1.01,
                # ATR 배수 기반 (최소 목표)
                entry + atr * 3.0,
                entry + atr * 5.0,
            ] if x > entry * 1.03
        ])

        min_rr3 = entry + risk * 3.0
        valid_t = [x for x in candidates if x >= min_rr3]
        if valid_t:
            weights = [1 / (x - entry) for x in valid_t]
            target = sum(x * w for x, w in zip(valid_t, weights)) / sum(weights)
        elif candidates:
            target = candidates[-1]
        else:
            target = entry + risk * 3.0

        target = min(target, entry * 2.0)

        # 호가 단위 적용
        entry      = round_to_tick(entry)
        target     = round_to_tick(target)
        stop       = round_to_tick(stop)
        ma240_tick = round_to_tick(ma240_v) if ma240_v else entry

        rr       = (target - entry) / (entry - stop + 1e-9)
        upside   = (target / entry - 1) * 100
        downside = (stop   / entry - 1) * 100

        return {
            "current":     current,
            "entry":       entry,
            "entry_label": entry_label,
            "ma240":       ma240_tick,
            "target":      target,
            "stop":        stop,
            "rr":          rr,
            "upside":      upside,
            "downside":    downside,
        }
    except:
        return {}


def format_signals(signals: dict) -> str:
    sig_map = {
        "vol_at_cross":          "📦 돌파 거래량",
        "recent_vol":            "📊 거래량 급증",
        "bb_squeeze_expand":     "🔥 BB수축→확장",
        "macd_cross":            "📈 MACD골든크로스",
        "ma240_turning_up":      "🔼 240선 상승전환",
        "ma_align":              "⚡ 이평선 정배열",
        "obv_rising":            "💹 OBV 상승",
        "ichimoku_bull":         "☁️ 일목균형표",
        "near_52w_high":         "🏆 52주 신고가",
        "stoch_cross":           "📉 스토캐스틱",
        "mfi_oversold_recovery": "💰 MFI 반등",
    }
    active = [sig_map[k] for k, v in signals.items() if v is True and k in sig_map]
    return "  ".join(active[:6]) if active else ""


def send_scan_alert(results: list, send_charts: bool = True):
    """스캔 결과 텔레그램 전송 (차트 이미지 포함)"""
    if not results:
        return

    today = date.today().strftime("%Y-%m-%d")

    # 요약 메시지 먼저 전송
    summary_lines = [f"🚀 <b>급등 예고 종목</b> ({today} 장마감) — {len(results[:10])}개\n{'━'*20}"]

    for i, r in enumerate(results[:10], 1):
        lv = calc_price_levels(r["symbol"])
        fin = get_financial_data(r["symbol"])
        s   = r.get("signals", {})
        sig_str = format_signals(s)

        entry_low  = lv['ma240'] if lv and lv.get('ma240') else (lv['stop'] if lv else None)
        entry_high = lv['entry'] if lv else None

        if lv and entry_low and entry_high:
            split_str = f"₩{entry_low:,.0f}~₩{entry_high:,.0f}"
        else:
            split_str = f"₩{r['current_price']:,.0f}"

        target_str = f"₩{lv['target']:,.0f} (+{lv['upside']:.1f}%)" if lv else "-"
        stop_str   = f"₩{lv['stop']:,.0f} ({lv['downside']:.1f}%)" if lv else "-"
        rr_str     = f"{lv['rr']:.1f} : 1" if lv else "-"

        per_str = f"PER {fin['per']}" if fin.get("per") else ""
        pbr_str = f"PBR {fin['pbr']}" if fin.get("pbr") else ""
        fin_str = "  ".join(filter(None, [per_str, pbr_str]))

        block = (
            f"\n<b>{i}. {r['name']} ({r['symbol']})</b> ⭐ {r['total_score']}점\n"
            f"📍 분할매수:  {split_str}\n"
            f"🎯 목표가:  {target_str}\n"
            f"🛑 손절가:  {stop_str}\n"
            f"⚖️ 손익비:  {rr_str}\n"
        )
        if fin_str:
            block += f"📊 {fin_str}\n"
        if sig_str:
            block += f"{sig_str}\n"
        block += "━" * 20
        summary_lines.append(block)

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

    # 차트 이미지 전송 (종목별)
    # 차트 이미지 전송 + 성과 추적 저장
    price_levels_map = {}
    if send_charts:
        for r in results[:5]:
            lv = calc_price_levels(r["symbol"])
            price_levels_map[r["symbol"]] = lv
            img = make_chart_image(r["symbol"], r["name"], price_levels=lv)
            if img:
                if lv:
                    caption = (
                        f"<b>{r['name']}</b> ⭐{r['total_score']}점\n"
                        f"📍 분할매수: ₩{lv.get('ma240', lv['entry']):,.0f}~₩{lv['entry']:,.0f}\n"
                        f"🎯 목표가: ₩{lv['target']:,.0f} (+{lv['upside']:.1f}%)\n"
                        f"🛑 손절가: ₩{lv['stop']:,.0f} ({lv['downside']:.1f}%)\n"
                        f"⚖️ 손익비: {lv['rr']:.1f}:1"
                    )
                else:
                    caption = f"<b>{r['name']}</b>"
                send_photo(img, caption)

    # ── 성과 추적 DB 저장 ──────────────────────────────────────
    try:
        from cache_db import save_alert_history
        # 차트 없는 종목도 포함해서 전체 저장
        for r in results:
            if r["symbol"] not in price_levels_map:
                price_levels_map[r["symbol"]] = calc_price_levels(r["symbol"])
        save_alert_history(results, price_levels_map)
        print(f"[성과추적] {len(results)}개 종목 저장 완료")
    except Exception as e:
        print(f"[성과추적] 저장 오류: {e}")


def send_test_alert():
    return send_telegram(
        "✅ <b>HotStock 알림 봇 연결 완료!</b>\n"
        "매일 장 마감 후 급등 예고 종목을 자동으로 알려드립니다. 🚀"
    )


def send_performance_update():
    """성과 업데이트 알림 - 상태 변경된 종목만 전송"""
    try:
        from cache_db import update_alert_status, get_alert_history, get_performance_summary
        import yfinance as yf

        # 상태 업데이트 실행
        update_alert_status()

        today = date.today().isoformat()
        history = get_alert_history(200)

        # 오늘 상태 변경된 종목 찾기
        newly_active   = [h for h in history if h["status"] == "active"   and h.get("exit_date") is None and h["alert_date"] == today]
        hit_target_today = [h for h in history if h["status"] == "hit_target" and h.get("exit_date") == today]
        hit_stop_today   = [h for h in history if h["status"] == "hit_stop"   and h.get("exit_date") == today]
        still_pending  = [h for h in history if h["status"] == "pending"]

        # 변경 사항 없으면 전송 안 함
        if not newly_active and not hit_target_today and not hit_stop_today:
            print("[성과추적] 오늘 상태 변경 없음 - 알림 생략")
            return

        lines = [f"📊 <b>성과 업데이트</b> ({today})\n{'━'*20}"]

        if hit_target_today:
            lines.append("\n✅ <b>목표가 달성!</b>")
            for h in hit_target_today:
                lines.append(f"• {h['name']} → ₩{h['exit_price']:,.0f} (<b>+{h['return_pct']:.1f}%</b>) 🎉")

        if hit_stop_today:
            lines.append("\n🛑 <b>손절가 이탈</b>")
            for h in hit_stop_today:
                lines.append(f"• {h['name']} → ₩{h['exit_price']:,.0f} ({h['return_pct']:.1f}%)")

        if newly_active:
            lines.append("\n🔵 <b>매수가 진입 확인</b>")
            for h in newly_active:
                lines.append(f"• {h['name']} → ₩{h['entry_price']:,.0f} 터치 (모니터링 시작)")

        if still_pending:
            from datetime import datetime as dt
            lines.append(f"\n⏳ <b>매수 대기 중</b> ({len(still_pending)}개)")
            for h in still_pending:
                try:
                    days = (dt.now() - dt.fromisoformat(h["alert_date"])).days
                    days_left = 5 - days
                    lines.append(f"• {h['name']} ₩{h['entry_price']:,.0f} 이하 진입 대기 (D+{days}, {days_left}일 후 만료)")
                except:
                    lines.append(f"• {h['name']} ₩{h['entry_price']:,.0f} 이하 진입 대기")

        send_telegram("\n".join(lines))
        print(f"[성과추적] 업데이트 알림 전송 완료")

    except Exception as e:
        print(f"[성과추적] 알림 오류: {e}")


def send_weekly_summary():
    """주간 성과 요약 - 매주 금요일 전송"""
    try:
        from cache_db import get_performance_summary
        from datetime import datetime

        # 금요일(4)만 전송
        if datetime.now().weekday() != 4:
            return

        perf = get_performance_summary()
        if perf["total"] == 0:
            return

        win_rate = perf["win_rate"]
        avg_ret  = perf["avg_return"]
        wr_emoji = "🟢" if win_rate >= 60 else "🟡" if win_rate >= 40 else "🔴"
        ret_emoji = "📈" if avg_ret >= 0 else "📉"

        msg = (
            f"📈 <b>주간 성과 요약</b>\n{'━'*20}\n\n"
            f"청산 종목: <b>{perf['total']}개</b>\n"
            f"✅ 목표달성: {perf['win']}개  |  🛑 손절: {perf['loss']}개\n\n"
            f"{wr_emoji} 승률: <b>{win_rate}%</b>\n"
            f"{ret_emoji} 평균 수익률: <b>{avg_ret:+.1f}%</b>\n"
        )
        if perf["win"] > 0:
            msg += f"평균 수익: <b style='color:green'>+{perf['avg_win']:.1f}%</b>\n"
        if perf["loss"] > 0:
            msg += f"평균 손실: <b>{perf['avg_loss']:.1f}%</b>\n"
        msg += f"\n🔵 진입 모니터링: {perf.get('active',0)}개\n"
        msg += f"⏳ 매수 대기: {perf.get('pending',0)}개\n"
        msg += "\n⚠️ 투자 참고용 정보입니다."

        send_telegram(msg)
        print("[성과추적] 주간 요약 전송 완료")

    except Exception as e:
        print(f"[성과추적] 주간 요약 오류: {e}")
