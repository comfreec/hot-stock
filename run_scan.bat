@echo off
chcp 65001 > nul
cd /d "%~dp0"
python -X utf8 run_scan.py >> scan_log.txt 2>&1
