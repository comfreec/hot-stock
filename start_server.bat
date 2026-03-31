@echo off
cd /d C:\Users\dev\급등주

:: Streamlit 서버 시작
start "Streamlit" cmd /c "streamlit run app.py --server.port 8510 --server.enableCORS false --server.enableXsrfProtection false"

:: 5초 대기 후 cloudflared 터널 시작
timeout /t 5 /nobreak

start "Cloudflared" cmd /c "cloudflared tunnel --protocol http2 --url http://localhost:8510 > C:\Users\dev\급등주\tunnel.log 2>&1"

:: 스케줄러 시작 (장 마감 자동 스캔 + 텔레그램 알림)
start "Scheduler" cmd /c "python C:\Users\dev\급등주\scheduler.py > C:\Users\dev\급등주\scheduler.log 2>&1"

echo 서버 시작 완료
