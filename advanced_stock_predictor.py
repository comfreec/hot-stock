"""
고급 주식 급등 예측 시스템 (LSTM 딥러닝 모델 포함)
Advanced Stock Surge Prediction System with LSTM Deep Learning
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class AdvancedStockPredictor:
    def __init__(self):
        """고급 주식 예측기 초기화"""
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.model = None
        self.sequence_length = 60  # 60일 데이터로 예측
        
        # 한국 주요 종목들
        self.korean_stocks = {
            '삼성전자': '005930.KS',
            'SK하이닉스': '000660.KS',
            'NAVER': '035420.KS',
            'LG화학': '051910.KS',
            '카카오': '035720.KS',
            '삼성바이오로직스': '207940.KS',
            '셀트리온': '068270.KS',
            'LG에너지솔루션': '373220.KS',
            '카카오뱅크': '323410.KS',
            '삼성SDI': '006400.KS'
        }
    
    def get_extended_stock_data(self, symbol, period='2y'):
        """확장된 주식 데이터 가져오기"""
        try:
            stock = yf.Ticker(symbol)
            data = stock.history(period=period)
            
            if len(data) < 100:
                print(f"Warning: {symbol}의 데이터가 부족합니다 ({len(data)}일)")
                return None
                
            return data
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return None
    
    def create_advanced_features(self, data):
        """고급 기술적 지표 생성"""
        if data is None or len(data) < 60:
            return None
        
        # 기본 가격 정보
        data['Price_Change'] = data['Close'].pct_change()
        data['High_Low_Ratio'] = data['High'] / data['Low']
        data['Volume_Price_Trend'] = data['Volume'] * data['Price_Change']
        
        # 이동평균선들
        for period in [5, 10, 20, 50]:
            data[f'MA_{period}'] = data['Close'].rolling(window=period).mean()
            data[f'MA_{period}_ratio'] = data['Close'] / data[f'MA_{period}']
        
        # RSI
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = data['Close'].ewm(span=12).mean()
        exp2 = data['Close'].ewm(span=26).mean()
        data['MACD'] = exp1 - exp2
        data['MACD_Signal'] = data['MACD'].ewm(span=9).mean()
        data['MACD_Histogram'] = data['MACD'] - data['MACD_Signal']
        
        # 볼린저 밴드
        data['BB_Middle'] = data['Close'].rolling(window=20).mean()
        bb_std = data['Close'].rolling(window=20).std()
        data['BB_Upper'] = data['BB_Middle'] + (bb_std * 2)
        data['BB_Lower'] = data['BB_Middle'] - (bb_std * 2)
        data['BB_Width'] = (data['BB_Upper'] - data['BB_Lower']) / data['BB_Middle']
        data['BB_Position'] = (data['Close'] - data['BB_Lower']) / (data['BB_Upper'] - data['BB_Lower'])
        
        # 스토캐스틱
        low_min = data['Low'].rolling(window=14).min()
        high_max = data['High'].rolling(window=14).max()
        data['Stochastic_K'] = 100 * (data['Close'] - low_min) / (high_max - low_min)
        data['Stochastic_D'] = data['Stochastic_K'].rolling(window=3).mean()
        
        # 거래량 지표
        data['Volume_MA'] = data['Volume'].rolling(window=20).mean()
        data['Volume_Ratio'] = data['Volume'] / data['Volume_MA']
        
        # 변동성 지표
        data['Volatility'] = data['Close'].rolling(window=20).std()
        data['ATR'] = self.calculate_atr(data)
        
        return data
    
    def calculate_atr(self, data, period=14):
        """Average True Range 계산"""
        high_low = data['High'] - data['Low']
        high_close = np.abs(data['High'] - data['Close'].shift())
        low_close = np.abs(data['Low'] - data['Close'].shift())
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = true_range.rolling(window=period).mean()
        
        return atr
    
    def prepare_lstm_data(self, data, target_column='Close'):
        """LSTM 모델용 데이터 준비"""
        # 필요한 특성들 선택
        feature_columns = [
            'Close', 'Volume', 'RSI', 'MACD', 'MACD_Signal', 'MACD_Histogram',
            'BB_Position', 'BB_Width', 'Stochastic_K', 'Stochastic_D',
            'Volume_Ratio', 'Volatility', 'ATR', 'MA_5_ratio', 'MA_20_ratio'
        ]
        
        # 결측값 제거
        data = data.dropna()
        
        if len(data) < self.sequence_length + 30:
            print(f"데이터가 부족합니다. 필요: {self.sequence_length + 30}, 현재: {len(data)}")
            return None, None, None, None
        
        # 특성 데이터 준비
        features = data[feature_columns].values
        target = data[target_column].values
        
        # 정규화
        features_scaled = self.scaler.fit_transform(features)
        target_scaler = MinMaxScaler(feature_range=(0, 1))
        target_scaled = target_scaler.fit_transform(target.reshape(-1, 1)).flatten()
        
        # 시퀀스 데이터 생성
        X, y = [], []
        for i in range(self.sequence_length, len(features_scaled)):
            X.append(features_scaled[i-self.sequence_length:i])
            y.append(target_scaled[i])
        
        X, y = np.array(X), np.array(y)
        
        # 훈련/테스트 분할
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        return X_train, X_test, y_train, y_test, target_scaler
    
    def build_lstm_model(self, input_shape):
        """LSTM 모델 구축"""
        model = Sequential([
            LSTM(50, return_sequences=True, input_shape=input_shape),
            Dropout(0.2),
            LSTM(50, return_sequences=True),
            Dropout(0.2),
            LSTM(50),
            Dropout(0.2),
            Dense(25),
            Dense(1)
        ])
        
        model.compile(optimizer='adam', loss='mean_squared_error', metrics=['mae'])
        return model
    
    def train_model(self, symbol, epochs=50):
        """모델 훈련"""
        print(f"\n{symbol} 모델 훈련 시작...")
        
        # 데이터 가져오기
        data = self.get_extended_stock_data(symbol, period='2y')
        if data is None:
            return None
        
        # 특성 생성
        data = self.create_advanced_features(data)
        if data is None:
            return None
        
        # LSTM 데이터 준비
        X_train, X_test, y_train, y_test, target_scaler = self.prepare_lstm_data(data)
        if X_train is None:
            return None
        
        # 모델 구축
        self.model = self.build_lstm_model((X_train.shape[1], X_train.shape[2]))
        
        # 모델 훈련
        history = self.model.fit(
            X_train, y_train,
            batch_size=32,
            epochs=epochs,
            validation_data=(X_test, y_test),
            verbose=0
        )
        
        # 예측 및 평가
        train_pred = self.model.predict(X_train)
        test_pred = self.model.predict(X_test)
        
        # 역정규화
        train_pred = target_scaler.inverse_transform(train_pred)
        test_pred = target_scaler.inverse_transform(test_pred)
        y_train_actual = target_scaler.inverse_transform(y_train.reshape(-1, 1))
        y_test_actual = target_scaler.inverse_transform(y_test.reshape(-1, 1))
        
        # 성능 평가
        train_rmse = np.sqrt(mean_squared_error(y_train_actual, train_pred))
        test_rmse = np.sqrt(mean_squared_error(y_test_actual, test_pred))
        
        print(f"훈련 RMSE: {train_rmse:.2f}")
        print(f"테스트 RMSE: {test_rmse:.2f}")
        
        return {
            'model': self.model,
            'target_scaler': target_scaler,
            'train_rmse': train_rmse,
            'test_rmse': test_rmse,
            'history': history,
            'data': data
        }
    
    def predict_future_price(self, symbol, days=5):
        """미래 주가 예측"""
        print(f"\n{symbol} {days}일 후 주가 예측 중...")
        
        # 모델 훈련
        result = self.train_model(symbol)
        if result is None:
            return None
        
        model = result['model']
        target_scaler = result['target_scaler']
        data = result['data']
        
        # 최근 데이터로 예측
        feature_columns = [
            'Close', 'Volume', 'RSI', 'MACD', 'MACD_Signal', 'MACD_Histogram',
            'BB_Position', 'BB_Width', 'Stochastic_K', 'Stochastic_D',
            'Volume_Ratio', 'Volatility', 'ATR', 'MA_5_ratio', 'MA_20_ratio'
        ]
        
        recent_data = data[feature_columns].dropna().tail(self.sequence_length)
        recent_scaled = self.scaler.transform(recent_data.values)
        
        # 예측
        prediction_input = recent_scaled.reshape(1, self.sequence_length, len(feature_columns))
        prediction_scaled = model.predict(prediction_input)
        prediction = target_scaler.inverse_transform(prediction_scaled)[0][0]
        
        current_price = data['Close'].iloc[-1]
        predicted_change = ((prediction - current_price) / current_price) * 100
        
        return {
            'current_price': current_price,
            'predicted_price': prediction,
            'predicted_change': predicted_change,
            'model_performance': {
                'train_rmse': result['train_rmse'],
                'test_rmse': result['test_rmse']
            }
        }
    
    def analyze_surge_probability(self):
        """급등 확률 분석"""
        print("🚀 한국 주식 급등 확률 분석 시작")
        print("=" * 60)
        
        results = []
        
        for name, symbol in self.korean_stocks.items():
            try:
                prediction = self.predict_future_price(symbol)
                if prediction:
                    surge_probability = max(0, min(100, prediction['predicted_change'] * 2 + 50))
                    
                    results.append({
                        'name': name,
                        'symbol': symbol,
                        'current_price': prediction['current_price'],
                        'predicted_price': prediction['predicted_price'],
                        'predicted_change': prediction['predicted_change'],
                        'surge_probability': surge_probability,
                        'model_accuracy': 100 - prediction['model_performance']['test_rmse']
                    })
                    
            except Exception as e:
                print(f"{name} 분석 중 오류: {e}")
                continue
        
        # 급등 확률로 정렬
        results.sort(key=lambda x: x['surge_probability'], reverse=True)
        
        return results
    
    def display_surge_analysis(self, results):
        """급등 분석 결과 출력"""
        print("\n" + "=" * 100)
        print("🔥 AI 딥러닝 기반 주식 급등 예측 결과")
        print("=" * 100)
        
        if not results:
            print("분석 결과가 없습니다.")
            return
        
        print(f"{'순위':<4} {'종목명':<15} {'현재가':<10} {'예측가':<10} {'예상등락률':<10} {'급등확률':<8} {'모델정확도':<10}")
        print("-" * 100)
        
        for i, result in enumerate(results, 1):
            print(f"{i:<4} {result['name']:<15} {result['current_price']:<10.0f} "
                  f"{result['predicted_price']:<10.0f} {result['predicted_change']:<10.2f}% "
                  f"{result['surge_probability']:<8.1f}% {result['model_accuracy']:<10.1f}%")
        
        # 상위 3개 종목 상세 분석
        print("\n" + "=" * 100)
        print("🎯 TOP 3 급등 예상 종목 상세 분석")
        print("=" * 100)
        
        for i, result in enumerate(results[:3], 1):
            print(f"\n{i}. {result['name']} ({result['symbol']})")
            print(f"   현재 주가: {result['current_price']:.0f}원")
            print(f"   예측 주가: {result['predicted_price']:.0f}원")
            print(f"   예상 등락률: {result['predicted_change']:.2f}%")
            print(f"   급등 확률: {result['surge_probability']:.1f}%")
            print(f"   AI 모델 정확도: {result['model_accuracy']:.1f}%")
            
            if result['predicted_change'] > 5:
                print("   🚀 강력한 상승 신호!")
            elif result['predicted_change'] > 2:
                print("   📈 상승 신호")
            elif result['predicted_change'] > 0:
                print("   ↗️ 약한 상승 신호")
            else:
                print("   ⚠️ 하락 위험")
    
    def run_advanced_analysis(self):
        """고급 분석 실행"""
        print("🤖 AI 딥러닝 기반 한국 주식 급등 예측 시스템")
        print(f"분석 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("LSTM 신경망을 사용한 고급 예측 분석을 시작합니다...")
        
        # 급등 확률 분석
        results = self.analyze_surge_probability()
        
        # 결과 출력
        self.display_surge_analysis(results)
        
        print("\n" + "=" * 100)
        print("⚠️  투자 유의사항")
        print("=" * 100)
        print("• 이 분석은 AI 모델 기반 예측이며, 실제 투자 결과를 보장하지 않습니다.")
        print("• 주식 투자는 원금 손실 위험이 있으니 신중하게 결정하시기 바랍니다.")
        print("• 다양한 정보를 종합하여 투자 결정을 내리시기 바랍니다.")
        
        return results

if __name__ == "__main__":
    predictor = AdvancedStockPredictor()
    results = predictor.run_advanced_analysis()