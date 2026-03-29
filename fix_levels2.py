content = open('app.py', encoding='utf-8').read()

# 1) 급등예고 탭 차트
content = content.replace(
    """                        st.plotly_chart(
                            make_candle(cd, f"{r['name']} ({r['symbol']}) — 2년 차트", cross_date=cross_date),
                            config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key=f"candle_{r['symbol']}")""",
    """                        _c1 = make_candle(cd, f"{r['name']} ({r['symbol']})", cross_date=cross_date)
                        st.plotly_chart(_c1, config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key=f"candle_{r['symbol']}")
                        show_price_levels(_c1)"""
)

# 2) 개별종목 분석 (조건 충족)
content = content.replace(
    """                st.plotly_chart(
                    make_candle(data, f"{name} ({symbol}) — {period} 차트", cross_date=cross_date),
                    config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True)""",
    """                _c2 = make_candle(data, f"{name} ({symbol})", cross_date=cross_date)
                st.plotly_chart(_c2, config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True)
                show_price_levels(_c2)"""
)

# 3) 개별종목 분석 (조건 미충족)
content = content.replace(
    """                st.plotly_chart(make_candle(data, f"{name} ({symbol}) — {period} 차트"),
                                config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key="chart_candle_no_cond")""",
    """                _c3 = make_candle(data, f"{name} ({symbol})")
                st.plotly_chart(_c3, config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key="chart_candle_no_cond")
                show_price_levels(_c3)"""
)

# 4) 우량주 RSI 탭
content = content.replace(
    """                    st.plotly_chart(
                        make_candle(r["df"], f"{r['name']} ({r['symbol']})"),
                        config={"scrollZoom": False, "displayModeBar": False},
                        use_container_width=True, key=f"candle_quality_{r['symbol']}")""",
    """                    _c4 = make_candle(r["df"], f"{r['name']} ({r['symbol']})")
                    st.plotly_chart(_c4, config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key=f"candle_quality_{r['symbol']}")
                    show_price_levels(_c4)"""
)

# 5) 최적 급등 타이밍 탭
content = content.replace(
    """                    st.plotly_chart(
                        make_candle(cd, f"{r['name']} ({r['symbol']})", show_levels=True),
                        config={"scrollZoom":False,"displayModeBar":False},
                        use_container_width=True, key=f"candle_timing_{r['symbol']}")""",
    """                    _c5 = make_candle(cd, f"{r['name']} ({r['symbol']})", show_levels=True)
                    st.plotly_chart(_c5, config={"scrollZoom":False,"displayModeBar":False}, use_container_width=True, key=f"candle_timing_{r['symbol']}")
                    show_price_levels(_c5)"""
)

open('app.py', 'w', encoding='utf-8').write(content)
print('done')
