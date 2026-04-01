@echo off
chcp 65001 > nul
cd /d "%~dp0"

:: .env 환경변수 로드
for /f "usebackq tokens=1,* delims==" %%A in (".env") do set %%A=%%B

echo [%date% %time%] Streamlit 앱 시작...
streamlit run app.py --server.port 8510 --server.headless true
