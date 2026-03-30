"""
로컬 성과 업데이트 스크립트
Windows 작업 스케줄러로 매일 KST 09:10에 실행
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_alert import send_performance_update, send_weekly_summary

print("성과 추적 업데이트 시작...")
send_performance_update()
send_weekly_summary()
print("완료")
