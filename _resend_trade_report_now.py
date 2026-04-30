"""자동매매 일일 리포트 강제 재전송"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== 자동매매 리포트 재전송 ===", flush=True)
from auto_trader import send_trade_report
send_trade_report()
print("=== 완료 ===", flush=True)
