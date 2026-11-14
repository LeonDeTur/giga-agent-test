function Assert-CourseEnvironment {
    if ($PSVersionTable.PSVersion -lt [version]'5.1') {
        throw 'Требуется Windows 10 или 11 с Windows PowerShell 5.1 или новее.'
    }
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or [Environment]::OSVersion.Version.Major -lt 10) {
        throw 'Требуется Windows 10 или 11.'
    }
    if (![Environment]::Is64BitOperatingSystem) {
        throw 'Требуется 64-разрядная Windows.'
    }
}
Assert-CourseEnvironment
function Get-CourseSHA256([string]$Path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $stream = [IO.File]::OpenRead($Path)
        try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '') }
        finally { $stream.Dispose() }
    } finally { $sha.Dispose() }
}
# Pinned versions; hashes are fetched from the official release host.
$UvVersion = '0.9.5'
$NodeVersion = '22.14.0'
function Initialize-Tools {
    $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
    [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
    $env:UV_CACHE_DIR="$PSScriptRoot\.cache\uv"
    $env:UV_PYTHON_INSTALL_DIR="$PSScriptRoot\.cache\python"
    $env:UV_TOOL_DIR="$PSScriptRoot\.cache\uv-tools"
    $env:HF_HOME="$PSScriptRoot\.cache\huggingface"
    $env:npm_config_cache="$PSScriptRoot\.cache\npm"
    if (Test-Path "$PSScriptRoot\OFFLINE") { $env:UV_OFFLINE='1'; $env:HF_HUB_OFFLINE='1'; $env:npm_config_offline='true' }
    $env:PATH="$PSScriptRoot\tools\uv;$PSScriptRoot\tools\node;"+$env:PATH
    foreach ($kind in @('uv','node')) {
        $exe = if ($kind -eq 'uv') {'uv.exe'} else {'node.exe'}
        if (Test-Path "$PSScriptRoot\tools\$kind\$exe") { continue }
        if ($env:UV_OFFLINE -eq '1') { throw 'В автономном архиве отсутствуют инструменты.' }
        $stage = Join-Path $PSScriptRoot ('.downloads\'+[guid]::NewGuid())
        try {
            New-Item -ItemType Directory -Path $stage -Force | Out-Null
            if ($kind -eq 'uv') {
                $asset='uv-x86_64-pc-windows-msvc.zip'
                $url="https://github.com/astral-sh/uv/releases/download/$UvVersion/$asset"
                $checks="$url.sha256"
            } else {
                $asset="node-v$NodeVersion-win-x64.zip"
                $url="https://nodejs.org/dist/v$NodeVersion/$asset"
                $checks="https://nodejs.org/dist/v$NodeVersion/SHASUMS256.txt"
            }
            Write-Host "Загрузка $kind; версия $(if ($kind -eq 'uv') {$UvVersion} else {$NodeVersion})"
            [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
            $savedProgressPreference = $ProgressPreference
            try {
                $ProgressPreference = 'SilentlyContinue'
                Invoke-WebRequest -UseBasicParsing $url -OutFile "$stage\$asset"
                Invoke-WebRequest -UseBasicParsing $checks -OutFile "$stage\checks.txt"
            } catch {
                $cause = $_.Exception
                $networkFailure = $false
                while ($null -ne $cause) {
                    if ($cause -is [Net.WebException] -or $cause.GetType().FullName -in @('System.Net.Http.HttpRequestException', 'Microsoft.PowerShell.Commands.HttpResponseException')) {
                        $networkFailure = $true
                        break
                    }
                    $cause = $cause.InnerException
                }
                if ($networkFailure) { throw "Ошибка загрузки $kind. Проверьте интернет. $($_.Exception.Message)" }
                throw
            } finally { $ProgressPreference = $savedProgressPreference }
            $lines=Get-Content "$stage\checks.txt"
            $line= if ($kind -eq 'uv') {$lines | Select-Object -First 1} else {$lines | Where-Object { $_ -match ('\s+\*?'+[regex]::Escape($asset)+'$') } | Select-Object -First 1}
            if (!$line -or $line -notmatch '^([0-9a-fA-F]{64})(\s|$)') { throw 'Некорректный официальный файл SHA256.' }
            $expected=$Matches[1]
            $actual=Get-CourseSHA256 "$stage\$asset"
            if ($actual -ne $expected) { throw 'SHA256 не совпадает. Установка прервана.' }
            Write-Host "SHA256 проверен: $actual"
            Expand-Archive -LiteralPath "$stage\$asset" -DestinationPath "$stage\extract"
            $source= if ($kind -eq 'uv') {"$stage\extract"} else {"$stage\extract\node-v$NodeVersion-win-x64"}
            New-Item -ItemType Directory "$PSScriptRoot\tools\$kind" -Force | Out-Null
            Copy-Item "$source\*" "$PSScriptRoot\tools\$kind" -Recurse -Force
        } catch { throw "Не удалось подготовить $($kind): $($_.Exception.Message)" }
        finally {
            Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
            $downloads = Join-Path $PSScriptRoot '.downloads'
            if ((Test-Path -LiteralPath $downloads) -and !(Get-ChildItem -LiteralPath $downloads -Force | Select-Object -First 1)) {
                Remove-Item -LiteralPath $downloads -Force -ErrorAction SilentlyContinue
            }
        }
    }
}
function Invoke-Course([string]$Command) {
    & "$PSScriptRoot\tools\uv\uv.exe" run --project "$PSScriptRoot" "$PSScriptRoot\dpo.py" $Command
    if ($LASTEXITCODE -ne 0) { throw "Команда $Command завершилась с ошибкой ($LASTEXITCODE)." }
}
function New-CourseShortcuts([string[]]$Folders) {
    $shell=New-Object -ComObject WScript.Shell
    foreach ($folder in $Folders) {
        New-Item -ItemType Directory $folder -Force | Out-Null
        foreach ($entry in @(@('запустить','start.cmd'),@('остановить','stop.cmd'))) {
            $link=$shell.CreateShortcut((Join-Path $folder "ДПО агенты — $($entry[0]).lnk"))
            $link.TargetPath=Join-Path $PSScriptRoot $entry[1]
            $link.WorkingDirectory=$PSScriptRoot
            $link.Save()
        }
    }
}
