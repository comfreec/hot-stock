import os, sys
os.chdir('/app')
sys.path.insert(0, '/app')
os.environ['DB_PATH'] = '/data/scan_cache.db'
from auto_trader import send_trade_report
send_trade_report()
print('완료')
