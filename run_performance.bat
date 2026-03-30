@echo off
chcp 65001 > nul
cd /d "%~dp0"
python -X utf8 run_performance.py >> performance_log.txt 2>&1
