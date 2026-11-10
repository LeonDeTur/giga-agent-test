# Локальные службы для giga-agent, каждая — отдельный процесс через uvx:
#   dpo_files  (8101) — MCP filesystem, stdio -> streamable HTTP через mcp-proxy
#   web_fetch  (8102) — MCP fetch,      stdio -> streamable HTTP через mcp-proxy
#   infinity   (8103) — эмбеддинги ai-forever/ru-en-RoSBERTa на CPU
#   litellm    (8104) — OpenAI-совместимый прокси перед infinity
#                       (декодирует номера токенов от giga-agent в текст)
# MCP-адреса для .giga_agent/mcp.json: http://127.0.0.1:<port>/mcp
# Эмбеддинги в giga-agent: подключение openai, Base URL http://127.0.0.1:8104/v1,
#   API Token = LITELLM_MASTER_KEY из .env, модель ru-en-rosberta.
# Использование:
#   powershell -ExecutionPolicy Bypass -File mcp-servers.ps1 start|stop|status
param([ValidateSet('start', 'stop', 'status')][string]$Action = 'start')

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$runDir = Join-Path $root '.giga_agent\mcp-run'
$dataDir = Join-Path $root 'dpo-kit\data'
$proxy = 'mcp-proxy@0.15.0'

function McpProxyArgs($port, [string[]]$cmd) {
    return @($proxy, '--host', '127.0.0.1', '--port', $port, '--') + $cmd
}

$servers = [ordered]@{
    dpo_files = @{
        Port = 8101
        Args = McpProxyArgs 8101 @('cmd', '/c', 'npx', '-y', '@modelcontextprotocol/server-filesystem@2.2.0', $dataDir)
    }
    web_fetch = @{
        Port = 8102
        Args = McpProxyArgs 8102 @('uvx', 'mcp-server-fetch@2026.11.4')
    }
    infinity  = @{
        Port = 8103
        Args = @('--python', '3.11', '--from', 'infinity-emb[all]', 'infinity_emb', 'v2',
            '--model-id', 'ai-forever/ru-en-RoSBERTa', '--device', 'cpu',
            '--host', '127.0.0.1', '--port', '8103', '--no-bettertransformer')
    }
    litellm   = @{
        Port      = 8104
        NeedsKey  = $true
        Args      = @('--python', '3.12', '--from', 'litellm[proxy]', 'litellm',
            '--config', (Join-Path $root 'litellm.yaml'), '--host', '127.0.0.1', '--port', '8104')
    }
}

New-Item -ItemType Directory -Force $runDir | Out-Null

function Get-ServerProcess($name) {
    $pidFile = Join-Path $runDir "$name.pid"
    if (-not (Test-Path $pidFile)) { return $null }
    $procId = [int](Get-Content $pidFile)
    return Get-Process -Id $procId -ErrorAction SilentlyContinue
}

function Test-Port($port) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', $port); $c.Close(); return $true
    } catch { return $false }
}

function Import-LiteLLMKey {
    $envFile = Join-Path $root '.env'
    if (-not (Test-Path $envFile)) { throw '.env not found: LITELLM_MASTER_KEY is required for litellm' }
    $line = Select-String -Path $envFile -Pattern '^LITELLM_MASTER_KEY=' | Select-Object -First 1
    if (-not $line) { throw 'LITELLM_MASTER_KEY is missing in .env' }
    $env:LITELLM_MASTER_KEY = $line.Line.Substring('LITELLM_MASTER_KEY='.Length).Trim()
}

switch ($Action) {
    'start' {
        $env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONUTF8 = '1'
        foreach ($name in $servers.Keys) {
            $s = $servers[$name]
            if (Get-ServerProcess $name) { Write-Host "$name already running"; continue }
            if (Test-Port $s.Port) { throw "Port $($s.Port) is busy, $name not started" }
            if ($s.NeedsKey) { Import-LiteLLMKey }
            $p = Start-Process -FilePath 'uvx' -ArgumentList $s.Args -WindowStyle Hidden -PassThru `
                -RedirectStandardOutput (Join-Path $runDir "$name.out.log") `
                -RedirectStandardError (Join-Path $runDir "$name.err.log")
            Set-Content -Path (Join-Path $runDir "$name.pid") -Value $p.Id
            Write-Host "$name -> 127.0.0.1:$($s.Port) (pid $($p.Id))"
        }
        Write-Host 'infinity loads the model for ~1 min (first run downloads it).'
    }
    'stop' {
        foreach ($name in $servers.Keys) {
            $p = Get-ServerProcess $name
            if ($p) { & taskkill.exe /PID $p.Id /T /F | Out-Null; Write-Host "$name stopped" }
            Remove-Item (Join-Path $runDir "$name.pid") -ErrorAction SilentlyContinue
        }
    }
    'status' {
        foreach ($name in $servers.Keys) {
            $s = $servers[$name]
            $state = if (Get-ServerProcess $name) { 'running' } else { 'stopped' }
            $port = if (Test-Port $s.Port) { 'listening' } else { 'closed' }
            Write-Host ("{0,-10} {1,-8} port {2} {3}" -f $name, $state, $s.Port, $port)
        }
    }
}
