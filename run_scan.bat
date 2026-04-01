@echo off
chcp 65001 > nul
cd /d "%~dp0"

:: .env 환경변수 로드
for /f "usebackq tokens=1,* delims==" %%A in (".env") do set %%A=%%B

python -X utf8 run_scan.py >> scan_log.txt 2>&1
