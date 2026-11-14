param([switch]$Yes, [switch]$Shortcuts)
$ErrorActionPreference='Stop'
try {
    . "$PSScriptRoot\bootstrap.ps1"
    if ($PSScriptRoot.Length -gt 80) { throw 'Путь к папке слишком длинный для Windows. Переместите комплект в C:\DPO. Кириллица и пробелы допустимы.' }
    if ((Get-Item $PSScriptRoot).PSDrive.Free -lt 5GB) { throw 'Для установки требуется около 5 ГБ свободного места.' }
    Set-Location -LiteralPath $PSScriptRoot
    New-Item -ItemType Directory '.giga_agent\run' -Force | Out-Null
    Start-Transcript -Path '.giga_agent\run\install.log' -Append | Out-Null
    Write-Host 'Подготовка инструментов. Первый запуск скачивает около 2 ГБ, 10–20 минут.'
    Initialize-Tools
    Write-Host 'Проверка ключа GigaChat.'
    while ($true) {
        & "$PSScriptRoot\tools\uv\uv.exe" run dpo.py installer-key
        if ($LASTEXITCODE -eq 0) { break }
        if ($Yes) { throw 'Задайте корректный ключ через DPO_GIGACHAT_CREDENTIALS.' }
        Write-Host 'developers.sber.ru → GigaChat API → Ключ авторизации. Scope: GIGACHAT_API_PERS.'
        $secure=Read-Host 'Вставьте ключ' -AsSecureString
        $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try { $env:DPO_GIGACHAT_CREDENTIALS=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    }
    Remove-Item Env:DPO_GIGACHAT_CREDENTIALS -ErrorAction SilentlyContinue
    Write-Host 'Установка Python, зависимостей, запуск пяти служб, настройка трёх проектов и проверка.'
    Invoke-Course 'up'
    Invoke-Course 'open-ui'
    $create=$Shortcuts.IsPresent
    if (!$Yes -and !$create) { $create=(Read-Host 'Создать ярлыки на рабочем столе и в меню Пуск? [Д/н]') -notmatch '^[нn]' }
    if ($create) { New-CourseShortcuts @([Environment]::GetFolderPath('Desktop'),(Join-Path ([Environment]::GetFolderPath('Programs')) 'ДПО агенты')) }
} catch { Write-Host "Ошибка: $($_.Exception.Message)"; exit 1 }
finally { try { Stop-Transcript | Out-Null } catch {} }
