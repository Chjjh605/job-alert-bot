# 윈도우 작업 스케줄러에 "취업공고알림" 작업을 등록한다 (매일 09:00, 18:00)
# 실행: PowerShell 에서  .\scripts\register_task.ps1
# 해제: Unregister-ScheduledTask -TaskName "취업공고알림"

$dir = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path (Split-Path (Get-Command python).Source) "pythonw.exe"   # 창 없이 실행

$action = New-ScheduledTaskAction -Execute $pythonw `
    -Argument "-m jobalert --log-file state\run.log" -WorkingDirectory $dir
$triggers = @(
    (New-ScheduledTaskTrigger -Daily -At 09:00),
    (New-ScheduledTaskTrigger -Daily -At 18:00)
)
# StartWhenAvailable: PC 가 꺼져 있어 놓친 실행은 켜지는 대로 바로 실행
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "취업공고알림" -Action $action -Trigger $triggers -Settings $settings `
    -Description "청년일경험 IT 인턴형 새 공고를 Discord로 알림 (job-alert-bot)" -Force
