"""
한국 주식 급등 예측 프로그램 v3.0
핵심 전략: 240일선 아래 6개월+ 조정 → 최근 돌파 → 현재 근처 → 급등 신호 복합
"""
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

try:
    import ta
    _TA_AVAILABLE = True
except ImportError:
    _TA_AVAILABLE = False

try:
    from backtest_ml import ml_score_adjustment
except:
    def ml_score_adjustment(signals, base_score): return float(base_score)


def _get_ohlcv_kis(symbol: str, years: int = 5):
    """
    KIS API로 일봉 데이터 조회 (yfinance 대체)
    KIS_APP_KEY 없으면 None 반환 → yfinance 폴백
    """
    try:
        if not os.environ.get("KIS_APP_KEY"):
            return None
        from auto_trader import KISClient
        from datetime import date, timedelta
        client = KISClient()
        end   = date.today().strftime("%Y%m%d")
        start = (date.today() - timedelta(days=years * 365)).strftime("%Y%m%d")
        # KIS API는 한 번에 최대 100일치 → 여러 번 호출해서 합치기
        all_dfs = []
        cur_end = date.today()
        for _ in range(years * 3):  # 최대 years*3번 호출
            cur_start = cur_end - timedelta(days=99)
            df_chunk = client.get_daily_ohlcv(
                symbol,
                cur_start.strftime("%Y%m%d"),
                cur_end.strftime("%Y%m%d")
            )
            if df_chunk is not None and len(df_chunk) > 0:
                all_dfs.append(df_chunk)
            cur_end = cur_start - timedelta(days=1)
            if cur_end < date.today() - timedelta(days=years * 365):
                break
        if not all_dfs:
            return None
        import pandas as pd
        df = pd.concat(all_dfs).sort_index()
        df = df[~df.index.duplicated(keep='last')]
        return df
    except Exception as e:
        print(f"[KIS OHLCV] {symbol} 오류: {e}")
        return None

# ── 종목 리스트: combined_symbols.json에서 로드 (코스피500 + 코스닥 우량주) ──
import json as _json, os as _os
_symbols_path = _os.path.join(_os.path.dirname(__file__), "combined_symbols.json")
try:
    with open(_symbols_path, encoding="utf-8") as _f:
        _symbols_data = _json.load(_f)
    ALL_SYMBOLS  = list(_symbols_data.keys())
    STOCK_NAMES  = dict(_symbols_data)
    print(f"[종목 로드] {len(ALL_SYMBOLS)}개 (코스피+코스닥)")
except Exception as _e:
    print(f"[종목 로드 실패] {_e} → 기본 리스트 사용")
    ALL_SYMBOLS = []
    STOCK_NAMES = {}
class KoreanStockSurgeDetector:
    def __init__(self, max_gap_pct=10.0, min_below_days=90, max_cross_days=60):  # max_cross 120→60
        self.all_symbols    = ALL_SYMBOLS
        self.max_gap_pct    = max_gap_pct
        self.min_below_days = min_below_days
        self.max_cross_days = max_cross_days

    # ── 보조 지표 ────────────────────────────────────────────────

    def _rsi(self, close, period=20):
        """RSI - ta 라이브러리 사용 (폴백: Wilder's Smoothing)"""
        if _TA_AVAILABLE:
            try:
                return ta.momentum.RSIIndicator(close=close, window=period).rsi()
            except:
                pass
        d = close.diff()
        gain = d.where(d > 0, 0.0)
        loss = -d.where(d < 0, 0.0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, float('nan'))
        return 100 - (100 / (1 + rs))

    def _obv(self, data):
        """OBV - ta 라이브러리 사용 (폴백: 수동 계산)"""
        if _TA_AVAILABLE:
            try:
                return ta.volume.OnBalanceVolumeIndicator(
                    close=data["Close"], volume=data["Volume"]
                ).on_balance_volume()
            except:
                pass
        obv = [0]
        for i in range(1, len(data)):
            if data["Close"].iloc[i] > data["Close"].iloc[i-1]:
                obv.append(obv[-1] + data["Volume"].iloc[i])
            elif data["Close"].iloc[i] < data["Close"].iloc[i-1]:
                obv.append(obv[-1] - data["Volume"].iloc[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=data.index)

    def _news_sentiment(self, symbol):
        """뉴스 감성 분석 - 네이버 + 한국경제 멀티소스"""
        code = symbol.replace(".KS","").replace(".KQ","")
        pos = ["급등","상승","돌파","신고가","수주","흑자","성장","호실적","매수","상향","계약",
               "수익","개선","확대","증가","강세","반등","회복","기대","호재","수혜","선정",
               "수상","특허","승인","허가","출시","신제품","협약","MOU","투자유치"]
        neg = ["급락","하락","적자","손실","매도","하향","감소","부진","우려","위기","악화",
               "하락세","조정","약세","실망","경고","리스크","소송","제재","벌금","횡령","배임"]
        titles = []
        try:
            # 네이버 금융 뉴스
            url = f"https://finance.naver.com/item/news_news.naver?code={code}&page=1"
            res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=3)
            soup = BeautifulSoup(res.text, "html.parser")
            titles += [a.get_text().strip() for a in soup.select(".title") if a.get_text().strip()]
        except:
            pass
        try:
            # 한국경제 종목 뉴스
            name = STOCK_NAMES.get(symbol, "").replace(" ", "+")
            if name:
                url2 = f"https://search.hankyung.com/search/news?query={name}&sort=date"
                res2 = requests.get(url2, headers={"User-Agent":"Mozilla/5.0"}, timeout=3)
                soup2 = BeautifulSoup(res2.text, "html.parser")
                titles += [a.get_text().strip() for a in soup2.select(".article-title, .tit") if a.get_text().strip()][:10]
        except:
            pass
        if not titles:
            return 0, 0, 0
        p = sum(1 for t in titles for k in pos if k in t)
        n = sum(1 for t in titles for k in neg if k in t)
        total = p + n
        return round((p - n) / total, 2) if total > 0 else 0, p, n

    def _dart_disclosure(self, symbol):
        """호재 공시 수집 - KIND(한국거래소) + 네이버 공시 멀티소스"""
        code = symbol.replace(".KS","").replace(".KQ","")
        good_keys = ["자기주식취득","수주","공급계약","투자","합병","분할","신규사업",
                     "특허","허가","승인","MOU","협약","유상증자철회","자사주","배당확대"]
        bad_keys  = ["횡령","배임","소송","제재","상장폐지","감사의견","영업정지"]
        hits = []
        try:
            # KIND 공시 직접 크롤링
            url = f"https://kind.krx.co.kr/disclosure/searchtotalinfo.do?method=searchTotalInfoSub&forward=searchtotalinfo_sub&searchCodeType=&searchCorpName={code}&searchCorpCode={code}&marketType=&reportType=&startDate=&endDate=&currentPage=1&maxResults=10"
            res = requests.get(url, headers={"User-Agent":"Mozilla/5.0", "Referer":"https://kind.krx.co.kr/"}, timeout=4)
            soup = BeautifulSoup(res.text, "html.parser")
            titles_kind = [a.get_text().strip() for a in soup.select("td.title a, .tit a") if a.get_text().strip()]
            hits += [k for t in titles_kind for k in good_keys if k in t]
            # 악재 공시 있으면 패널티
            bad_hits = [k for t in titles_kind for k in bad_keys if k in t]
            if bad_hits:
                return False, []
        except:
            pass
        try:
            # 네이버 공시 폴백
            url2 = f"https://finance.naver.com/item/news_dis.naver?code={code}"
            res2 = requests.get(url2, headers={"User-Agent":"Mozilla/5.0"}, timeout=3)
            soup2 = BeautifulSoup(res2.text, "html.parser")
            titles_naver = [a.get_text().strip() for a in soup2.select(".title") if a.get_text().strip()]
            hits += [k for t in titles_naver for k in good_keys if k in t]
            bad_hits2 = [k for t in titles_naver for k in bad_keys if k in t]
            if bad_hits2:
                return False, []
        except:
            pass
        unique_hits = list(dict.fromkeys(hits))  # 중복 제거
        return len(unique_hits) > 0, unique_hits[:3]

    def _institutional_flow(self, symbol):
        """기관/외국인 순매수 크롤링 (네이버 금융 메인 페이지)
        Returns: (inst_net: int, foreign_net: int)  단위: 주, 최근 5일 합산
        """
        code = symbol.replace(".KS","").replace(".KQ","")
        try:
            url = f"https://finance.naver.com/item/main.naver?code={code}"
            res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=3)
            soup = BeautifulSoup(res.text, "html.parser")
            inst_net = 0
            foreign_net = 0
            for table in soup.select("table"):
                # 헤더(th)에 외국인/기관 있는 테이블 찾기
                ths = [th.get_text(strip=True) for th in table.select("th")]
                if "외국인" in ths and "기관" in ths:
                    fi = ths.index("외국인")
                    ii = ths.index("기관")
                    for row in table.select("tr"):
                        cols = row.select("td")
                        if len(cols) > max(fi, ii):
                            try:
                                fv = cols[fi].get_text(strip=True).replace(",","").replace("+","")
                                iv = cols[ii].get_text(strip=True).replace(",","").replace("+","")
                                if fv and fv not in ("-",""):
                                    foreign_net += int(fv)
                                if iv and iv not in ("-",""):
                                    inst_net += int(iv)
                            except:
                                pass
                    break
                # th 없이 td만 있는 경우: 날짜/종가/전일비/외국인/기관 순서
                tds_header = table.select("tr:first-child td")
                header_texts = [td.get_text(strip=True) for td in tds_header]
                if "외국인" in header_texts and "기관" in header_texts:
                    fi = header_texts.index("외국인")
                    ii = header_texts.index("기관")
                    for row in table.select("tr")[1:6]:
                        cols = row.select("td")
                        if len(cols) > max(fi, ii):
                            try:
                                fv = cols[fi].get_text(strip=True).replace(",","").replace("+","")
                                iv = cols[ii].get_text(strip=True).replace(",","").replace("+","")
                                if fv and fv not in ("-",""):
                                    foreign_net += int(fv)
                                if iv and iv not in ("-",""):
                                    inst_net += int(iv)
                            except:
                                pass
                    break
                # 고정 인덱스: 날짜(0)/종가(1)/전일비(2)/외국인(3)/기관(4) - 4컬럼이면 종가없이 전일비/외국인/기관
                rows_data = [r for r in table.select("tr") if len(r.select("td")) == 4]
                if rows_data:
                    # 헤더 확인
                    first_vals = [td.get_text(strip=True) for td in rows_data[0].select("td")]
                    # 숫자+부호 패턴이면 데이터 행
                    import re
                    if any(re.search(r'[+\-]\d', v) for v in first_vals):
                        for row in rows_data[:5]:
                            cols = row.select("td")
                            try:
                                fv = cols[2].get_text(strip=True).replace(",","").replace("+","")
                                iv = cols[3].get_text(strip=True).replace(",","").replace("+","")
                                if fv and fv not in ("-",""):
                                    foreign_net += int(fv)
                                if iv and iv not in ("-",""):
                                    inst_net += int(iv)
                            except:
                                pass
                        if foreign_net != 0 or inst_net != 0:
                            break
            return inst_net, foreign_net
        except:
            return 0, 0

    # ── 핵심 분석 ────────────────────────────────────────────────

    def _market_condition(self):
        """KOSPI 시장 상태 확인 - 상승장/하락장"""
        try:
            kospi = yf.Ticker("^KS11").history(period="1y")
            kospi = kospi.dropna(subset=["Close"])
            close = kospi["Close"]
            ma200 = float(close.rolling(200).mean().iloc[-1])
            ma60  = float(close.rolling(60).mean().iloc[-1])
            cur   = float(close.iloc[-1])
            # 200일선 위 = 상승장, 아래 = 하락장
            bull = cur > ma200
            # 60일선 기울기 (모멘텀)
            slope = (float(close.rolling(60).mean().iloc[-1]) - float(close.rolling(60).mean().iloc[-20])) / float(close.rolling(60).mean().iloc[-20]) * 100
            return bull, round(slope, 2)
        except:
            return True, 0

    def _rsi_cycle_pullback(self, close, ma_long, rsi_period=20) -> dict:
        """
        RSI 사이클 눌림목 패턴 탐지
        조건:
          1) RSI(20)이 30 이하(과매도)에서 탈출
          2) 과매도 탈출 ~ 과매수 도달 사이에 1000일선 상향 돌파 존재
          3) RSI가 70 이상(과매수)까지 도달
          4) RSI가 70에서 이탈 (조정 시작)
          5) 현재 RSI 55 이하 + 현재 주가 1000선 근처
        """
        try:
            rsi = self._rsi(close, rsi_period).dropna()
            if len(rsi) < 60:
                return {"matched": False}

            rsi_vals = rsi.values
            n = len(rsi_vals)
            close_arr = close.values
            ma_arr = ma_long.values

            # 최근 250일 내에서 패턴 탐색 (긴 사이클 포함)
            search_start = max(0, n - 250)

            # Step 1: 과매도 탈출 시점 찾기 - 가장 강한 바닥(최저 RSI) 사이클 선택
            oversold_candidates = []
            for i in range(search_start, n - 20):
                if rsi_vals[i-1] <= 30 and rsi_vals[i] > 30:
                    look_back = max(0, i - 20)
                    min_rsi = float(rsi_vals[look_back:i].min()) if i > look_back else float(rsi_vals[i-1])
                    oversold_candidates.append((i, min_rsi))

            if not oversold_candidates:
                return {"matched": False}

            oversold_exit_idx = min(oversold_candidates, key=lambda x: (x[1], -x[0]))[0]

            # Step 2: 과매도 탈출 이후 RSI 70 이상 도달 시점
            overbought_idx = None
            for i in range(oversold_exit_idx, n - 5):
                if rsi_vals[i] >= 70:
                    overbought_idx = i
                    break
            if overbought_idx is None:
                return {"matched": False}

            # Step 3: 과매도 탈출 ~ 과매수 도달 사이에 1000선 상향 돌파 존재 확인
            cross_in_cycle = False
            cross_in_cycle_idx = None
            for i in range(oversold_exit_idx, overbought_idx + 1):
                if i == 0 or pd.isna(ma_arr[i]) or pd.isna(ma_arr[i-1]):
                    continue
                if close_arr[i] > ma_arr[i] and close_arr[i-1] <= ma_arr[i-1]:
                    cross_in_cycle = True
                    cross_in_cycle_idx = i
                    break
            if not cross_in_cycle:
                return {"matched": False}

            # Step 4: 70 도달 이후 70 이탈 시점
            overbought_exit_idx = None
            for i in range(overbought_idx, n - 1):
                if rsi_vals[i-1] >= 70 and rsi_vals[i] < 70:
                    overbought_exit_idx = i
                    break
            if overbought_exit_idx is None:
                return {"matched": False}

            # Step 5: 현재 RSI 55 이하 (눌림목 충분히 진행)
            cur_rsi = float(rsi_vals[-1])
            if cur_rsi > 55:
                return {"matched": False}

            # 70 이탈 후 너무 오래된 사이클 제외 (120일로 완화)
            days_since_peak = n - 1 - overbought_exit_idx
            if days_since_peak > 120:
                return {"matched": False}

            rsi_low  = float(rsi_vals[oversold_exit_idx - 1])
            rsi_peak = float(rsi_vals[overbought_idx:overbought_exit_idx+1].max())

            return {
                "matched":             True,
                "oversold_exit_idx":   oversold_exit_idx,
                "overbought_idx":      overbought_idx,
                "overbought_exit_idx": overbought_exit_idx,
                "cross_in_cycle_idx":  cross_in_cycle_idx,
                "rsi_low":             round(rsi_low, 1),
                "rsi_peak":            round(rsi_peak, 1),
                "cur_rsi":             round(cur_rsi, 1),
                "days_since_peak":     days_since_peak,
            }
        except Exception:
            return {"matched": False}

    def _sector_momentum(self, symbol):
        """섹터 모멘텀 - 같은 섹터 ETF 기준"""
        sector_etf = {
            # 반도체
            "005930.KS":"091160.KS","000660.KS":"091160.KS","011070.KS":"091160.KS",
            # 자동차
            "005380.KS":"091180.KS","000270.KS":"091180.KS",
            # 바이오
            "207940.KS":"244580.KS","068270.KS":"244580.KS","145020.KQ":"244580.KS",
            # 2차전지
            "006400.KS":"305720.KS","051910.KS":"305720.KS","373220.KS":"305720.KS",
            # 방산
            "047810.KS":"459580.KS","064350.KS":"459580.KS",
        }
        etf = sector_etf.get(symbol)
        if not etf:
            return 0
        try:
            df = yf.Ticker(etf).history(period="3mo")
            df = df.dropna(subset=["Close"])
            close = df["Close"]
            ret_1m = (float(close.iloc[-1]) - float(close.iloc[-20])) / float(close.iloc[-20]) * 100
            return round(ret_1m, 2)
        except:
            return 0

    def analyze_stock(self, symbol, as_of_date=None):
        """
        as_of_date: datetime.date 또는 None (None이면 오늘 기준)
        과거 날짜 지정 시 해당 날짜까지의 데이터만 사용 (백테스트용)
        """
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="2y", auto_adjust=False)

            # ── as_of_date 기준으로 데이터 자르기 ──
            if as_of_date is not None:
                import pandas as _pd
                cutoff = _pd.Timestamp(as_of_date).tz_localize(data.index.tz) if data.index.tz else _pd.Timestamp(as_of_date)
                data = data[data.index <= cutoff]
                if len(data) == 0:
                    return None

            # ── 당일 종가 보완: yfinance NaN이면 네이버에서 가져오기 ──
            # _today_price_cache는 analyze_all_stocks에서 사전 조회한 값
            if len(data) > 0 and pd.isna(data["Close"].iloc[-1]):
                today_price = getattr(self, '_today_price_cache', {}).get(symbol)
                if today_price:
                    data.loc[data.index[-1], "Open"]  = today_price
                    data.loc[data.index[-1], "High"]  = today_price
                    data.loc[data.index[-1], "Low"]   = today_price
                    data.loc[data.index[-1], "Close"] = today_price

            data = data.dropna(subset=["Open","High","Low","Close"])
            if len(data) < 260:
                return None

            close = data["Close"]
            high  = data["High"]
            low   = data["Low"]
            vol   = data["Volume"]
            n     = len(close)

            # ── 거래대금 필터: 일평균 20억 미만 제외 ────────────────
            avg_price  = float(close.tail(20).mean())
            avg_vol    = float(vol.tail(20).mean())
            avg_amount = avg_price * avg_vol  # 일평균 거래대금 (원)
            if avg_amount < 2_000_000_000:    # 20억 미만 제외
                return None

            # ── 하락장 필터: analyze_all_stocks에서 사전 체크 완료 ──
            # (KOSPI 200일선 체크는 analyze_all_stocks에서 1회만 수행)

            ma240 = close.rolling(240).mean()
            ma1000 = close.rolling(1000).mean()
            ma120 = close.rolling(120).mean()
            ma60  = close.rolling(60).mean()
            ma20  = close.rolling(20).mean()
            ma5   = close.rolling(5).mean()

            if pd.isna(ma240.iloc[-1]):
                return None

            current  = float(close.iloc[-1])
            ma240_v  = float(ma240.iloc[-1])
            ma1000_v = float(ma1000.iloc[-1]) if not pd.isna(ma1000.iloc[-1]) else None

            # ── 핵심 조건: RSI(20) 사이클 + 240선 돌파 + 현재 240선 근처 ──
            # 1) RSI 30 이하 탈출
            # 2) 이후 240선 상향 돌파
            # 3) 이후 RSI 70 이상 도달
            # 4) 이후 RSI 70 이탈 (조정)
            # 5) 현재 주가 240선 위 0~max_gap_pct%
            rsi = self._rsi(close, 20)
            rsi_vals = rsi.fillna(50).values
            close_arr = close.values
            ma240_arr = ma240.values

            # 현재 240선 근처 체크 (빠른 사전 필터)
            gap_pct = (current - ma240_v) / ma240_v * 100
            if not (0 <= gap_pct <= self.max_gap_pct):
                return None

            # 최근 400일 내에서 패턴 탐색 (긴 사이클 종목 포함)
            search_start = max(1, n - 400)

            # Step1: RSI 30 이하 탈출 시점 - 여러 사이클 중 가장 강한 것 선택
            # (가장 낮은 RSI 바닥을 가진 사이클 우선)
            oversold_candidates = []
            for i in range(search_start, n - 30):
                if rsi_vals[i-1] <= 30 and rsi_vals[i] > 30:
                    # 탈출 직전 최저 RSI 기록
                    look_back = max(0, i - 20)
                    min_rsi_before = float(rsi_vals[look_back:i].min()) if i > look_back else float(rsi_vals[i-1])
                    oversold_candidates.append((i, min_rsi_before))

            if not oversold_candidates:
                return None

            # 가장 낮은 바닥(과매도 강도 높은) 사이클 선택, 동점이면 최근 것
            oversold_exit = min(oversold_candidates, key=lambda x: (x[1], -x[0]))[0]

            # Step2: 탈출 이후 240선 상향 돌파 - 거래량 동반한 가장 강한 돌파 선택
            # (첫 번째 돌파가 아니라 거래량 배수가 가장 높은 돌파)
            vol_arr = vol.values
            vol_ma20_arr = vol.rolling(20).mean().values
            cross_candidates = []
            for i in range(oversold_exit, n - 10):
                if pd.isna(ma240_arr[i]) or pd.isna(ma240_arr[i-1]):
                    continue
                if close_arr[i] > ma240_arr[i] and close_arr[i-1] <= ma240_arr[i-1]:
                    # 돌파 시 거래량 배수 계산
                    vr = float(vol_arr[i] / vol_ma20_arr[i]) if vol_ma20_arr[i] > 0 and not pd.isna(vol_ma20_arr[i]) else 1.0
                    cross_candidates.append((i, vr))

            if not cross_candidates:
                return None

            # 거래량 배수 가장 높은 돌파 선택 (동점이면 최근 것)
            cross_idx = max(cross_candidates, key=lambda x: (x[1], x[0]))[0]

            # Step3: 240선 돌파 이후 RSI 70 이상 도달
            overbought_idx = None
            for i in range(cross_idx, n - 5):
                if rsi_vals[i] >= 70:
                    overbought_idx = i
                    break
            if overbought_idx is None:
                return None

            # Step4: RSI 70 이탈 (조정 시작)
            overbought_exit = None
            for i in range(overbought_idx, n - 1):
                if rsi_vals[i-1] >= 70 and rsi_vals[i] < 70:
                    overbought_exit = i
                    break
            if overbought_exit is None:
                return None

            # Step5: 현재 주가 240선 위 0~max_gap_pct% (이미 위에서 체크)
            cur_rsi = float(rsi_vals[-1])

            # 70 이탈 후 너무 오래된 사이클 제외 (기본 180일)
            ob_max_days = getattr(self, '_ob_days', 180)
            days_since_ob_exit = n - 1 - overbought_exit
            if days_since_ob_exit > ob_max_days:
                return None

            # 눌림목 최소 기간 하한: 70 이탈 후 최소 5일 이상 (너무 빠른 재진입 제외)
            if days_since_ob_exit < 5:
                return None

            days_since_cross = n - 1 - cross_idx
            # 돌파 직전 조정 기간 계산 (가산점용)
            below_days = 0
            for i in range(cross_idx - 1, -1, -1):
                if not pd.isna(ma240.iloc[i]) and close.iloc[i] < ma240.iloc[i]:
                    below_days += 1
                else:
                    break

            # 장기선 아래 최소 진행 기간 필터 (앱에서 설정한 값)
            rc_below_min = getattr(self, '_rc_below', 0)
            if rc_below_min > 0 and below_days < rc_below_min:
                return None
            cross_gap  = (float(close.iloc[cross_idx]) - float(ma240.iloc[cross_idx])) / float(ma240.iloc[cross_idx]) * 100
            gc_days    = None
            signals_pre = {
                "rsi_cycle_pullback": True,
                "rsi_cycle_low":      round(float(rsi_vals[oversold_exit-1]), 1),
                "rsi_cycle_peak":     round(float(rsi_vals[overbought_idx:overbought_exit+1].max()), 1),
                "rsi_cycle_cur":      round(cur_rsi, 1),
                "rsi_cycle_days_since": days_since_ob_exit,
            }
            # ── 여기까지 통과 = 핵심 조건 충족 ─────────────────────
            score   = 0
            signals = {}
            signals.update(signals_pre)

            # [+3] 돌파 시 거래량 급증 (기준 강화: 3배 이상 = 강한 신호)
            vol_ma20 = vol.rolling(20).mean()
            cross_vr = float(vol.iloc[cross_idx] / vol_ma20.iloc[cross_idx]) if vol_ma20.iloc[cross_idx] > 0 else 0
            recent_vr = float(vol.iloc[-5:].mean() / vol_ma20.iloc[-1]) if vol_ma20.iloc[-1] > 0 else 0
            signals["vol_at_cross"]     = cross_vr >= 2.0
            signals["vol_strong_cross"] = cross_vr >= 3.0   # ▶ 추가: 강한 돌파 (3배 이상)
            signals["recent_vol"]       = recent_vr >= 1.5
            signals["cross_vol_ratio"]  = round(cross_vr, 2)
            signals["recent_vol_ratio"] = round(recent_vr, 2)
            if signals["vol_strong_cross"]: score += 4   # 3배 이상 = 4점
            elif signals["vol_at_cross"]:   score += 3   # 2배 이상 = 3점
            if signals["recent_vol"]:       score += 2

            # ▶ 추가: 돌파 전후 5일 평균 거래량 증가 확인
            try:
                vol_before5 = float(vol.iloc[cross_idx-5:cross_idx].mean())
                vol_after5  = float(vol.iloc[cross_idx:cross_idx+5].mean())
                signals["vol_surge_sustained"] = vol_after5 > vol_before5 * 1.5
                if signals["vol_surge_sustained"]: score += 2
            except:
                signals["vol_surge_sustained"] = False

            # [+2] OBV 지속 상승
            obv = self._obv(data)
            obv_after = obv.iloc[cross_idx:]
            signals["obv_rising"] = len(obv_after) > 1 and float(obv_after.iloc[-1]) > float(obv_after.iloc[0])
            if signals["obv_rising"]: score += 2

            # [+3] 이평선 정배열 MA5 > MA20 > MA60
            signals["ma_align"] = bool(ma5.iloc[-1] > ma20.iloc[-1] > ma60.iloc[-1])
            if signals["ma_align"]: score += 3

            # [+2] 눌림목 후 재상승
            pa = close.iloc[cross_idx:]
            signals["pullback_recovery"] = (
                len(pa) >= 3 and
                float(pa.min()) < float(pa.iloc[0]) and
                current > float(close.iloc[cross_idx])
            )
            if signals["pullback_recovery"]: score += 2

            # [+2] RSI(20) 건강 구간 40~65
            rsi = self._rsi(close, 20)
            cur_rsi = float(rsi.iloc[-1])
            signals["rsi"]         = round(cur_rsi, 1)
            signals["rsi_healthy"] = 40 <= cur_rsi <= 65
            if signals["rsi_healthy"]: score += 2

            # [+3] RSI(2) 단기 과매도 확인 (Larry Connors 방식)
            # 눌림목 구간에서 RSI(2) 10 이하면 단기 바닥 신호 - 진입 타이밍 정확도 향상
            try:
                rsi2 = self._rsi(close, 2).dropna()
                cur_rsi2 = float(rsi2.iloc[-1])
                signals["rsi2"]            = round(cur_rsi2, 1)
                signals["rsi2_oversold"]   = cur_rsi2 <= 10   # 강한 신호
                signals["rsi2_near_low"]   = cur_rsi2 <= 25   # 보통 신호
                # 3일 연속 하락 후 반등 (Connors 진입 조건)
                rsi2_vals = rsi2.values
                rsi2_3day_drop = (len(rsi2_vals) >= 4 and
                                  rsi2_vals[-4] > rsi2_vals[-3] > rsi2_vals[-2])
                rsi2_bounce    = len(rsi2_vals) >= 2 and rsi2_vals[-1] > rsi2_vals[-2]
                signals["rsi2_connors_entry"] = rsi2_3day_drop and rsi2_bounce and cur_rsi2 <= 25
                if signals["rsi2_oversold"]:       score += 3
                elif signals["rsi2_near_low"]:     score += 1
                if signals["rsi2_connors_entry"]:  score += 3
            except:
                signals["rsi2"]               = 50
                signals["rsi2_oversold"]      = False
                signals["rsi2_near_low"]      = False
                signals["rsi2_connors_entry"] = False

            # [+3] 상대강도(RS) - KOSPI 대비 종목 수익률
            # 시장보다 강한 종목이 눌림목에서 더 잘 반등
            try:
                kospi_data = yf.Ticker("^KS11").history(period="3mo").dropna(subset=["Close"])
                if len(kospi_data) >= 20 and len(close) >= 20:
                    stock_ret_1m  = (float(close.iloc[-1])  - float(close.iloc[-20]))  / float(close.iloc[-20])  * 100
                    kospi_ret_1m  = (float(kospi_data["Close"].iloc[-1]) - float(kospi_data["Close"].iloc[-20])) / float(kospi_data["Close"].iloc[-20]) * 100
                    rs_score = stock_ret_1m - kospi_ret_1m  # 양수 = 시장 대비 강함
                    stock_ret_3m  = (float(close.iloc[-1])  - float(close.iloc[-60]))  / float(close.iloc[-60])  * 100 if len(close) >= 60 else 0
                    kospi_ret_3m  = (float(kospi_data["Close"].iloc[-1]) - float(kospi_data["Close"].iloc[0]))   / float(kospi_data["Close"].iloc[0])   * 100
                    rs_score_3m = stock_ret_3m - kospi_ret_3m
                    signals["rs_score_1m"]   = round(rs_score, 1)
                    signals["rs_score_3m"]   = round(rs_score_3m, 1)
                    signals["rs_outperform"] = rs_score > 0       # 1개월 시장 대비 강함
                    signals["rs_strong"]     = rs_score > 5 and rs_score_3m > 0  # 강한 상대강도
                    if signals["rs_strong"]:     score += 3
                    elif signals["rs_outperform"]: score += 1
                else:
                    signals["rs_score_1m"]   = 0
                    signals["rs_score_3m"]   = 0
                    signals["rs_outperform"] = False
                    signals["rs_strong"]     = False
            except:
                signals["rs_score_1m"]   = 0
                signals["rs_score_3m"]   = 0
                signals["rs_outperform"] = False
                signals["rs_strong"]     = False

            # ── RSI 고급 신호 ────────────────────────────────────

            # [+3] RSI 상승 기울기 - 바닥 찍고 올라오는 중인지 확인
            try:
                rsi_clean = rsi.dropna()
                rsi_slope3 = float(rsi_clean.iloc[-1]) - float(rsi_clean.iloc[-4])   # 3일 기울기
                rsi_slope5 = float(rsi_clean.iloc[-1]) - float(rsi_clean.iloc[-6])   # 5일 기울기
                signals["rsi_slope_up"] = rsi_slope3 > 0 and rsi_slope5 > 0
                signals["rsi_slope_val"] = round(rsi_slope3, 1)
                if signals["rsi_slope_up"]: score += 3
            except:
                signals["rsi_slope_up"]  = False
                signals["rsi_slope_val"] = 0

            # [+3] RSI 50선 재돌파 - 눌림목 후 50 상향 돌파 (최근 5일 이내)
            try:
                rsi_arr = rsi.dropna().values
                rsi_cross50 = False
                for i in range(max(1, len(rsi_arr) - 5), len(rsi_arr)):
                    if rsi_arr[i-1] < 50 and rsi_arr[i] >= 50:
                        rsi_cross50 = True
                        break
                signals["rsi_cross50"] = rsi_cross50
                if rsi_cross50: score += 3
            except:
                signals["rsi_cross50"] = False

            # [+4] RSI 강세 다이버전스 - 주가 신저가 but RSI 전저점보다 높음
            try:
                rsi_vals_d = rsi.dropna().values
                close_vals_d = close.reindex(rsi.dropna().index).values
                div_window = min(60, len(rsi_vals_d) - 5)
                rsi_div = False
                if div_window > 10:
                    # 최근 저점 (최근 10일 내)
                    recent_low_idx  = int(np.argmin(close_vals_d[-10:]))  + len(close_vals_d) - 10
                    recent_rsi_low  = float(rsi_vals_d[recent_low_idx])
                    recent_price_low = float(close_vals_d[recent_low_idx])
                    # 이전 저점 (그 이전 div_window 내)
                    prev_window = close_vals_d[-(div_window):-10]
                    prev_rsi_window = rsi_vals_d[-(div_window):-10]
                    if len(prev_window) > 0:
                        prev_low_idx  = int(np.argmin(prev_window))
                        prev_price_low = float(prev_window[prev_low_idx])
                        prev_rsi_low   = float(prev_rsi_window[prev_low_idx])
                        # 주가는 더 낮은데 RSI는 더 높으면 강세 다이버전스
                        rsi_div = (recent_price_low < prev_price_low * 0.99 and
                                   recent_rsi_low   > prev_rsi_low   + 2.0)
                signals["rsi_divergence"] = rsi_div
                if rsi_div: score += 4
            except:
                signals["rsi_divergence"] = False

            # [+3] 주봉 RSI 50 이상 - 중기 추세 살아있음
            try:
                weekly = yf.Ticker(symbol).history(period="2y", interval="1wk", auto_adjust=False)
                weekly = weekly.dropna(subset=["Close"])
                if len(weekly) >= 25:
                    w_rsi = self._rsi(weekly["Close"], 14).dropna()
                    w_cur_rsi = float(w_rsi.iloc[-1])
                    signals["weekly_rsi"]        = round(w_cur_rsi, 1)
                    signals["weekly_rsi_bull"]   = w_cur_rsi >= 50
                    # 주봉 RSI도 상승 기울기면 추가 가산
                    w_slope = float(w_rsi.iloc[-1]) - float(w_rsi.iloc[-4]) if len(w_rsi) >= 4 else 0
                    signals["weekly_rsi_rising"] = w_slope > 0
                    if signals["weekly_rsi_bull"]:   score += 3
                    if signals["weekly_rsi_rising"]: score += 1
                else:
                    signals["weekly_rsi"]        = 50
                    signals["weekly_rsi_bull"]   = False
                    signals["weekly_rsi_rising"] = False
            except:
                signals["weekly_rsi"]        = 50
                signals["weekly_rsi_bull"]   = False
                signals["weekly_rsi_rising"] = False

            # [+3] RSI 수렴 패턴 - 고점 낮아지고 저점 높아지는 삼각 수렴
            try:
                rsi_c = rsi.dropna().values[-30:]  # 최근 30일
                if len(rsi_c) >= 20:
                    # 고점 시퀀스: 짝수 인덱스 피크
                    peaks   = [rsi_c[i] for i in range(2, len(rsi_c)-2)
                               if rsi_c[i] > rsi_c[i-1] and rsi_c[i] > rsi_c[i+1] and rsi_c[i] > 50]
                    troughs = [rsi_c[i] for i in range(2, len(rsi_c)-2)
                               if rsi_c[i] < rsi_c[i-1] and rsi_c[i] < rsi_c[i+1] and rsi_c[i] < 60]
                    converging = (
                        len(peaks) >= 2 and len(troughs) >= 2 and
                        peaks[-1]   < peaks[-2]   and   # 고점 낮아짐
                        troughs[-1] > troughs[-2]        # 저점 높아짐
                    )
                    signals["rsi_converging"] = converging
                    if converging: score += 3
                else:
                    signals["rsi_converging"] = False
            except:
                signals["rsi_converging"] = False

            # [+3] 볼린저밴드 수축 → 확장
            bb_std   = close.rolling(20).std()
            bb_mid   = close.rolling(20).mean()
            bb_w     = (4 * bb_std) / bb_mid.replace(0, np.nan)
            bb_w_avg = bb_w.rolling(40).mean()
            bb_sq = (not pd.isna(bb_w_avg.iloc[-5]) and
                     float(bb_w.iloc[-5]) < float(bb_w_avg.iloc[-5]) * 0.7)
            bb_ex = float(bb_w.iloc[-1]) > float(bb_w.iloc[-5])
            signals["bb_squeeze_expand"] = bb_sq and bb_ex
            if signals["bb_squeeze_expand"]: score += 3

            # [+2] MACD 골든크로스
            try:
                if _TA_AVAILABLE:
                    _macd_ind = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
                    macd   = _macd_ind.macd()
                    macd_s = _macd_ind.macd_signal()
                else:
                    macd   = close.ewm(span=12).mean() - close.ewm(span=26).mean()
                    macd_s = macd.ewm(span=9).mean()
                signals["macd_cross"] = bool(
                    macd.iloc[-1] > macd_s.iloc[-1] and
                    macd.iloc[-2] <= macd_s.iloc[-2]
                )
            except:
                macd   = close.ewm(span=12).mean() - close.ewm(span=26).mean()
                macd_s = macd.ewm(span=9).mean()
                signals["macd_cross"] = bool(
                    macd.iloc[-1] > macd_s.iloc[-1] and
                    macd.iloc[-2] <= macd_s.iloc[-2]
                )
            if signals["macd_cross"]: score += 2

            # [+3] 240일선 하락→상승 전환
            ma240_old_slope = float(ma240.iloc[-20]) - float(ma240.iloc[-40])
            ma240_new_slope = float(ma240.iloc[-1])  - float(ma240.iloc[-20])
            signals["ma240_turning_up"] = ma240_old_slope <= 0 and ma240_new_slope >= 0
            if signals["ma240_turning_up"]: score += 3

            # [+2] MFI (Money Flow Index) - RSI에 거래량 가중
            try:
                if _TA_AVAILABLE:
                    mfi_s = ta.volume.MFIIndicator(high=high, low=low, close=close, volume=vol, window=14).money_flow_index()
                else:
                    tp = (high + low + close) / 3
                    mf = tp * vol
                    pos_mf = mf.where(tp > tp.shift(1), 0).rolling(14).sum()
                    neg_mf = mf.where(tp < tp.shift(1), 0).rolling(14).sum()
                    mfi_s = 100 - (100 / (1 + pos_mf / neg_mf.replace(0, np.nan)))
                cur_mfi = float(mfi_s.iloc[-1])
                signals["mfi"] = round(cur_mfi, 1)
                signals["mfi_oversold_recovery"] = (
                    float(mfi_s.iloc[-5:].min()) < 25 and cur_mfi > 30
                )
                if signals["mfi_oversold_recovery"]: score += 2
            except:
                signals["mfi"] = 50
                signals["mfi_oversold_recovery"] = False

            # [+2] 스토캐스틱 골든크로스 (과매도 구간에서)
            try:
                if _TA_AVAILABLE:
                    _stoch = ta.momentum.StochasticOscillator(high=high, low=low, close=close, window=14, smooth_window=3)
                    k = _stoch.stoch()
                    d = _stoch.stoch_signal()
                else:
                    low14  = low.rolling(14).min()
                    high14 = high.rolling(14).max()
                    k = 100 * (close - low14) / (high14 - low14).replace(0, np.nan)
                    d = k.rolling(3).mean()
                stoch_cross = bool(
                    k.iloc[-1] > d.iloc[-1] and
                    k.iloc[-2] <= d.iloc[-2] and
                    k.iloc[-1] < 50
                )
                signals["stoch_k"] = round(float(k.iloc[-1]), 1)
                signals["stoch_cross"] = stoch_cross
                if stoch_cross: score += 2
            except:
                signals["stoch_k"] = 50
                signals["stoch_cross"] = False

            # [+2] ADX (추세 강도) - 25 이상이면 추세 확인
            try:
                if _TA_AVAILABLE:
                    _adx_ind = ta.trend.ADXIndicator(high=high, low=low, close=close, window=14)
                    adx    = _adx_ind.adx()
                    di_pos = _adx_ind.adx_pos()
                    di_neg = _adx_ind.adx_neg()
                else:
                    tr_s = pd.concat([
                        high - low,
                        (high - close.shift(1)).abs(),
                        (low  - close.shift(1)).abs()
                    ], axis=1).max(axis=1)
                    dm_plus  = (high - high.shift(1)).where((high - high.shift(1)) > (low.shift(1) - low), 0).clip(lower=0)
                    dm_minus = (low.shift(1) - low).where((low.shift(1) - low) > (high - high.shift(1)), 0).clip(lower=0)
                    atr14    = tr_s.ewm(span=14, adjust=False).mean()
                    di_pos   = 100 * dm_plus.ewm(span=14, adjust=False).mean() / atr14.replace(0, np.nan)
                    di_neg   = 100 * dm_minus.ewm(span=14, adjust=False).mean() / atr14.replace(0, np.nan)
                    dx       = 100 * (di_pos - di_neg).abs() / (di_pos + di_neg).replace(0, np.nan)
                    adx      = dx.ewm(span=14, adjust=False).mean()
                cur_adx = float(adx.iloc[-1])
                signals["adx"] = round(cur_adx, 1)
                signals["adx_strong"] = cur_adx >= 25 and float(di_pos.iloc[-1]) > float(di_neg.iloc[-1])
                if signals["adx_strong"]: score += 2
            except:
                signals["adx"] = 0
                signals["adx_strong"] = False

            # [+2] VWAP 위에 있는지 (당일 매수세 우위)
            try:
                vwap = (close * vol).rolling(20).sum() / vol.rolling(20).sum()
                signals["above_vwap"] = bool(current > float(vwap.iloc[-1]))
                if signals["above_vwap"]: score += 2
            except:
                signals["above_vwap"] = False

            # [+3] 일목균형표 - 구름대 돌파
            try:
                tenkan  = (high.rolling(9).max()  + low.rolling(9).min())  / 2
                kijun   = (high.rolling(26).max() + low.rolling(26).min()) / 2
                senkou_a = ((tenkan + kijun) / 2).shift(26)
                senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
                cloud_top = pd.concat([senkou_a, senkou_b], axis=1).max(axis=1)
                cloud_bot = pd.concat([senkou_a, senkou_b], axis=1).min(axis=1)
                ichimoku_bull = bool(
                    current > float(cloud_top.iloc[-1]) and
                    float(tenkan.iloc[-1]) > float(kijun.iloc[-1])
                )
                signals["ichimoku_bull"] = ichimoku_bull
                if ichimoku_bull: score += 3
            except:
                signals["ichimoku_bull"] = False

            # [+2] 52주 신고가 근처 (5% 이내)
            high_52w = float(high.tail(252).max())
            high_ratio = current / high_52w
            signals["near_52w_high"] = high_ratio >= 0.95
            signals["high_ratio"] = round(high_ratio * 100, 1)
            if signals["near_52w_high"]: score += 2

            # ── 시장 상태 필터 ────────────────────────────────────
            market_bull, market_slope = self._market_condition()
            signals["market_bull"]  = market_bull
            signals["market_slope"] = market_slope
            # 하락장이면 점수 패널티
            if not market_bull:
                score = max(0, score - 3)
            elif market_slope > 2:
                score += 2  # 강한 상승장 가산점

            # ── 섹터 모멘텀 ──────────────────────────────────────
            sector_ret = self._sector_momentum(symbol)
            signals["sector_momentum"] = sector_ret
            if sector_ret > 5:   score += 3  # 섹터 강세
            elif sector_ret > 2: score += 1
            elif sector_ret < -5: score = max(0, score - 2)  # 섹터 약세 패널티

            # ── 거래량 패턴 정교화 ───────────────────────────────
            # 3일 연속 거래량 증가 + 가격 상승
            vol3 = vol.iloc[-3:]
            close3 = close.iloc[-3:]
            vol_rising3 = bool(
                vol3.iloc[-1] > vol3.iloc[-2] > vol3.iloc[-3] and
                close3.iloc[-1] > close3.iloc[-2] > close3.iloc[-3]
            )
            signals["vol_price_rising3"] = vol3_rising = vol_rising3
            if vol_rising3: score += 3

            # ── 눌림목 깊이 측정 ─────────────────────────────────
            # 240선 돌파 후 최대 하락폭 (고점 대비 낙폭)
            prices_after = close.iloc[cross_idx:]
            if len(prices_after) >= 3:
                entry_price    = float(close.iloc[cross_idx])
                peak_after     = float(prices_after.max())
                min_after      = float(prices_after.min())
                pullback_depth = (entry_price - min_after) / entry_price * 100
                # 고점 대비 낙폭 (더 정확한 눌림목 측정)
                peak_drawdown  = (peak_after - float(close.iloc[-1])) / peak_after * 100 if peak_after > 0 else 0
                signals["pullback_depth"]  = round(pullback_depth, 1)
                signals["peak_drawdown"]   = round(peak_drawdown, 1)
                # 이상적 낙폭 구간: 고점 대비 10~25%
                if 10 <= peak_drawdown <= 25:
                    score += 4   # 이상적 눌림목 구간
                elif 5 <= peak_drawdown < 10:
                    score += 2   # 얕은 눌림
                elif peak_drawdown > 35:
                    score = max(0, score - 3)  # 너무 깊은 낙폭 패널티
                # 기존 돌파가격 기준 낙폭
                if 3 <= pullback_depth <= 15:
                    score += 2
                elif pullback_depth > 25:
                    score = max(0, score - 2)
            else:
                signals["pullback_depth"] = 0
                signals["peak_drawdown"]  = 0

            # ── Higher Low 패턴 (눌림목 저점 상승) ──────────────
            # 70 이탈 후 저점들이 점점 높아지는지 확인
            try:
                after_ob = close.iloc[overbought_exit:]
                if len(after_ob) >= 10:
                    # 5일 단위로 저점 비교
                    lows = []
                    chunk = 5
                    for i in range(0, len(after_ob) - chunk, chunk):
                        lows.append(float(after_ob.iloc[i:i+chunk].min()))
                    higher_low = len(lows) >= 2 and all(lows[i] <= lows[i+1] for i in range(len(lows)-1))
                    signals["higher_low"] = higher_low
                    if higher_low: score += 4
                else:
                    signals["higher_low"] = False
            except:
                signals["higher_low"] = False

            # [+1~2] 캔들 패턴
            o_s  = data["Open"]
            body = abs(close - o_s)
            ls   = o_s.where(close > o_s, close) - low
            tr   = (high - low).replace(0, np.nan)
            try:    signals["hammer"]         = bool(((ls >= 2*body) & (tr > 0)).iloc[-1])
            except: signals["hammer"]         = False
            try:    signals["bullish_engulf"] = bool(((close > o_s) & (close.shift(1) < o_s.shift(1)) & (close > o_s.shift(1)) & (o_s < close.shift(1))).iloc[-1])
            except: signals["bullish_engulf"] = False
            if signals["hammer"]:         score += 1
            if signals["bullish_engulf"]: score += 2

            # [+1~3] 조정 기간 가산점
            if   below_days >= 240: score += 3
            elif below_days >= 180: score += 2
            elif below_days >= 120: score += 1

            # [+1~2] 뉴스 감성 - 손익비 통과 후 실행 (기본값)
            sentiment, pos_n, neg_n = 0, 0, 0
            signals["news_sentiment"] = 0
            signals["pos_news"]       = 0
            signals["neg_news"]       = 0

            # [+2] 호재 공시 - 손익비 통과 후 실행 (기본값)
            has_disc, disc_types = False, []
            signals["has_disclosure"]   = False
            signals["disclosure_types"] = []

            # ── 1. 세력 매집 감지 (조용한 거래량 증가) ──────────
            # 주가 횡보 + 거래량 꾸준히 증가 = 세력 매집 패턴
            try:
                price_std_20  = float(close.tail(20).std() / close.tail(20).mean())  # 가격 변동성
                vol_trend_20  = float(vol.tail(20).mean() / vol.tail(40).mean())      # 거래량 증가율
                # 가격은 조용하고(변동성 낮음) 거래량은 늘어남 = 매집
                signals["stealth_accumulation"] = price_std_20 < 0.05 and vol_trend_20 > 1.2
                if signals["stealth_accumulation"]: score += 3
            except:
                signals["stealth_accumulation"] = False

            # ── 2. 눌림목 타이밍 정교화 ─────────────────────────
            # 240선 돌파 후 첫 번째 눌림목에서 반등 중인지 확인
            try:
                prices_after = close.iloc[cross_idx:]
                if len(prices_after) >= 5:
                    # 최근 5일 저점 대비 반등 중
                    recent_low5  = float(close.tail(5).min())
                    recent_high5 = float(close.tail(5).max())
                    bounce_pct   = (current - recent_low5) / (recent_low5 + 1e-9) * 100
                    # 저점 대비 2% 이상 반등 + 고점 갱신 중
                    signals["pullback_bounce"] = bounce_pct >= 2.0 and current >= recent_high5 * 0.98
                    if signals["pullback_bounce"]: score += 3
                else:
                    signals["pullback_bounce"] = False
            except:
                signals["pullback_bounce"] = False

            # ── 3. 복합 신호 승수 (강한 조합 = 배율 적용) ───────
            # BB수축 + MACD + 거래량 3종 세트 = 최강 조합
            triple_combo = (
                signals.get("bb_squeeze_expand") and
                signals.get("macd_cross") and
                (signals.get("vol_at_cross") or signals.get("recent_vol"))
            )
            if triple_combo:
                score = int(score * 1.3)  # 30% 가산

            # 이평선 정배열 + 일목균형표 + ADX = 추세 확인 조합
            trend_combo = (
                signals.get("ma_align") and
                signals.get("ichimoku_bull") and
                signals.get("adx_strong")
            )
            if trend_combo:
                score = int(score * 1.2)  # 20% 가산

            # 세력 매집 + OBV 상승 + 눌림목 반등 = 매집 완료 신호
            accumulation_combo = (
                signals.get("stealth_accumulation") and
                signals.get("obv_rising") and
                signals.get("pullback_bounce")
            )
            if accumulation_combo:
                score = int(score * 1.25)  # 25% 가산

            # ── 4. 섹터 모멘텀 강화 ─────────────────────────────
            # 같은 섹터 상위 3개 종목 동반 상승 여부 체크
            try:
                sector_peers = {
                    # 반도체
                    "005930.KS": ["000660.KS","011070.KS","042700.KS"],
                    "000660.KS": ["005930.KS","011070.KS","042700.KS"],
                    "011070.KS": ["005930.KS","000660.KS","042700.KS"],
                    "042700.KS": ["005930.KS","000660.KS","011070.KS"],
                    # 2차전지
                    "006400.KS": ["051910.KS","373220.KS","247540.KQ","066970.KQ"],
                    "051910.KS": ["006400.KS","373220.KS","247540.KQ","066970.KQ"],
                    "373220.KS": ["006400.KS","051910.KS","247540.KQ","066970.KQ"],
                    "247540.KQ": ["006400.KS","051910.KS","373220.KS","066970.KQ"],
                    "066970.KQ": ["006400.KS","051910.KS","373220.KS","247540.KQ"],
                    # 자동차
                    "005380.KS": ["000270.KS","012330.KS","204320.KS"],
                    "000270.KS": ["005380.KS","012330.KS","204320.KS"],
                    "012330.KS": ["005380.KS","000270.KS","204320.KS"],
                    "204320.KS": ["005380.KS","000270.KS","012330.KS"],
                    # 바이오/제약
                    "207940.KS": ["068270.KS","196170.KQ","141080.KQ","298380.KQ"],
                    "068270.KS": ["207940.KS","196170.KQ","141080.KQ","298380.KQ"],
                    "196170.KQ": ["207940.KS","068270.KS","141080.KQ","298380.KQ"],
                    "141080.KQ": ["207940.KS","068270.KS","196170.KQ","298380.KQ"],
                    "298380.KQ": ["207940.KS","068270.KS","196170.KQ","141080.KQ"],
                    # 인터넷/플랫폼
                    "035420.KS": ["035720.KS","323410.KS","251270.KQ"],
                    "035720.KS": ["035420.KS","323410.KS","251270.KQ"],
                    "323410.KS": ["035420.KS","035720.KS","251270.KQ"],
                    # 엔터/게임
                    "041510.KQ": ["035900.KQ","036030.KQ","112040.KQ"],
                    "035900.KQ": ["041510.KQ","036030.KQ","112040.KQ"],
                    "036030.KQ": ["041510.KQ","035900.KQ","112040.KQ"],
                    "112040.KQ": ["041510.KQ","035900.KQ","036030.KQ"],
                    # 조선/방산
                    "329180.KS": ["042660.KS","267250.KS","064350.KS"],
                    "042660.KS": ["329180.KS","267250.KS","064350.KS"],
                    "064350.KS": ["329180.KS","042660.KS","267250.KS"],
                    # 금융
                    "105560.KS": ["055550.KS","316140.KS","175330.KS"],
                    "055550.KS": ["105560.KS","316140.KS","175330.KS"],
                    "316140.KS": ["105560.KS","055550.KS","175330.KS"],
                    # 화장품/뷰티
                    "090430.KS": ["214150.KQ","145020.KQ","950140.KQ"],
                    "214150.KQ": ["090430.KS","145020.KQ","950140.KQ"],
                    "145020.KQ": ["090430.KS","214150.KQ","950140.KQ"],
                    "950140.KQ": ["090430.KS","214150.KQ","145020.KQ"],
                    # 로봇/AI
                    "277810.KQ": ["042700.KS","005930.KS"],
                }
                peers = sector_peers.get(symbol, [])
                if peers:
                    peer_up_count = 0
                    for peer in peers:
                        try:
                            peer_data = yf.Ticker(peer).history(period="5d").dropna(subset=["Close"])
                            if len(peer_data) >= 2:
                                peer_ret = (float(peer_data["Close"].iloc[-1]) - float(peer_data["Close"].iloc[-5])) / float(peer_data["Close"].iloc[-5]) * 100
                                if peer_ret > 2:
                                    peer_up_count += 1
                        except:
                            pass
                    signals["peer_momentum"] = peer_up_count
                    if peer_up_count >= 2: score += 3   # 동종 섹터 동반 상승
                    elif peer_up_count == 1: score += 1
                else:
                    signals["peer_momentum"] = 0
            except:
                signals["peer_momentum"] = 0

            # ── 기관/외국인 수급 ─────────────────────────────────
            inst_net, foreign_net = self._institutional_flow(symbol)
            signals["inst_net_buy"]    = inst_net
            signals["foreign_net_buy"] = foreign_net
            signals["smart_money_in"]  = inst_net > 0 or foreign_net > 0
            signals["both_buying"]     = inst_net > 0 and foreign_net > 0
            if signals["both_buying"]:     score += 6  # 기관+외국인 동시 순매수 = 강한 신호
            elif signals["smart_money_in"]: score += 3  # 둘 중 하나라도 순매수

            # ── 필수 신호 최소 개수 조건 ─────────────────────────
            # 핵심 신호 중 최소 2개 이상 충족해야 통과
            core_signals = [
                signals.get("ma_align"),           # 이평선 정배열
                signals.get("obv_rising"),          # OBV 상승
                signals.get("vol_at_cross"),        # 돌파 시 거래량
                signals.get("vol_surge_sustained"), # 거래량 지속
                signals.get("macd_cross"),          # MACD 골든크로스
                signals.get("ichimoku_bull"),       # 일목균형표
                signals.get("adx_strong"),          # ADX 추세
                signals.get("smart_money_in"),      # 기관/외국인 수급
            ]
            core_count = sum(1 for s in core_signals if s)
            signals["core_signal_count"] = core_count

            has_volume_signal = signals.get("vol_strong_cross") or signals.get("vol_at_cross") or signals.get("vol_surge_sustained")
            has_supply_signal = signals.get("smart_money_in")

            # 핵심 신호 2개 이상 필수
            if core_count < 2:
                return None

            # 거래량 또는 수급 신호 필수
            if not has_volume_signal and not has_supply_signal:
                return None

            # ── ML 점수 보정 ─────────────────────────────────────
            ml_adjusted = ml_score_adjustment(signals, score)
            signals["ml_adjusted_score"] = ml_adjusted

            # ── 손익비 필터: 2.5:1 미만 제외 ────────────────────────
            try:
                tr_f = pd.concat([
                    high - low,
                    (high - close.shift(1)).abs(),
                    (low  - close.shift(1)).abs()
                ], axis=1).max(axis=1)
                atr_f = float(tr_f.rolling(14).mean().dropna().iloc[-1])

                ma240_v_f  = float(ma240.iloc[-1])
                ma20_v_f   = float(ma20.iloc[-1])
                swing_low_f = float(low.tail(20).min())

                # 매수가 (240선 근거)
                entry_cands = []
                if not pd.isna(ma240_v_f):
                    entry_cands.append(ma240_v_f * 1.005)
                entry_cands.append(ma20_v_f)
                entry_cands.append(swing_low_f)
                valid_e = [p for p in entry_cands if p < current]
                entry_f = max(valid_e) if valid_e else current

                # 손절가: RSI(20) 30 돌파 시점 직전 5일 저가 최솟값
                ob_exit_idx = oversold_exit
                look_back_start = max(0, ob_exit_idx - 5)
                stop_f = float(low.iloc[look_back_start:ob_exit_idx].min())

                # 안전 범위: 매수가 대비 -12% ~ -5%
                stop_f = max(stop_f, entry_f * 0.88)
                stop_f = min(stop_f, entry_f * 0.95)
                risk_f = max(entry_f - stop_f, entry_f * 0.01)

                # 목표가: 피보나치 확장 + ATR 복합 (앱과 동일 방식)
                recent_high_f = float(high.tail(120).max())
                recent_low_f  = float(low.tail(120).min())
                swing_range_f = max(recent_high_f - recent_low_f, entry_f * 0.01)

                target_cands = sorted([
                    x for x in [
                        recent_low_f + swing_range_f * 1.272,
                        recent_low_f + swing_range_f * 1.618,
                        recent_low_f + swing_range_f * 2.0,
                        recent_high_f * 1.05,
                        entry_f + atr_f * 3.0,
                        entry_f + atr_f * 5.0,
                    ] if x > entry_f * 1.03
                ])
                min_rr3 = entry_f + risk_f * 3.0
                valid_t = [x for x in target_cands if x >= min_rr3]
                if valid_t:
                    weights = [1 / (x - entry_f) for x in valid_t]
                    target_f = sum(x * w for x, w in zip(valid_t, weights)) / sum(weights)
                elif target_cands:
                    target_f = target_cands[-1]
                else:
                    target_f = entry_f + risk_f * 3.0
                target_f = min(target_f, entry_f * 2.0)

                rr_f = (target_f - entry_f) / risk_f
                signals["rr_ratio"] = round(rr_f, 2)
            except:
                signals["rr_ratio"] = 0

            # ── 손익비 통과 후에만 크롤링 실행 (속도 최적화) ────
            # 하루 1~5개 통과 종목에만 크롤링 → 224번 → 1~5번으로 감소
            sentiment, pos_n, neg_n = self._news_sentiment(symbol)
            signals["news_sentiment"] = sentiment
            signals["pos_news"]       = pos_n
            signals["neg_news"]       = neg_n
            if sentiment > 0.3: score += 2
            elif sentiment > 0: score += 1

            has_disc, disc_types = self._dart_disclosure(symbol)
            signals["has_disclosure"]   = has_disc
            signals["disclosure_types"] = disc_types
            if has_disc: score += 2

            # ML 점수 재보정 (뉴스/공시 반영 후)
            ml_adjusted = ml_score_adjustment(signals, score)
            signals["ml_adjusted_score"] = ml_adjusted

            return {
                "symbol":           symbol,
                "name":             STOCK_NAMES.get(symbol, symbol),
                "current_price":    current,
                "price_change_1d":  round((current - float(close.iloc[-2])) / float(close.iloc[-2]) * 100, 2),
                "ma240":            round(ma240_v, 0),
                "ma1000":           round(ma1000_v, 0) if ma1000_v else None,
                "ma240_gap":        round(gap_pct, 2),
                "gc_days":          gc_days,  # 240/1000 골든크로스 경과일
                "days_since_cross": days_since_cross,
                "below_days":       below_days,
                "total_score":      int(ml_adjusted),
                "raw_score":        score,
                "signals":          signals,
                "rsi":              signals["rsi"],
                "vol_ratio":        round(recent_vr, 2),
                "vol_accumulation": signals["vol_at_cross"] or signals["recent_vol"],
                "obv_divergence":   signals["obv_rising"],
                "bb_squeeze":       signals["bb_squeeze_expand"],
                "squeeze_ratio":    0,
                "near_52w_high":    signals.get("near_52w_high", False),
                "high_ratio":       signals.get("high_ratio", 0),
                "golden_cross_imminent": signals["ma_align"],
                "macd_cross":       signals["macd_cross"],
                "disparity":        round(gap_pct, 2),
                "candle_patterns":  {
                    "hammer":         signals["hammer"],
                    "bullish_engulf": signals["bullish_engulf"],
                    "morning_star":   False,
                    "inv_hammer":     False,
                },
                "news_sentiment":   sentiment,
                "pos_news":         pos_n,
                "neg_news":         neg_n,
                "has_disclosure":   has_disc,
                "disclosure_types": disc_types,
                "inst_net_buy":     inst_net,
                "foreign_net_buy":  foreign_net,
                "smart_money_in":   signals["smart_money_in"],
                "both_buying":      signals["both_buying"],
                "core_signal_count": signals["core_signal_count"],
                "cross_gap_pct":    round(cross_gap, 2),
                "rsi_cycle_pullback": True,
                "rsi_cycle_peak":   signals_pre.get("rsi_cycle_peak", 0),
                "rsi_cycle_cur":    signals_pre.get("rsi_cycle_cur", 0),
                "rsi_slope_up":     signals.get("rsi_slope_up", False),
                "rsi_slope_val":    signals.get("rsi_slope_val", 0),
                "rsi_cross50":      signals.get("rsi_cross50", False),
                "rsi_divergence":   signals.get("rsi_divergence", False),
                "weekly_rsi":       signals.get("weekly_rsi", 50),
                "weekly_rsi_bull":  signals.get("weekly_rsi_bull", False),
                "weekly_rsi_rising":signals.get("weekly_rsi_rising", False),
                "rsi_converging":   signals.get("rsi_converging", False),
                "rsi2":             signals.get("rsi2", 50),
                "rsi2_oversold":    signals.get("rsi2_oversold", False),
                "rsi2_connors_entry": signals.get("rsi2_connors_entry", False),
                "rs_score_1m":      signals.get("rs_score_1m", 0),
                "rs_score_3m":      signals.get("rs_score_3m", 0),
                "rs_outperform":    signals.get("rs_outperform", False),
                "rs_strong":        signals.get("rs_strong", False),
                "peak_drawdown":    signals.get("peak_drawdown", 0),
                "higher_low":       signals.get("higher_low", False),
                "close_series":     close,
                "high_series":      high,
                "low_series":       low,
                "open_series":      data["Open"],
                "ma240_series":     ma240,
                "ma1000_series":    ma1000,
                "ma60_series":      ma60,
                "ma20_series":      ma20,
                "rsi_series":       rsi,
                "volume_series":    vol,
                "vol_ma_series":    vol_ma20,
            }

        except Exception as e:
            return None

    def analyze_all_stocks(self, as_of_date=None):
        results = []
        date_label = str(as_of_date) if as_of_date else "오늘"
        print(f"스캔 중 ({date_label} 기준)...")

        # ── KOSPI 상태 1회만 가져와서 공유 ──
        kospi_filter = True
        try:
            kospi_df = yf.Ticker("^KS11").history(period="1y", auto_adjust=False).dropna(subset=["Close"])
            if as_of_date:
                import pandas as _pd
                cutoff = _pd.Timestamp(as_of_date).tz_localize(kospi_df.index.tz) if kospi_df.index.tz else _pd.Timestamp(as_of_date)
                kospi_df = kospi_df[kospi_df.index <= cutoff]
            if len(kospi_df) > 200:
                kospi_cur   = float(kospi_df["Close"].iloc[-1])
                kospi_ma200 = float(kospi_df["Close"].rolling(200).mean().iloc[-1])
                if kospi_cur < kospi_ma200 * 0.97:
                    kospi_filter = False
                    print(f"[하락장 감지] KOSPI {kospi_cur:,.0f} / 200일선 {kospi_ma200:,.0f} → 스캔 중단")
        except:
            pass

        if not kospi_filter:
            return []

        # 과거 날짜 스캔이면 당일 종가 보완 불필요
        self._today_price_cache = {}
        if as_of_date is None:
            try:
                test_df = yf.Ticker("005930.KS").history(period="3d")
                need_today_price = len(test_df) > 0 and pd.isna(test_df["Close"].iloc[-1])
                if need_today_price:
                    print("[당일종가] yfinance NaN → 네이버에서 병렬 수집 중...")
                    def _fetch_naver_price(sym):
                        try:
                            code = sym.replace(".KS","").replace(".KQ","")
                            url = f"https://finance.naver.com/item/main.naver?code={code}"
                            res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=2)
                            soup = BeautifulSoup(res.text, "html.parser")
                            tag = soup.select_one(".no_today .blind")
                            return (sym, float(tag.get_text().replace(",","")) if tag else None)
                        except:
                            return (sym, None)
                    from concurrent.futures import ThreadPoolExecutor as TPE
                    with TPE(max_workers=20) as ex:
                        for sym, price in ex.map(_fetch_naver_price, self.all_symbols):
                            if price:
                                self._today_price_cache[sym] = price
                    print(f"[당일종가] {len(self._today_price_cache)}개 수집 완료")
            except:
                pass

        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(self.analyze_stock, sym, as_of_date): sym for sym in self.all_symbols}
            for future in as_completed(futures):
                sym = futures[future]
                try:
                    r = future.result()
                    if r:
                        results.append(r)
                        print(f"  OK {sym} ({r['total_score']}pt)")
                    else:
                        print(f"  [X] {sym}")
                except Exception as e:
                    print(f"  [!] {sym}: {e}")
        return sorted(results, key=lambda x: x["total_score"], reverse=True)

    def run_analysis(self):
        print(f"한국 주식 급등 예측 v3.0  ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        print(f"조건: 240선 아래 {self.min_below_days}일+ → {self.max_cross_days}일내 돌파 → 근처 {self.max_gap_pct}%")
        results = self.analyze_all_stocks()
        print(f"\n총 {len(results)}개 종목 발견")
        for r in results:
            print(f"  {r['name']:12} 점수:{r['total_score']:2d}  "
                  f"240선위:{r['ma240_gap']:+.1f}%  "
                  f"조정:{r['below_days']}일  돌파:{r['days_since_cross']}일전")
        return results

    def analyze_stock_classic(self, symbol, as_of_date=None):
        """
        기존 240일선 돌파 전략
        조건:
          1) 240선 아래 min_below_days 이상 조정
          2) 최근 max_cross_days 이내 240선 상향 돌파
          3) 현재가 240선 위 0~max_gap_pct%
        """
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="2y", auto_adjust=False)

            if as_of_date is not None:
                import pandas as _pd
                cutoff = _pd.Timestamp(as_of_date).tz_localize(data.index.tz) if data.index.tz else _pd.Timestamp(as_of_date)
                data = data[data.index <= cutoff]
                if len(data) == 0:
                    return None

            if len(data) > 0 and pd.isna(data["Close"].iloc[-1]):
                today_price = getattr(self, '_today_price_cache', {}).get(symbol)
                if today_price:
                    data.loc[data.index[-1], "Open"]  = today_price
                    data.loc[data.index[-1], "High"]  = today_price
                    data.loc[data.index[-1], "Low"]   = today_price
                    data.loc[data.index[-1], "Close"] = today_price

            data = data.dropna(subset=["Open","High","Low","Close"])
            if len(data) < 260:
                return None

            close = data["Close"]
            high  = data["High"]
            low   = data["Low"]
            vol   = data["Volume"]
            n     = len(close)

            avg_amount = float(close.tail(20).mean()) * float(vol.tail(20).mean())
            if avg_amount < 2_000_000_000:
                return None

            ma240 = close.rolling(240).mean()
            ma60  = close.rolling(60).mean()
            ma20  = close.rolling(20).mean()
            ma5   = close.rolling(5).mean()

            if pd.isna(ma240.iloc[-1]):
                return None

            current = float(close.iloc[-1])
            ma240_v = float(ma240.iloc[-1])

            # 조건1: 현재가 240선 위 0~max_gap_pct%
            gap_pct = (current - ma240_v) / ma240_v * 100
            if not (0 <= gap_pct <= self.max_gap_pct):
                return None

            # 조건2: max_cross_days 이내 240선 상향 돌파
            cross_idx = None
            for i in range(n-1, max(n - self.max_cross_days - 1, 240), -1):
                if close.iloc[i] > ma240.iloc[i] and close.iloc[i-1] <= ma240.iloc[i-1]:
                    cross_idx = i
                    break
            if cross_idx is None:
                return None

            # 가짜 돌파 방지
            confirm_end = min(cross_idx + 4, n)
            days_above = sum(1 for i in range(cross_idx, confirm_end) if float(close.iloc[i]) > float(ma240.iloc[i]))
            if days_above < 3:
                return None

            cross_gap = (float(close.iloc[cross_idx]) - float(ma240.iloc[cross_idx])) / float(ma240.iloc[cross_idx]) * 100
            if cross_gap < 0.5:
                return None

            days_since_cross = n - 1 - cross_idx

            # 조건3: 돌파 직전 min_below_days 이상 조정
            below_days = 0
            for i in range(cross_idx - 1, -1, -1):
                if not pd.isna(ma240.iloc[i]) and close.iloc[i] < ma240.iloc[i]:
                    below_days += 1
                else:
                    break
            if below_days < self.min_below_days:
                below_days = sum(1 for i in range(cross_idx) if not pd.isna(ma240.iloc[i]) and close.iloc[i] < ma240.iloc[i])
            if below_days < self.min_below_days:
                return None

            # 240선 기울기 체크
            ma240_at_cross   = float(ma240.iloc[cross_idx])
            ma240_20d_before = float(ma240.iloc[cross_idx - 20]) if cross_idx >= 20 else ma240_at_cross
            if (ma240_at_cross - ma240_20d_before) / ma240_20d_before * 100 < -3.0:
                return None

            # 돌파 후 재이탈 제한
            consecutive = 0
            for i in range(cross_idx + 1, n):
                if float(close.iloc[i]) < float(ma240.iloc[i]):
                    consecutive += 1
                    if consecutive >= 3:
                        return None
                else:
                    consecutive = 0

            # 점수 계산 - 기존 analyze_stock과 동일한 전체 신호
            score   = 0
            signals = {"rsi_cycle_pullback": False}

            vol_ma20  = vol.rolling(20).mean()
            cross_vr  = float(vol.iloc[cross_idx] / vol_ma20.iloc[cross_idx]) if vol_ma20.iloc[cross_idx] > 0 else 0
            recent_vr = float(vol.iloc[-5:].mean() / vol_ma20.iloc[-1]) if vol_ma20.iloc[-1] > 0 else 0
            signals["vol_at_cross"]     = cross_vr >= 2.0
            signals["vol_strong_cross"] = cross_vr >= 3.0
            signals["recent_vol"]       = recent_vr >= 1.5
            signals["cross_vol_ratio"]  = round(cross_vr, 2)
            signals["recent_vol_ratio"] = round(recent_vr, 2)
            if signals["vol_strong_cross"]: score += 4
            elif signals["vol_at_cross"]:   score += 3
            if signals["recent_vol"]:       score += 2

            try:
                vol_before5 = float(vol.iloc[cross_idx-5:cross_idx].mean())
                vol_after5  = float(vol.iloc[cross_idx:cross_idx+5].mean())
                signals["vol_surge_sustained"] = vol_after5 > vol_before5 * 1.5
                if signals["vol_surge_sustained"]: score += 2
            except:
                signals["vol_surge_sustained"] = False

            obv = self._obv(data)
            obv_after = obv.iloc[cross_idx:]
            signals["obv_rising"] = len(obv_after) > 1 and float(obv_after.iloc[-1]) > float(obv_after.iloc[0])
            if signals["obv_rising"]: score += 2

            signals["ma_align"] = bool(ma5.iloc[-1] > ma20.iloc[-1] > ma60.iloc[-1])
            if signals["ma_align"]: score += 3

            pa = close.iloc[cross_idx:]
            signals["pullback_recovery"] = (len(pa) >= 3 and float(pa.min()) < float(pa.iloc[0]) and current > float(close.iloc[cross_idx]))
            if signals["pullback_recovery"]: score += 2

            rsi = self._rsi(close, 20)
            cur_rsi = float(rsi.iloc[-1])
            signals["rsi"]         = round(cur_rsi, 1)
            signals["rsi_healthy"] = 40 <= cur_rsi <= 65
            if signals["rsi_healthy"]: score += 2

            bb_std = close.rolling(20).std()
            bb_mid = close.rolling(20).mean()
            bb_w   = (4 * bb_std) / bb_mid.replace(0, np.nan)
            bb_w_avg = bb_w.rolling(40).mean()
            bb_sq = (not pd.isna(bb_w_avg.iloc[-5]) and float(bb_w.iloc[-5]) < float(bb_w_avg.iloc[-5]) * 0.7)
            bb_ex = float(bb_w.iloc[-1]) > float(bb_w.iloc[-5])
            signals["bb_squeeze_expand"] = bb_sq and bb_ex
            if signals["bb_squeeze_expand"]: score += 3

            try:
                if _TA_AVAILABLE:
                    _macd_ind = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
                    macd   = _macd_ind.macd()
                    macd_s = _macd_ind.macd_signal()
                else:
                    macd   = close.ewm(span=12).mean() - close.ewm(span=26).mean()
                    macd_s = macd.ewm(span=9).mean()
                signals["macd_cross"] = bool(macd.iloc[-1] > macd_s.iloc[-1] and macd.iloc[-2] <= macd_s.iloc[-2])
            except:
                macd   = close.ewm(span=12).mean() - close.ewm(span=26).mean()
                macd_s = macd.ewm(span=9).mean()
                signals["macd_cross"] = bool(macd.iloc[-1] > macd_s.iloc[-1] and macd.iloc[-2] <= macd_s.iloc[-2])
            if signals["macd_cross"]: score += 2

            ma240_old = float(ma240.iloc[-20]) - float(ma240.iloc[-40])
            ma240_new = float(ma240.iloc[-1])  - float(ma240.iloc[-20])
            signals["ma240_turning_up"] = ma240_old <= 0 and ma240_new >= 0
            if signals["ma240_turning_up"]: score += 3

            try:
                if _TA_AVAILABLE:
                    mfi_s = ta.volume.MFIIndicator(high=high, low=low, close=close, volume=vol, window=14).money_flow_index()
                else:
                    tp = (high + low + close) / 3
                    mf = tp * vol
                    pos_mf = mf.where(tp > tp.shift(1), 0).rolling(14).sum()
                    neg_mf = mf.where(tp < tp.shift(1), 0).rolling(14).sum()
                    mfi_s = 100 - (100 / (1 + pos_mf / neg_mf.replace(0, np.nan)))
                cur_mfi = float(mfi_s.iloc[-1])
                signals["mfi"] = round(cur_mfi, 1)
                signals["mfi_oversold_recovery"] = (float(mfi_s.iloc[-5:].min()) < 25 and cur_mfi > 30)
                if signals["mfi_oversold_recovery"]: score += 2
            except:
                signals["mfi"] = 50
                signals["mfi_oversold_recovery"] = False

            try:
                if _TA_AVAILABLE:
                    _stoch = ta.momentum.StochasticOscillator(high=high, low=low, close=close, window=14, smooth_window=3)
                    k = _stoch.stoch(); d = _stoch.stoch_signal()
                else:
                    low14 = low.rolling(14).min(); high14 = high.rolling(14).max()
                    k = 100 * (close - low14) / (high14 - low14).replace(0, np.nan)
                    d = k.rolling(3).mean()
                signals["stoch_k"]    = round(float(k.iloc[-1]), 1)
                signals["stoch_cross"] = bool(k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2] and k.iloc[-1] < 50)
                if signals["stoch_cross"]: score += 2
            except:
                signals["stoch_k"] = 50; signals["stoch_cross"] = False

            try:
                if _TA_AVAILABLE:
                    _adx_ind = ta.trend.ADXIndicator(high=high, low=low, close=close, window=14)
                    adx = _adx_ind.adx(); di_pos = _adx_ind.adx_pos(); di_neg = _adx_ind.adx_neg()
                else:
                    tr_s = pd.concat([high-low,(high-close.shift(1)).abs(),(low-close.shift(1)).abs()],axis=1).max(axis=1)
                    dm_plus  = (high-high.shift(1)).where((high-high.shift(1))>(low.shift(1)-low),0).clip(lower=0)
                    dm_minus = (low.shift(1)-low).where((low.shift(1)-low)>(high-high.shift(1)),0).clip(lower=0)
                    atr14 = tr_s.ewm(span=14,adjust=False).mean()
                    di_pos = 100*dm_plus.ewm(span=14,adjust=False).mean()/atr14.replace(0,np.nan)
                    di_neg = 100*dm_minus.ewm(span=14,adjust=False).mean()/atr14.replace(0,np.nan)
                    dx = 100*(di_pos-di_neg).abs()/(di_pos+di_neg).replace(0,np.nan)
                    adx = dx.ewm(span=14,adjust=False).mean()
                signals["adx"] = round(float(adx.iloc[-1]), 1)
                signals["adx_strong"] = float(adx.iloc[-1]) >= 25 and float(di_pos.iloc[-1]) > float(di_neg.iloc[-1])
                if signals["adx_strong"]: score += 2
            except:
                signals["adx"] = 0; signals["adx_strong"] = False

            try:
                vwap = (close * vol).rolling(20).sum() / vol.rolling(20).sum()
                signals["above_vwap"] = bool(current > float(vwap.iloc[-1]))
                if signals["above_vwap"]: score += 2
            except:
                signals["above_vwap"] = False

            try:
                tenkan  = (high.rolling(9).max()  + low.rolling(9).min())  / 2
                kijun   = (high.rolling(26).max() + low.rolling(26).min()) / 2
                senkou_a = ((tenkan + kijun) / 2).shift(26)
                senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
                cloud_top = pd.concat([senkou_a, senkou_b], axis=1).max(axis=1)
                signals["ichimoku_bull"] = bool(current > float(cloud_top.iloc[-1]) and float(tenkan.iloc[-1]) > float(kijun.iloc[-1]))
                if signals["ichimoku_bull"]: score += 3
            except:
                signals["ichimoku_bull"] = False

            high_52w = float(high.tail(252).max())
            signals["near_52w_high"] = current / high_52w >= 0.95
            signals["high_ratio"]    = round(current / high_52w * 100, 1)
            if signals["near_52w_high"]: score += 2

            market_bull, market_slope = self._market_condition()
            signals["market_bull"] = market_bull; signals["market_slope"] = market_slope
            if not market_bull: score = max(0, score - 3)
            elif market_slope > 2: score += 2

            sector_ret = self._sector_momentum(symbol)
            signals["sector_momentum"] = sector_ret
            if sector_ret > 5: score += 3
            elif sector_ret > 2: score += 1
            elif sector_ret < -5: score = max(0, score - 2)

            vol3 = vol.iloc[-3:]; close3 = close.iloc[-3:]
            signals["vol_price_rising3"] = bool(vol3.iloc[-1]>vol3.iloc[-2]>vol3.iloc[-3] and close3.iloc[-1]>close3.iloc[-2]>close3.iloc[-3])
            if signals["vol_price_rising3"]: score += 3

            prices_after = close.iloc[cross_idx:]
            if len(prices_after) >= 3:
                entry_price = float(close.iloc[cross_idx])
                min_after   = float(prices_after.min())
                pullback_depth = (entry_price - min_after) / entry_price * 100
                signals["pullback_depth"] = round(pullback_depth, 1)
                if 3 <= pullback_depth <= 15: score += 3
                elif pullback_depth > 25: score = max(0, score - 2)
            else:
                signals["pullback_depth"] = 0

            o_s  = data["Open"]; body = abs(close - o_s)
            ls   = o_s.where(close > o_s, close) - low
            tr   = (high - low).replace(0, np.nan)
            try:    signals["hammer"]         = bool(((ls >= 2*body) & (tr > 0)).iloc[-1])
            except: signals["hammer"]         = False
            try:    signals["bullish_engulf"] = bool(((close > o_s) & (close.shift(1) < o_s.shift(1)) & (close > o_s.shift(1)) & (o_s < close.shift(1))).iloc[-1])
            except: signals["bullish_engulf"] = False
            if signals["hammer"]:         score += 1
            if signals["bullish_engulf"]: score += 2

            if   below_days >= 240: score += 3
            elif below_days >= 180: score += 2
            elif below_days >= 120: score += 1

            try:
                price_std_20 = float(close.tail(20).std() / close.tail(20).mean())
                vol_trend_20 = float(vol.tail(20).mean() / vol.tail(40).mean())
                signals["stealth_accumulation"] = price_std_20 < 0.05 and vol_trend_20 > 1.2
                if signals["stealth_accumulation"]: score += 3
            except:
                signals["stealth_accumulation"] = False

            try:
                if len(prices_after) >= 5:
                    recent_low5  = float(close.tail(5).min())
                    recent_high5 = float(close.tail(5).max())
                    bounce_pct   = (current - recent_low5) / (recent_low5 + 1e-9) * 100
                    signals["pullback_bounce"] = bounce_pct >= 2.0 and current >= recent_high5 * 0.98
                    if signals["pullback_bounce"]: score += 3
                else:
                    signals["pullback_bounce"] = False
            except:
                signals["pullback_bounce"] = False

            triple_combo = signals.get("bb_squeeze_expand") and signals.get("macd_cross") and (signals.get("vol_at_cross") or signals.get("recent_vol"))
            if triple_combo: score = int(score * 1.3)
            trend_combo = signals.get("ma_align") and signals.get("ichimoku_bull") and signals.get("adx_strong")
            if trend_combo: score = int(score * 1.2)
            accumulation_combo = signals.get("stealth_accumulation") and signals.get("obv_rising") and signals.get("pullback_bounce")
            if accumulation_combo: score = int(score * 1.25)

            inst_net, foreign_net = self._institutional_flow(symbol)
            signals["inst_net_buy"]    = inst_net
            signals["foreign_net_buy"] = foreign_net
            signals["smart_money_in"]  = inst_net > 0 or foreign_net > 0
            signals["both_buying"]     = inst_net > 0 and foreign_net > 0
            if signals["both_buying"]:      score += 6
            elif signals["smart_money_in"]: score += 3

            core_signals = [signals.get("ma_align"), signals.get("obv_rising"), signals.get("vol_at_cross"),
                            signals.get("vol_surge_sustained"), signals.get("macd_cross"),
                            signals.get("ichimoku_bull"), signals.get("adx_strong"), signals.get("smart_money_in")]
            signals["core_signal_count"] = sum(1 for s in core_signals if s)

            # 핵심 신호 2개 이상 필수
            if signals["core_signal_count"] < 2:
                return None

            # 거래량 또는 수급 신호 필수
            has_volume = signals.get("vol_strong_cross") or signals.get("vol_at_cross") or signals.get("vol_surge_sustained")
            has_supply = signals.get("smart_money_in")
            if not has_volume and not has_supply:
                return None

            ml_adjusted = ml_score_adjustment(signals, score)
            signals["ml_adjusted_score"] = ml_adjusted

            sentiment, pos_n, neg_n = self._news_sentiment(symbol)
            signals["news_sentiment"] = sentiment; signals["pos_news"] = pos_n; signals["neg_news"] = neg_n
            if sentiment > 0.3: score += 2
            elif sentiment > 0: score += 1

            has_disc, disc_types = self._dart_disclosure(symbol)
            signals["has_disclosure"] = has_disc; signals["disclosure_types"] = disc_types
            if has_disc: score += 2

            ml_adjusted = ml_score_adjustment(signals, score)
            signals["ml_adjusted_score"] = ml_adjusted

            return {
                "symbol":           symbol,
                "name":             STOCK_NAMES.get(symbol, symbol),
                "current_price":    current,
                "price_change_1d":  round((current - float(close.iloc[-2])) / float(close.iloc[-2]) * 100, 2),
                "ma240":            round(ma240_v, 0),
                "ma1000":           None,
                "ma240_gap":        round(gap_pct, 2),
                "days_since_cross": days_since_cross,
                "below_days":       below_days,
                "total_score":      int(ml_adjusted),
                "raw_score":        score,
                "signals":          signals,
                "rsi":              signals["rsi"],
                "vol_ratio":        round(recent_vr, 2),
                "vol_accumulation": signals["vol_at_cross"] or signals["recent_vol"],
                "obv_divergence":   signals["obv_rising"],
                "bb_squeeze":       signals["bb_squeeze_expand"],
                "squeeze_ratio":    0,
                "near_52w_high":    signals.get("near_52w_high", False),
                "high_ratio":       signals.get("high_ratio", 0),
                "golden_cross_imminent": signals["ma_align"],
                "macd_cross":       signals["macd_cross"],
                "disparity":        round(gap_pct, 2),
                "candle_patterns":  {"hammer": signals["hammer"], "bullish_engulf": signals["bullish_engulf"], "morning_star": False, "inv_hammer": False},
                "news_sentiment":   sentiment,
                "pos_news":         pos_n,
                "neg_news":         neg_n,
                "has_disclosure":   has_disc,
                "disclosure_types": disc_types,
                "inst_net_buy":     inst_net,
                "foreign_net_buy":  foreign_net,
                "smart_money_in":   signals["smart_money_in"],
                "both_buying":      signals["both_buying"],
                "core_signal_count": signals["core_signal_count"],
                "cross_gap_pct":    round(cross_gap, 2),
                "rsi_cycle_pullback": False,
                "rsi_cycle_peak":   0,
                "rsi_cycle_cur":    cur_rsi,
                "gc_days":          None,
                "close_series":     close,
                "high_series":      high,
                "low_series":       low,
                "open_series":      data["Open"],
                "ma240_series":     ma240,
                "ma1000_series":    None,
                "ma60_series":      ma60,
                "ma20_series":      ma20,
                "rsi_series":       rsi,
                "volume_series":    vol,
                "vol_ma_series":    vol_ma20,
            }
        except Exception as e:
            return None

    def analyze_all_stocks_classic(self, as_of_date=None):
        """기존 240선 돌파 전략으로 전체 종목 스캔"""
        results = []
        print("스캔 중 (장기선 돌파 전략)...")

        kospi_filter = True
        try:
            kospi_df = yf.Ticker("^KS11").history(period="1y", auto_adjust=False).dropna(subset=["Close"])
            if as_of_date:
                import pandas as _pd
                cutoff = _pd.Timestamp(as_of_date).tz_localize(kospi_df.index.tz) if kospi_df.index.tz else _pd.Timestamp(as_of_date)
                kospi_df = kospi_df[kospi_df.index <= cutoff]
            if len(kospi_df) > 200:
                kc = float(kospi_df["Close"].iloc[-1])
                km = float(kospi_df["Close"].rolling(200).mean().iloc[-1])
                if kc < km * 0.97:
                    kospi_filter = False
                    print(f"[하락장] KOSPI {kc:,.0f} / 200선 {km:,.0f} → 스캔 중단")
        except:
            pass

        if not kospi_filter:
            return []

        self._today_price_cache = {}

        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(self.analyze_stock_classic, sym, as_of_date): sym for sym in self.all_symbols}
            for future in as_completed(futures):
                sym = futures[future]
                try:
                    r = future.result()
                    if r:
                        results.append(r)
                        print(f"  OK {sym} ({r['total_score']}pt)")
                except Exception as e:
                    pass
        return sorted(results, key=lambda x: x["total_score"], reverse=True)

    # ── RSI(20) 강세 다이버전스 전용 스캔 ────────────────────────────

    def analyze_stock_divergence(self, symbol):
        """
        RSI(20) 강세 다이버전스 전용 스캔
        신뢰도 높은 조건 3가지 동시 충족:
          1) 과매도 구간(RSI 30 이하)에서 발생
          2) 두 저점 간격 20일 이상
          3) 두 번째 저점에서 거래량 감소 (매도 세력 소진)
        """
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="2y", auto_adjust=False)
            data = data.dropna(subset=["Open","High","Low","Close"])
            if len(data) < 60:
                return None

            # 거래대금 필터
            avg_amount = float(data["Close"].tail(20).mean()) * float(data["Volume"].tail(20).mean())
            if avg_amount < 2_000_000_000:
                return None

            close = data["Close"]
            high  = data["High"]
            low   = data["Low"]
            vol   = data["Volume"]
            n     = len(close)

            rsi = self._rsi(close, 20).fillna(50)
            rsi_vals   = rsi.values
            close_vals = close.values
            vol_vals   = vol.values

            # 최근 120일 내에서 탐색 (범위 축소 - 최신 신호만)
            search_start = max(1, n - 120)

            # 저점 후보 수집: 주가 로컬 최저점 기준, RSI 45 이하만
            troughs = []
            for i in range(search_start + 5, n - 5):
                price_window = close_vals[max(0, i-5): i+6]
                if close_vals[i] != price_window.min():
                    continue
                if rsi_vals[i] > 45:  # RSI 45 이하만 (과매도 근처)
                    continue
                troughs.append((i, float(close_vals[i]), float(rsi_vals[i]), float(vol_vals[i])))

            if len(troughs) < 2:
                return None

            # 전체 저점 쌍 중 다이버전스 조건 충족하는 최적 조합 탐색
            best_pair = None
            for j in range(len(troughs) - 1, 0, -1):
                t2_cand = troughs[j]
                for i in range(j - 1, -1, -1):
                    t1_cand = troughs[i]
                    if t2_cand[0] - t1_cand[0] < 30:    # 30일 이상 간격
                        continue
                    if t2_cand[1] >= t1_cand[1] * 0.92:  # 주가 8% 이상 하락
                        continue
                    if t2_cand[2] <= t1_cand[2] + 6.0:   # RSI 6 이상 상승
                        continue
                    best_pair = (t1_cand, t2_cand)
                    break
                if best_pair:
                    break

            if not best_pair:
                return None

            t1, t2 = best_pair

            # 거래량 감소 체크 (가산점용, 필수 아님)
            vol_ma20_t2 = float(vol.iloc[max(0, t2[0]-20): t2[0]].mean()) if t2[0] > 20 else t2[3]
            vol_ratio_t2 = t2[3] / vol_ma20_t2 if vol_ma20_t2 > 0 else 1.0
            vol_decreasing = vol_ratio_t2 < 0.9

            # 핵심 조건 3: 현재 RSI가 t2보다 10 이상 반등 중
            cur_rsi = float(rsi_vals[-1])
            if cur_rsi <= t2[2] + 10:
                return None
            current = float(close_vals[-1])
            signals = {}  # 신호 딕셔너리 초기화

            # ── 필수 조건: 주봉 RSI(20) 다이버전스 동시 충족 ────────
            # 일봉 다이버전스만으로는 노이즈 많음 → 주봉도 같은 방향이어야 신뢰도 높음
            try:
                weekly = yf.Ticker(symbol).history(period="2y", interval="1wk", auto_adjust=False).dropna(subset=["Close"])
                if len(weekly) >= 25:
                    w_rsi = self._rsi(weekly["Close"], 20).dropna()
                    w_cur = float(w_rsi.iloc[-1])
                    w_slope = float(w_rsi.iloc[-1]) - float(w_rsi.iloc[-4]) if len(w_rsi) >= 4 else 0
                    w_vals = w_rsi.values
                    w_close = weekly["Close"].reindex(w_rsi.index).values
                    w_div = False
                    if len(w_vals) >= 10:
                        # 최근 12주 저점 vs 이전 24주 저점 (윈도우 확대)
                        w_recent_low_idx = int(np.argmin(w_close[-12:])) + len(w_close) - 12
                        w_prev_window_close = w_close[-36:-12]
                        w_prev_window_rsi   = w_vals[-36:-12]
                        if len(w_prev_window_close) > 0:
                            w_prev_low_idx_rel = int(np.argmin(w_prev_window_close))
                            w_div = (
                                w_close[w_recent_low_idx] < w_prev_window_close[w_prev_low_idx_rel] * 1.03 and
                                w_vals[w_recent_low_idx]  > w_prev_window_rsi[w_prev_low_idx_rel] + 2.0
                            )
                    signals["weekly_rsi"]        = round(w_cur, 1)
                    signals["weekly_rsi_bull"]   = w_cur >= 45
                    signals["weekly_rsi_slope"]  = round(w_slope, 1)
                    signals["weekly_rsi_rising"] = w_slope > 0
                    signals["weekly_rsi_div"]    = w_div
                else:
                    w_div = False
                    signals["weekly_rsi"]        = 50
                    signals["weekly_rsi_bull"]   = False
                    signals["weekly_rsi_slope"]  = 0
                    signals["weekly_rsi_rising"] = False
                    signals["weekly_rsi_div"]    = False
            except:
                w_div = False
                signals["weekly_rsi"]        = 50
                signals["weekly_rsi_bull"]   = False
                signals["weekly_rsi_slope"]  = 0
                signals["weekly_rsi_rising"] = False
                signals["weekly_rsi_div"]    = False

            # 주봉 필수 조건: 다이버전스 OR 주봉 RSI 상승 기울기 (둘 중 하나)
            if not w_div and not signals.get("weekly_rsi_rising"):
                return None

            # 점수 계산 시작
            score = 0
            signals["div_price_drop"]   = round((t2[1] - t1[1]) / t1[1] * 100, 2)
            signals["div_rsi_gain"]     = round(t2[2] - t1[2], 1)
            signals["div_t1_rsi"]       = round(t1[2], 1)
            signals["div_t2_rsi"]       = round(t2[2], 1)
            signals["div_gap_days"]     = t2[0] - t1[0]
            signals["vol_ratio_t2"]     = round(vol_ratio_t2, 2)
            signals["vol_decreasing"]   = vol_decreasing

            score += 10  # 일봉 다이버전스 기본
            score += 8   # 주봉 다이버전스 추가 (필수 통과 보상)
            if vol_decreasing: score += 3
            if t2[2] - t1[2] >= 5: score += 3
            elif t2[2] - t1[2] >= 3: score += 1
            if t1[2] <= 35 and t2[2] <= 35: score += 3
            if signals["weekly_rsi_bull"]:   score += 3
            if signals["weekly_rsi_rising"]: score += 2

            # [+2] OBV 상승 (두 번째 저점 이후)
            obv = self._obv(data)
            obv_after = obv.iloc[t2[0]:]
            signals["obv_rising"] = len(obv_after) > 1 and float(obv_after.iloc[-1]) > float(obv_after.iloc[0])
            if signals["obv_rising"]: score += 2

            # [+2] 이평선 정배열 시작
            ma5  = close.rolling(5).mean()
            ma20_s = close.rolling(20).mean()
            ma60_s = close.rolling(60).mean()
            signals["ma_align"] = bool(ma5.iloc[-1] > ma20_s.iloc[-1] > ma60_s.iloc[-1])
            if signals["ma_align"]: score += 2

            # [+2] 거래량 최근 증가 (반등 확인)
            vol_ma20 = vol.rolling(20).mean()
            recent_vr = float(vol.iloc[-5:].mean() / vol_ma20.iloc[-1]) if vol_ma20.iloc[-1] > 0 else 0
            signals["recent_vol"] = recent_vr >= 1.3
            if signals["recent_vol"]: score += 2

            signals["rsi"]         = round(cur_rsi, 1)
            signals["current_rsi"] = round(cur_rsi, 1)

            ma240 = close.rolling(240).mean()
            ma240_v = float(ma240.iloc[-1]) if not pd.isna(ma240.iloc[-1]) else None

            return {
                "symbol":           symbol,
                "name":             STOCK_NAMES.get(symbol, symbol),
                "current_price":    current,
                "price_change_1d":  round((current - float(close.iloc[-2])) / float(close.iloc[-2]) * 100, 2),
                "ma240":            round(ma240_v, 0) if ma240_v else None,
                "ma240_gap":        round((current - ma240_v) / ma240_v * 100, 2) if ma240_v else None,
                "total_score":      score,
                "raw_score":        score,
                "signals":          signals,
                "rsi":              round(cur_rsi, 1),
                "div_price_drop":   signals["div_price_drop"],
                "div_rsi_gain":     signals["div_rsi_gain"],
                "div_t1_rsi":       signals["div_t1_rsi"],
                "div_t2_rsi":       signals["div_t2_rsi"],
                "div_gap_days":     signals["div_gap_days"],
                "vol_decreasing":   vol_decreasing,
                "rsi_rebounding":   cur_rsi > t2[2] + 5,
                "weekly_rsi":       signals.get("weekly_rsi", 50),
                "weekly_rsi_bull":  signals.get("weekly_rsi_bull", False),
                "weekly_rsi_rising":signals.get("weekly_rsi_rising", False),
                "weekly_rsi_div":   signals.get("weekly_rsi_div", False),
                "obv_rising":       signals["obv_rising"],
                "scan_type":        "divergence",
                "close_series":     close,
                "high_series":      high,
                "low_series":       low,
                "open_series":      data["Open"],
                "ma240_series":     ma240,
                "ma60_series":      ma60_s,
                "ma20_series":      ma20_s,
                "rsi_series":       rsi,
                "volume_series":    vol,
                "vol_ma_series":    vol_ma20,
            }
        except Exception:
            return None

    def analyze_all_stocks_divergence(self):
        """RSI(20) 강세 다이버전스 전용 스캔 - 전 종목"""
        results = []
        print("RSI(20) 다이버전스 스캔 중...")

        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(self.analyze_stock_divergence, sym): sym for sym in self.all_symbols}
            for future in as_completed(futures):
                sym = futures[future]
                try:
                    r = future.result()
                    if r:
                        results.append(r)
                        print(f"  [DIV] {sym} ({r['total_score']}pt)")
                except Exception:
                    pass
        return sorted(results, key=lambda x: x["total_score"], reverse=True)


if __name__ == "__main__":
    KoreanStockSurgeDetector().run_analysis()