"""
주식 급등 예측 웹 애플리케이션
Stock Surge Prediction Web Application
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import yfinance as yf
from stock_surge_detector import KoreanStockSurgeDetector

# TensorFlow 관련 import를 조건부로 처리
try:
    from advanced_stock_predictor import AdvancedStockPredictor
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False

# 페이지 설정
st.set_page_config(
    page_title="한국 주식 급등 예측 시스템",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 제목
st.title("🚀 한국 주식 급등 예측 시스템")
st.markdown("---")

# 사이드바
st.sidebar.header("분석 옵션")

# TensorFlow 사용 가능 여부에 따라 옵션 조정
if TENSORFLOW_AVAILABLE:
    analysis_options = ["기본 급등 탐지", "AI 딥러닝 예측", "개별 종목 분석"]
else:
    analysis_options = ["기본 급등 탐지", "개별 종목 분석"]
    st.sidebar.warning("⚠️ TensorFlow가 설치되지 않아 AI 분석 기능을 사용할 수 없습니다.")

analysis_type = st.sidebar.selectbox(
    "분석 유형 선택",
    analysis_options
)

# 캐시된 데이터 로딩 함수
@st.cache_data(ttl=300)  # 5분 캐시
def load_basic_analysis():
    detector = KoreanStockSurgeDetector()
    return detector.analyze_all_stocks()

@st.cache_data(ttl=1800)  # 30분 캐시
def load_advanced_analysis():
    if not TENSORFLOW_AVAILABLE:
        return None
    predictor = AdvancedStockPredictor()
    return predictor.analyze_surge_probability()

@st.cache_data(ttl=300)
def get_stock_chart_data(symbol, period="3mo"):
    try:
        stock = yf.Ticker(symbol)
        data = stock.history(period=period)
        return data
    except:
        return None

def create_stock_chart(data, title):
    """주식 차트 생성"""
    fig = go.Figure()
    
    # 캔들스틱 차트
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name="주가"
    ))
    
    # 거래량 차트 (보조)
    fig.add_trace(go.Bar(
        x=data.index,
        y=data['Volume'],
        name="거래량",
        yaxis="y2",
        opacity=0.3
    ))
    
    fig.update_layout(
        title=title,
        yaxis_title="주가 (원)",
        yaxis2=dict(
            title="거래량",
            overlaying="y",
            side="right"
        ),
        xaxis_rangeslider_visible=False,
        height=500
    )
    
    return fig

# 메인 컨텐츠
if analysis_type == "기본 급등 탐지":
    st.header("📊 기본 급등 탐지 분석")
    
    if st.button("분석 시작", type="primary"):
        with st.spinner("주식 데이터 분석 중..."):
            results = load_basic_analysis()
            
            if results:
                # 결과를 DataFrame으로 변환
                df = pd.DataFrame(results)
                df = df.sort_values('surge_score', ascending=False)
                
                # 상위 10개 종목 표시
                st.subheader("🔥 급등 후보 TOP 10")
                
                # 데이터 포맷팅
                display_df = df.head(10).copy()
                display_df['현재가'] = display_df['current_price'].apply(lambda x: f"{x:,.0f}원")
                display_df['등락률'] = display_df['price_change'].apply(lambda x: f"{x:.2f}%")
                display_df['거래량비'] = display_df['volume_ratio'].apply(lambda x: f"{x:.1f}배")
                display_df['RSI'] = display_df['rsi'].apply(lambda x: f"{x:.1f}")
                
                st.dataframe(
                    display_df[['symbol', '현재가', '등락률', '거래량비', 'RSI', 'surge_score']],
                    column_config={
                        'symbol': '종목코드',
                        'surge_score': '급등점수'
                    },
                    use_container_width=True
                )
                
                # 차트 표시
                col1, col2 = st.columns(2)
                
                with col1:
                    # 급등 점수 차트
                    fig_score = px.bar(
                        df.head(10), 
                        x='symbol', 
                        y='surge_score',
                        title="급등 점수 비교",
                        color='surge_score',
                        color_continuous_scale='Reds'
                    )
                    st.plotly_chart(fig_score, use_container_width=True)
                
                with col2:
                    # 등락률 vs 거래량 산점도
                    fig_scatter = px.scatter(
                        df.head(10),
                        x='price_change',
                        y='volume_ratio',
                        size='surge_score',
                        hover_data=['symbol'],
                        title="등락률 vs 거래량 비율",
                        labels={'price_change': '등락률 (%)', 'volume_ratio': '거래량 비율'}
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)
                
                # 상위 3개 종목 상세 정보
                st.subheader("🎯 TOP 3 상세 분석")
                
                for i, (_, row) in enumerate(df.head(3).iterrows()):
                    with st.expander(f"{i+1}. {row['symbol']} - 급등점수: {row['surge_score']}"):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("현재가", f"{row['current_price']:,.0f}원")
                            st.metric("등락률", f"{row['price_change']:.2f}%")
                        
                        with col2:
                            st.metric("거래량 비율", f"{row['volume_ratio']:.1f}배")
                            st.metric("RSI", f"{row['rsi']:.1f}")
                        
                        with col3:
                            st.metric("이동평균 신호", row['ma_signal'])
                            st.metric("볼린저밴드 신호", row['bb_signal'])
                        
                        # 개별 차트
                        chart_data = get_stock_chart_data(row['symbol'])
                        if chart_data is not None:
                            fig = create_stock_chart(chart_data, f"{row['symbol']} 주가 차트")
                            st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("분석 데이터를 가져올 수 없습니다.")

elif analysis_type == "AI 딥러닝 예측" and TENSORFLOW_AVAILABLE:
    st.header("🤖 AI 딥러닝 급등 예측")
    st.info("LSTM 신경망을 사용한 고급 예측 분석입니다. 분석에 시간이 소요될 수 있습니다.")
    
    if st.button("AI 분석 시작", type="primary"):
        with st.spinner("AI 모델 훈련 및 예측 중... (약 2-3분 소요)"):
            try:
                results = load_advanced_analysis()
                
                if results:
                    # 결과를 DataFrame으로 변환
                    df = pd.DataFrame(results)
                    
                    st.subheader("🔥 AI 예측 급등 후보")
                    
                    # 데이터 포맷팅
                    display_df = df.copy()
                    display_df['현재가'] = display_df['current_price'].apply(lambda x: f"{x:,.0f}원")
                    display_df['예측가'] = display_df['predicted_price'].apply(lambda x: f"{x:,.0f}원")
                    display_df['예상등락률'] = display_df['predicted_change'].apply(lambda x: f"{x:.2f}%")
                    display_df['급등확률'] = display_df['surge_probability'].apply(lambda x: f"{x:.1f}%")
                    display_df['모델정확도'] = display_df['model_accuracy'].apply(lambda x: f"{x:.1f}%")
                    
                    st.dataframe(
                        display_df[['name', '현재가', '예측가', '예상등락률', '급등확률', '모델정확도']],
                        column_config={
                            'name': '종목명'
                        },
                        use_container_width=True
                    )
                    
                    # 시각화
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # 급등 확률 차트
                        fig_prob = px.bar(
                            df, 
                            x='name', 
                            y='surge_probability',
                            title="AI 급등 확률 예측",
                            color='surge_probability',
                            color_continuous_scale='Viridis'
                        )
                        fig_prob.update_xaxis(tickangle=45)
                        st.plotly_chart(fig_prob, use_container_width=True)
                    
                    with col2:
                        # 예상 등락률 차트
                        fig_change = px.bar(
                            df,
                            x='name',
                            y='predicted_change',
                            title="예상 등락률",
                            color='predicted_change',
                            color_continuous_scale='RdYlGn'
                        )
                        fig_change.update_xaxis(tickangle=45)
                        st.plotly_chart(fig_change, use_container_width=True)
                    
                    # 상위 3개 종목 상세
                    st.subheader("🎯 AI 추천 TOP 3")
                    
                    for i, row in df.head(3).iterrows():
                        with st.expander(f"{row['name']} - 급등확률: {row['surge_probability']:.1f}%"):
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.metric("현재가", f"{row['current_price']:,.0f}원")
                            with col2:
                                st.metric("예측가", f"{row['predicted_price']:,.0f}원")
                            with col3:
                                st.metric("예상 등락률", f"{row['predicted_change']:.2f}%")
                            with col4:
                                st.metric("급등 확률", f"{row['surge_probability']:.1f}%")
                            
                            # 투자 추천
                            if row['surge_probability'] > 70:
                                st.success("🚀 강력 추천: 높은 급등 가능성")
                            elif row['surge_probability'] > 60:
                                st.info("📈 추천: 상승 가능성")
                            elif row['surge_probability'] > 50:
                                st.warning("⚠️ 관심: 신중한 접근 필요")
                            else:
                                st.error("❌ 비추천: 하락 위험")
                
                else:
                    st.error("AI 분석 결과를 가져올 수 없습니다.")
                    
            except Exception as e:
                st.error(f"AI 분석 중 오류가 발생했습니다: {str(e)}")

else:  # 개별 종목 분석
    st.header("📈 개별 종목 분석")
    
    # 종목 선택
    korean_stocks = {
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
    
    selected_stock = st.selectbox("분석할 종목을 선택하세요", list(korean_stocks.keys()))
    symbol = korean_stocks[selected_stock]
    
    period = st.selectbox("분석 기간", ["1mo", "3mo", "6mo", "1y", "2y"])
    
    if st.button("종목 분석", type="primary"):
        with st.spinner(f"{selected_stock} 분석 중..."):
            data = get_stock_chart_data(symbol, period)
            
            if data is not None:
                # 기본 정보
                current_price = data['Close'].iloc[-1]
                prev_price = data['Close'].iloc[-2]
                price_change = ((current_price - prev_price) / prev_price) * 100
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("현재가", f"{current_price:,.0f}원")
                with col2:
                    st.metric("전일 대비", f"{price_change:.2f}%", delta=f"{current_price - prev_price:,.0f}원")
                with col3:
                    st.metric("거래량", f"{data['Volume'].iloc[-1]:,.0f}")
                with col4:
                    st.metric("시가총액", "계산 중...")
                
                # 차트
                fig = create_stock_chart(data, f"{selected_stock} ({symbol}) 주가 차트")
                st.plotly_chart(fig, use_container_width=True)
                
                # 기술적 분석
                st.subheader("📊 기술적 분석")
                
                # 이동평균선
                data['MA5'] = data['Close'].rolling(window=5).mean()
                data['MA20'] = data['Close'].rolling(window=20).mean()
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # 이동평균 분석
                    ma5_signal = "상승" if data['Close'].iloc[-1] > data['MA5'].iloc[-1] else "하락"
                    ma20_signal = "상승" if data['Close'].iloc[-1] > data['MA20'].iloc[-1] else "하락"
                    
                    st.write("**이동평균선 분석**")
                    st.write(f"• 5일 이평선: {ma5_signal}")
                    st.write(f"• 20일 이평선: {ma20_signal}")
                
                with col2:
                    # RSI 계산
                    delta = data['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    current_rsi = rsi.iloc[-1]
                    
                    st.write("**RSI 분석**")
                    st.write(f"• 현재 RSI: {current_rsi:.1f}")
                    if current_rsi > 70:
                        st.write("• 상태: 과매수")
                    elif current_rsi < 30:
                        st.write("• 상태: 과매도")
                    else:
                        st.write("• 상태: 중립")
                
                # 거래량 분석
                st.subheader("📊 거래량 분석")
                volume_ma = data['Volume'].rolling(window=20).mean()
                volume_ratio = data['Volume'].iloc[-1] / volume_ma.iloc[-1]
                
                st.write(f"• 평균 거래량 대비: {volume_ratio:.1f}배")
                if volume_ratio > 2:
                    st.success("🔥 거래량 급증!")
                elif volume_ratio > 1.5:
                    st.info("📈 거래량 증가")
                else:
                    st.write("📊 평균 수준")
            
            else:
                st.error("종목 데이터를 가져올 수 없습니다.")

# 푸터
st.markdown("---")
st.markdown("""
**⚠️ 투자 유의사항**
- 이 분석은 참고용이며, 실제 투자 결과를 보장하지 않습니다.
- 주식 투자는 원금 손실 위험이 있으니 신중하게 결정하시기 바랍니다.
- 다양한 정보를 종합하여 투자 결정을 내리시기 바랍니다.
""")

st.markdown("Made with ❤️ by Korean Stock Analyzer")