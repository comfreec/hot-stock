"""
한국 주식 급등 예측 프로그램
Korean Stock Surge Detection Program
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class KoreanStockSurgeDetector:
    def __init__(self):
        """한국 주식 급등 탐지기 초기화"""
        self.kospi_symbols = [
            '005930.KS',  # 삼성전자
            '000660.KS',  # SK하이닉스
            '035420.KS',  # NAVER
            '051910.KS',  # LG화학
            '006400.KS',  # 삼성SDI
            '035720.KS',  # 카카오
            '207940.KS',  # 삼성바이오로직스
            '068270.KS',  # 셀트리온
            '323410.KS',  # 카카오뱅크
            '373220.KS',  # LG에너지솔루션
        ]
        
        self.kosdaq_symbols = [
            '091990.KQ',  # 셀트리온헬스케어
            '196170.KQ',  # 알테오젠
            '263750.KQ',  # 펄어비스
            '293490.KQ',  # 카카오게임즈
            '112040.KQ',  # 위메이드
            '357780.KQ',  # 솔브레인
            '086900.KQ',  # 메디톡스
            '214150.KQ',  # 클래시스
            '950140.KQ',  # 잉글우드랩
            '900140.KQ',  # 엔씨소프트
        ]
        
        self.all_symbols = self.kospi_symbols + self.kosdaq_symbols
        
    def get_stock_data(self, symbol, period='3mo'):
        """주식 데이터 가져오기"""
        try:
            stock = yf.Ticker(symbol)
            data = stock.history(period=period)
            return data
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return None
    
    def calculate_technical_indicators(self, data):
        """기술적 지표 계산"""
        if data is None or len(data) < 20:
            return None
            
        # RSI 계산
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        
        # 이동평균선
        data['MA5'] = data['Close'].rolling(window=5).mean()
        data['MA20'] = data['Close'].rolling(window=20).mean()
        data['MA60'] = data['Close'].rolling(window=60).mean()
        
        # 볼린저 밴드
        data['BB_Middle'] = data['Close'].rolling(window=20).mean()
        bb_std = data['Close'].rolling(window=20).std()
        data['BB_Upper'] = data['BB_Middle'] + (bb_std * 2)
        data['BB_Lower'] = data['BB_Middle'] - (bb_std * 2)
        
        # 거래량 이동평균
        data['Volume_MA'] = data['Volume'].rolling(window=20).mean()
        
        return data
    
    def detect_surge_signals(self, data, symbol):
        """급등 신호 탐지"""
        if data is None or len(data) < 20:
            return None
            
        latest = data.iloc[-1]
        prev_day = data.iloc[-2]
        
        signals = {
            'symbol': symbol,
            'current_price': latest['Close'],
            'price_change': ((latest['Close'] - prev_day['Close']) / prev_day['Close']) * 100,
            'volume_ratio': latest['Volume'] / latest['Volume_MA'] if latest['Volume_MA'] > 0 else 0,
            'rsi': latest['RSI'],
            'ma_signal': 0,
            'bb_signal': 0,
            'volume_signal': 0,
            'surge_score': 0
        }
        
        # 이동평균선 신호 (골든크로스)
        if latest['MA5'] > latest['MA20'] and prev_day['MA5'] <= prev_day['MA20']:
            signals['ma_signal'] = 2  # 강한 신호
        elif latest['MA5'] > latest['MA20']:
            signals['ma_signal'] = 1  # 약한 신호
            
        # 볼린저 밴드 신호
        if latest['Close'] > latest['BB_Upper']:
            signals['bb_signal'] = 2  # 상단 돌파
        elif latest['Close'] > latest['BB_Middle']:
            signals['bb_signal'] = 1  # 중간선 상회
            
        # 거래량 신호
        if signals['volume_ratio'] > 2:
            signals['volume_signal'] = 2  # 평균의 2배 이상
        elif signals['volume_ratio'] > 1.5:
            signals['volume_signal'] = 1  # 평균의 1.5배 이상
            
        # 종합 급등 점수 계산
        surge_score = 0
        
        # 가격 상승률 점수
        if signals['price_change'] > 5:
            surge_score += 3
        elif signals['price_change'] > 2:
            surge_score += 2
        elif signals['price_change'] > 0:
            surge_score += 1
            
        # RSI 점수 (과매수 구간 진입)
        if 50 < signals['rsi'] < 70:
            surge_score += 2
        elif signals['rsi'] > 70:
            surge_score += 1  # 과매수 위험
            
        # 기술적 지표 점수
        surge_score += signals['ma_signal']
        surge_score += signals['bb_signal']
        surge_score += signals['volume_signal']
        
        signals['surge_score'] = surge_score
        
        return signals
    
    def analyze_all_stocks(self):
        """모든 주식 분석"""
        results = []
        
        print("한국 주식 급등 분석 중...")
        print("=" * 50)
        
        for symbol in self.all_symbols:
            print(f"분석 중: {symbol}")
            
            # 데이터 가져오기
            data = self.get_stock_data(symbol)
            if data is None:
                continue
                
            # 기술적 지표 계산
            data = self.calculate_technical_indicators(data)
            if data is None:
                continue
                
            # 급등 신호 탐지
            signals = self.detect_surge_signals(data, symbol)
            if signals:
                results.append(signals)
        
        return results
    
    def rank_surge_candidates(self, results):
        """급등 후보 순위 매기기"""
        if not results:
            return []
            
        # 급등 점수로 정렬
        sorted_results = sorted(results, key=lambda x: x['surge_score'], reverse=True)
        
        return sorted_results
    
    def display_results(self, ranked_results):
        """결과 출력"""
        print("\n" + "=" * 80)
        print("🚀 한국 주식 급등 후보 분석 결과")
        print("=" * 80)
        
        if not ranked_results:
            print("분석 가능한 데이터가 없습니다.")
            return
            
        print(f"{'순위':<4} {'종목코드':<12} {'현재가':<10} {'등락률':<8} {'거래량비':<8} {'RSI':<6} {'급등점수':<6}")
        print("-" * 80)
        
        for i, result in enumerate(ranked_results[:10], 1):
            print(f"{i:<4} {result['symbol']:<12} {result['current_price']:<10.0f} "
                  f"{result['price_change']:<8.2f}% {result['volume_ratio']:<8.1f} "
                  f"{result['rsi']:<6.1f} {result['surge_score']:<6}")
        
        # 상위 3개 종목 상세 분석
        print("\n" + "=" * 80)
        print("🔥 TOP 3 급등 후보 상세 분석")
        print("=" * 80)
        
        for i, result in enumerate(ranked_results[:3], 1):
            print(f"\n{i}. {result['symbol']}")
            print(f"   현재가: {result['current_price']:.0f}원")
            print(f"   등락률: {result['price_change']:.2f}%")
            print(f"   거래량 비율: {result['volume_ratio']:.1f}배")
            print(f"   RSI: {result['rsi']:.1f}")
            print(f"   이동평균 신호: {result['ma_signal']}")
            print(f"   볼린저밴드 신호: {result['bb_signal']}")
            print(f"   거래량 신호: {result['volume_signal']}")
            print(f"   급등 점수: {result['surge_score']}")
    
    def run_analysis(self):
        """전체 분석 실행"""
        print("🇰🇷 한국 주식 급등 예측 프로그램 시작")
        print(f"분석 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 모든 주식 분석
        results = self.analyze_all_stocks()
        
        # 순위 매기기
        ranked_results = self.rank_surge_candidates(results)
        
        # 결과 출력
        self.display_results(ranked_results)
        
        return ranked_results

if __name__ == "__main__":
    detector = KoreanStockSurgeDetector()
    results = detector.run_analysis()