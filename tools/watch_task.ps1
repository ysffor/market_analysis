# 注册 Windows 计划任务：每个工作日 08:50 运行 tools/watch.py，生成 A 股信号日报（docs/watch/）。
# 电脑在计划时间没开机的，开机后补跑；需要联网；只在当前用户登录时运行，不需要保存密码。
# Register a Windows scheduled task that runs tools/watch.py on weekdays at 08:50 (catch-up run if missed).
# 用法 | usage: powershell -ExecutionPolicy Bypass -File tools\watch_task.ps1 [-Python <pythonw.exe>] [-At 08:50]
#   删除 | remove: Unregister-ScheduledTask -TaskName market_analysis_watch -Confirm:$false
param([string]$Python = "D:\python3.10.6\pythonw.exe", [string]$At = "08:50")
$root = Split-Path -Parent $PSScriptRoot
$act = New-ScheduledTaskAction -Execute $Python -Argument "-I `"$root\tools\watch.py`" `"$root`"" -WorkingDirectory $root
$trg = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At $At
$set = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "market_analysis_watch" -Description "A-share daily signal report (D:\download\usd-liquidity-dashboard\tools\watch.py)" -Action $act -Trigger $trg -Settings $set -Force | Out-Null
Get-ScheduledTask -TaskName "market_analysis_watch" | Get-ScheduledTaskInfo | Select-Object TaskName, NextRunTime
