# Registra node_agent.py como tarea de inicio de sesion en Windows
$pythonPath  = "C:\Python313\python.exe"
$scriptPath  = "C:\Users\APRENDIZ.ITAAPR10712143\Desktop\CLI y API KEY\OLLAMA API AI\app\node_agent.py"
$taskName    = "LanLLM_NodeAgent"

$accion  = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$config  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -Hidden

Register-ScheduledTask -TaskName $taskName -Action $accion -Trigger $trigger -Settings $config -Force

Write-Host "Tarea '$taskName' registrada. Se iniciara automaticamente al iniciar sesion."
