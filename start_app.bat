@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo [%date% %time%] Streamlit 앱 시작...
streamlit run app.py --server.port 8510 --server.headless true
