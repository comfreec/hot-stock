$workDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── 1. Streamlit 앱 부팅 시 자동 시작 ──────────────────────────
$action1  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$(Join-Path $workDir 'start_app.bat')`""
$trigger1 = New-ScheduledTaskTrigger -AtLogOn
$settings1 = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 24) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "HotStock_App" -Action $action1 -Trigger $trigger1 -Settings $settings1 -RunLevel Highest -Force
Write-Host "1. 앱 자동시작 등록 완료 (로그인 시 자동 실행)"

# ── 2. 매일 KST 09:10 성과 업데이트 ────────────────────────────
$action2  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$(Join-Path $workDir 'run_performance.bat')`""
$trigger2 = New-ScheduledTaskTrigger -Daily -At "09:10"
$settings2 = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -StartWhenAvailable
Register-ScheduledTask -TaskName "HotStock_Performance" -Action $action2 -Trigger $trigger2 -Settings $settings2 -RunLevel Highest -Force
Write-Host "2. 성과 업데이트 등록 완료 (매일 KST 09:10)"

# ── 3. 매일 KST 15:40 스캔 + 급등 알림 ─────────────────────────
$action3  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$(Join-Path $workDir 'run_scan.bat')`""
$trigger3 = New-ScheduledTaskTrigger -Daily -At "15:40"
$settings3 = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 60) -StartWhenAvailable
Register-ScheduledTask -TaskName "HotStock_DailyScan" -Action $action3 -Trigger $trigger3 -Settings $settings3 -RunLevel Highest -Force
Write-Host "3. 스캔 알림 등록 완료 (매일 KST 15:40)"

Write-Host ""
Write-Host "=== 등록된 작업 목록 ==="
Get-ScheduledTask | Where-Object { $_.TaskName -like "HotStock_*" } | Select-Object TaskName, State | Format-Table -AutoSize
