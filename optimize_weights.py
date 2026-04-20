"""
신호 가중치 자동 최적화
- 과거 스캔 통과 종목들의 실제 수익률 데이터로 학습
- 어떤 신호가 실제 수익과 연관 있는지 분석
- 최적화된 가중치를 backtest_ml.py의 SIGNAL_WEIGHTS에 반영
"""
import json
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# 최적화 대상 신호 목록 (backtest_ml.py와 동일)
SIGNAL_KEYS = [
    "bb_squeeze_expand", "stealth_accumulation", "vol_price_rising3",
    "vol_strong_cross", "vol_at_cross", "vol_surge_sustained",
    "both_buying", "smart_money_in", "pullback_bounce", "ichimoku_bull",
    "ma240_turning_up", "ma_align", "macd_cross", "obv_rising",
    "near_52w_high", "pullback_recovery", "mfi_oversold_recovery",
    "adx_strong", "stoch_cross", "recent_vol", "rsi_healthy",
    "above_vwap", "hammer", "bullish_engulf",
    # RSI 관련 신호
    "rsi_slope_up", "rsi_cross50", "rsi_divergence",
    "weekly_rsi_bull", "weekly_rsi_rising",
    "rsi2_oversold", "rsi2_connors_entry",
    "higher_low", "pullback_depth",
]


def load_alert_history() -> pd.DataFrame:
    """alert_history DB에서 청산된 종목 데이터 로드"""
    try:
        from cache_db import _get_conn
        conn = _get_conn()
        rows = conn.execute("""
            SELECT symbol, status, return_pct, entry_price, exit_price, alert_date
            FROM alert_history
            WHERE status IN ('hit_target', 'hit_stop')
              AND return_pct IS NOT NULL
            ORDER BY alert_date DESC
        """).fetchall()
        if not rows:
            print("[최적화] alert_history 데이터 없음")
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=["symbol","status","return_pct","entry_price","exit_price","alert_date"])
        print(f"[최적화] 청산 종목 {len(df)}개 로드 (승: {(df.status=='hit_target').sum()}, 패: {(df.status=='hit_stop').sum()})")
        return df
    except Exception as e:
        print(f"[최적화] DB 로드 오류: {e}")
        return pd.DataFrame()


def load_scan_signals() -> pd.DataFrame:
    """저장된 스캔 결과에서 신호 데이터 추출"""
    try:
        from cache_db import _get_conn
        conn = _get_conn()
        rows = conn.execute("""
            SELECT scan_date, results FROM scan_results
            ORDER BY scan_date DESC LIMIT 60
        """).fetchall()
        if not rows:
            return pd.DataFrame()

        records = []
        for scan_date, results_json in rows:
            try:
                results = json.loads(results_json)
                for r in results:
                    sig = r.get("signals", {})
                    record = {"symbol": r.get("symbol"), "scan_date": scan_date}
                    for k in SIGNAL_KEYS:
                        v = sig.get(k, False)
                        record[k] = 1 if v is True else 0
                    record["total_score"] = r.get("total_score", 0)
                    records.append(record)
            except Exception:
                continue

        df = pd.DataFrame(records)
        print(f"[최적화] 스캔 신호 {len(df)}개 로드")
        return df
    except Exception as e:
        print(f"[최적화] 스캔 신호 로드 오류: {e}")
        return pd.DataFrame()


def analyze_signal_performance(history_df: pd.DataFrame, signals_df: pd.DataFrame) -> pd.DataFrame:
    """신호별 실제 수익률 기여도 분석"""
    if history_df.empty or signals_df.empty:
        return pd.DataFrame()

    # 스캔 신호 + 실제 수익률 조인
    merged = pd.merge(
        signals_df,
        history_df[["symbol", "return_pct", "status"]],
        on="symbol", how="inner"
    )
    if merged.empty:
        print("[최적화] 조인 결과 없음 - 데이터 부족")
        return pd.DataFrame()

    print(f"[최적화] 분석 가능 종목: {len(merged)}개")

    results = []
    for sig in SIGNAL_KEYS:
        if sig not in merged.columns:
            continue
        with_sig    = merged[merged[sig] == 1]["return_pct"]
        without_sig = merged[merged[sig] == 0]["return_pct"]

        if len(with_sig) < 3:
            continue

        win_rate_with    = (with_sig > 0).mean() * 100
        win_rate_without = (without_sig > 0).mean() * 100 if len(without_sig) > 0 else 50
        avg_ret_with     = with_sig.mean()
        avg_ret_without  = without_sig.mean() if len(without_sig) > 0 else 0

        # 신호 유무에 따른 수익률 차이 (핵심 지표)
        ret_diff     = avg_ret_with - avg_ret_without
        winrate_diff = win_rate_with - win_rate_without

        results.append({
            "signal":          sig,
            "count":           len(with_sig),
            "avg_ret_with":    round(avg_ret_with, 2),
            "avg_ret_without": round(avg_ret_without, 2),
            "ret_diff":        round(ret_diff, 2),
            "win_rate_with":   round(win_rate_with, 1),
            "winrate_diff":    round(winrate_diff, 1),
        })

    df = pd.DataFrame(results).sort_values("ret_diff", ascending=False)
    return df


def optimize_weights(perf_df: pd.DataFrame) -> dict:
    """
    성과 분석 결과로 최적 가중치 계산
    - ret_diff > 0: 수익에 기여 → 가중치 증가
    - ret_diff < 0: 수익에 해로움 → 가중치 감소
    """
    from backtest_ml import SIGNAL_WEIGHTS

    new_weights = dict(SIGNAL_WEIGHTS)  # 기존 가중치 복사

    if perf_df.empty:
        return new_weights

    # ret_diff를 0.5~3.0 범위로 정규화해서 가중치로 변환
    max_diff = perf_df["ret_diff"].abs().max()
    if max_diff == 0:
        return new_weights

    for _, row in perf_df.iterrows():
        sig = row["signal"]
        ret_diff = row["ret_diff"]
        winrate_diff = row["winrate_diff"]

        # 수익률 차이 + 승률 차이를 종합한 점수
        combined_score = ret_diff * 0.7 + winrate_diff * 0.03

        # 0.5 ~ 3.0 범위로 정규화
        normalized = 1.0 + (combined_score / max_diff) * 1.5
        new_weight = max(0.3, min(3.5, normalized))

        if sig in new_weights:
            # 기존 가중치와 50:50 블렌딩 (급격한 변화 방지)
            new_weights[sig] = round(new_weights[sig] * 0.5 + new_weight * 0.5, 2)
        else:
            new_weights[sig] = round(new_weight, 2)

    return new_weights


def apply_weights_to_backtest_ml(new_weights: dict):
    """최적화된 가중치를 backtest_ml.py에 반영"""
    try:
        with open("backtest_ml.py", "r", encoding="utf-8") as f:
            content = f.read()

        # SIGNAL_WEIGHTS 딕셔너리 부분을 새 가중치로 교체
        lines = []
        for sig, w in sorted(new_weights.items(), key=lambda x: -x[1]):
            lines.append(f'    "{sig}": {w},')

        new_block = "SIGNAL_WEIGHTS = {\n" + "\n".join(lines) + "\n}\n"

        import re
        updated = re.sub(
            r"SIGNAL_WEIGHTS\s*=\s*\{[^}]+\}",
            new_block,
            content,
            flags=re.DOTALL
        )

        with open("backtest_ml.py", "w", encoding="utf-8") as f:
            f.write(updated)

        print("[최적화] backtest_ml.py 가중치 업데이트 완료")
        return True
    except Exception as e:
        print(f"[최적화] 파일 업데이트 오류: {e}")
        return False


def run_backtest_validation(new_weights: dict, sample_symbols: list = None) -> dict:
    """
    최적화된 가중치로 백테스트 실행해서 개선 여부 확인
    """
    try:
        import json as _json
        if sample_symbols is None:
            with open("combined_symbols.json", encoding="utf-8") as f:
                all_syms = list(_json.load(f).keys())
            # 거래대금 상위 30개만 샘플로 사용
            sample_symbols = all_syms[:30]

        from backtest_ml import backtest_signal, SIGNAL_WEIGHTS as OLD_WEIGHTS

        old_results = []
        new_results = []

        print(f"[검증] {len(sample_symbols)}개 종목 백테스트 중...")
        for sym in sample_symbols:
            r = backtest_signal(sym, lookback_days=120, hold_days=20, min_score=5)
            if r:
                old_results.append(r)

        if not old_results:
            return {}

        old_avg = np.mean([r["avg_ret"] for r in old_results])
        old_wr  = np.mean([r["win_rate"] for r in old_results])

        return {
            "old_avg_ret":  round(old_avg, 2),
            "old_win_rate": round(old_wr, 1),
            "sample_count": len(old_results),
        }
    except Exception as e:
        print(f"[검증] 오류: {e}")
        return {}


def run_optimization(apply: bool = False):
    """
    전체 최적화 파이프라인 실행
    apply=True: backtest_ml.py에 실제 반영
    apply=False: 분석 결과만 출력 (기본값 - 안전)
    """
    print("=" * 50)
    print("신호 가중치 최적화 시작")
    print("=" * 50)

    # 1. 데이터 로드
    history_df = load_alert_history()
    signals_df = load_scan_signals()

    if history_df.empty:
        print("\n⚠️  청산 데이터가 부족합니다.")
        print("   alert_history에 hit_target/hit_stop 종목이 쌓여야 최적화 가능합니다.")
        print("   현재는 기존 가중치를 유지합니다.")
        return None

    # 2. 신호별 성과 분석
    print("\n[분석] 신호별 수익률 기여도 계산 중...")
    perf_df = analyze_signal_performance(history_df, signals_df)

    if perf_df.empty:
        print("⚠️  분석 데이터 부족 - 스캔 결과와 성과 데이터 매칭 실패")
        return None

    # 3. 결과 출력
    print("\n📊 신호별 수익률 기여도 (상위 10개)")
    print(f"{'신호':<30} {'보유시 평균수익':>12} {'차이':>8} {'승률':>8} {'건수':>6}")
    print("-" * 70)
    for _, row in perf_df.head(10).iterrows():
        marker = "✅" if row["ret_diff"] > 0 else "❌"
        print(f"{marker} {row['signal']:<28} {row['avg_ret_with']:>+10.2f}%  "
              f"{row['ret_diff']:>+6.2f}%  {row['win_rate_with']:>6.1f}%  {row['count']:>5}건")

    print("\n📊 수익에 해로운 신호 (하위 5개)")
    for _, row in perf_df.tail(5).iterrows():
        print(f"❌ {row['signal']:<28} {row['avg_ret_with']:>+10.2f}%  "
              f"{row['ret_diff']:>+6.2f}%  {row['win_rate_with']:>6.1f}%  {row['count']:>5}건")

    # 4. 최적 가중치 계산
    new_weights = optimize_weights(perf_df)

    print("\n📊 가중치 변화 (주요 신호)")
    from backtest_ml import SIGNAL_WEIGHTS as OLD
    changed = []
    for sig, new_w in new_weights.items():
        old_w = OLD.get(sig, 1.0)
        diff = new_w - old_w
        if abs(diff) > 0.1:
            changed.append((sig, old_w, new_w, diff))
    changed.sort(key=lambda x: -abs(x[3]))
    for sig, old_w, new_w, diff in changed[:10]:
        arrow = "↑" if diff > 0 else "↓"
        print(f"  {arrow} {sig:<30} {old_w:.1f} → {new_w:.1f}  ({diff:+.2f})")

    if apply:
        print("\n✅ backtest_ml.py에 새 가중치 적용 중...")
        apply_weights_to_backtest_ml(new_weights)
    else:
        print("\n💡 실제 적용하려면: run_optimization(apply=True)")

    return new_weights


if __name__ == "__main__":
    import sys
    apply_flag = "--apply" in sys.argv
    result = run_optimization(apply=apply_flag)
    if result:
        print(f"\n완료. 최적화된 신호 수: {len(result)}개")
