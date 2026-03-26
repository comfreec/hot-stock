import streamlit as st

st.title("테스트")

try:
    import pandas as pd
    st.success("pandas OK")
except Exception as e:
    st.error(f"pandas: {e}")

try:
    import numpy as np
    st.success("numpy OK")
except Exception as e:
    st.error(f"numpy: {e}")

try:
    import plotly.graph_objects as go
    st.success("plotly OK")
except Exception as e:
    st.error(f"plotly: {e}")

try:
    import yfinance as yf
    st.success("yfinance OK")
except Exception as e:
    st.error(f"yfinance: {e}")

try:
    from stock_surge_detector import KoreanStockSurgeDetector
    st.success("stock_surge_detector OK")
except Exception as e:
    st.error(f"stock_surge_detector: {e}")

st.write("모든 import 완료")
