@echo off
cd /d C:\Users\dev\급등주

:: Streamlit 서버 시작
start "Streamlit" cmd /c "streamlit run app.py --server.port 8510 --server.enableCORS false --server.enableXsrfProtection false"

:: 5초 대기 후 cloudflared 터널 시작
timeout /t 5 /nobreak

start "Cloudflared" cmd /c "C:\cloudflared.exe tunnel --url http://localhost:8510 > C:\Users\dev\급등주\tunnel.log 2>&1"

echo 서버 시작 완료
