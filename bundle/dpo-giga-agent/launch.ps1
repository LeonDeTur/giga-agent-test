param([ValidateSet('start','stop','status','reset')][string]$Command)
$ErrorActionPreference='Stop'
try {
    Set-Location -LiteralPath $PSScriptRoot
    . "$PSScriptRoot\bootstrap.ps1"
    Initialize-Tools
    Invoke-Course $Command
    if ($Command -eq 'start') { Invoke-Course 'open-ui' }
} catch { Write-Host "Ошибка: $($_.Exception.Message)"; exit 1 }
