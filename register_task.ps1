$workDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── 1. Streamlit 앱 로그인 시 자동 시작 ─────────────────────────
$action1  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$(Join-Path $workDir 'start_app.bat')`""
$trigger1 = New-ScheduledTaskTrigger -AtLogOn
$settings1 = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 24) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "HotStock_App" -Action $action1 -Trigger $trigger1 -Settings $settings1 -RunLevel Highest -Force
Write-Host "1. 앱 자동시작 등록 완료 (로그인 시 자동 실행)"

# ── 2. scheduler.py 로그인 시 자동 시작 (15:40 스캔 + 09:10 성과 모두 관리) ──
$pythonPath = (Get-Command python).Source
$action2  = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$(Join-Path $workDir 'scheduler.py')`"" -WorkingDirectory $workDir
$trigger2 = New-ScheduledTaskTrigger -AtLogOn
$settings2 = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 24) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "HotStock_Scheduler" -Action $action2 -Trigger $trigger2 -Settings $settings2 -RunLevel Highest -Force
Write-Host "2. 스케줄러 자동시작 등록 완료 (로그인 시 자동 실행 - 15:40 스캔 / 09:10 성과)"

# ── DailyScan / Performance 는 scheduler.py가 대신하므로 비활성화 ──
Disable-ScheduledTask -TaskName "HotStock_DailyScan"   -ErrorAction SilentlyContinue
Disable-ScheduledTask -TaskName "HotStock_Performance" -ErrorAction SilentlyContinue
Write-Host "3. HotStock_DailyScan / HotStock_Performance 비활성화 완료"

Write-Host ""
Write-Host "=== 등록된 작업 목록 ==="
Get-ScheduledTask | Where-Object { $_.TaskName -like "HotStock_*" } | Select-Object TaskName, State | Format-Table -AutoSize
