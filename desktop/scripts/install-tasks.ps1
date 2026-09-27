param(
    [Parameter(Mandatory = $true)][string]$ServerExe,
    [Parameter(Mandatory = $true)][string]$ConfigDirectory,
    [Parameter(Mandatory = $true)][ValidateSet('server', 'client')][string]$Mode
)
$ErrorActionPreference = 'Stop'
$taskExecutable = (Resolve-Path -LiteralPath $ServerExe).Path
$taskConfig = (Resolve-Path -LiteralPath $ConfigDirectory).Path
$taskUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 0)
$principal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Limited

# Restrict credentials/recovery key to this Windows user, SYSTEM and administrators.
$acl = Get-Acl -LiteralPath $taskConfig
$acl.SetAccessRuleProtection($true, $false)
foreach ($identity in @([System.Security.Principal.WindowsIdentity]::GetCurrent().User, (New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')), (New-Object System.Security.Principal.SecurityIdentifier('S-1-5-32-544')))) {
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $taskConfig -AclObject $acl

if ($Mode -eq 'server') {
    $dataDirectory = Join-Path $taskConfig 'data'
    $action = New-ScheduledTaskAction -Execute $taskExecutable -Argument ('--data-dir "' + $dataDirectory + '"') -WorkingDirectory (Split-Path -Parent $taskExecutable)
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $taskUser
    Register-ScheduledTask -TaskName 'Marassim-Serveur' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Serveur central Marassim et sauvegarde quotidienne a 19h.' -Force | Out-Null
} else {
    $replicaConfiguration = Join-Path $taskConfig 'replica.json'
    $onlineConfiguration = Join-Path $taskConfig 'cloud.json'
    if (-not (Test-Path -LiteralPath $replicaConfiguration) -and -not (Test-Path -LiteralPath $onlineConfiguration)) { throw "Activez d'abord les copies ou le relais en ligne sur ce poste dans Marassim." }
    if (Test-Path -LiteralPath $replicaConfiguration) {
    $action = New-ScheduledTaskAction -Execute $taskExecutable -Argument ('--replica "' + $replicaConfiguration + '"') -WorkingDirectory (Split-Path -Parent $taskExecutable)
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
    Register-ScheduledTask -TaskName 'Marassim-CopieLocale' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Copie et verification des sauvegardes Marassim toutes les 5 minutes.' -Force | Out-Null
    Start-ScheduledTask -TaskName 'Marassim-CopieLocale'
    }
    if (Test-Path -LiteralPath $onlineConfiguration) {
        $action = New-ScheduledTaskAction -Execute $taskExecutable -Argument ('--online-sync "' + $onlineConfiguration + '"') -WorkingDirectory (Split-Path -Parent $taskExecutable)
        $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 20)
        $cloudSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 18)
        Register-ScheduledTask -TaskName 'Marassim-RelaisEnLigne' -Action $action -Trigger $trigger -Settings $cloudSettings -Principal $principal -Description 'Copie chiffree vers Vercel toutes les 20 minutes depuis ce poste connecte a Internet.' -Force | Out-Null
        Start-ScheduledTask -TaskName 'Marassim-RelaisEnLigne'
    }
}
