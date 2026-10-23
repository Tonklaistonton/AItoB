param (
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "status", "logs", "build")]
    [string]$Action = "status",

    [Parameter(Position = 1)]
    [string]$Service = ""
)

$wslc = "C:\Program Files\WSL\wslc.exe"
if (-not (Test-Path $wslc)) {
    Write-Error "wslc.exe not found at $wslc"
    exit 1
}

$repoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$networkName = "aitob-net"
$services = @("gateway", "gmail", "assistant", "webui", "line-bot")

# Helper to load .env variables
function Get-EnvMap {
    $map = @{}
    $envFile = "$repoRoot\.env"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            $line = $_.Trim()
            if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
                $idx = $line.IndexOf("=")
                $k = $line.Substring(0, $idx).Trim()
                $v = $line.Substring($idx + 1).Trim()
                $map[$k] = $v
            }
        }
    }
    return $map
}

function Ensure-Network {
    $networks = & $wslc network list
    if ($networks -notmatch $networkName) {
        Write-Host "Creating network $networkName..."
        & $wslc network create $networkName | Out-Null
    }
}

function Build-Images {
    Write-Host "Building container images..."
    & $wslc build -t aitob-gateway -f "$repoRoot\project\gateway\Dockerfile" "$repoRoot\project\gateway"
    & $wslc build -t aitob-gmail -f "$repoRoot\project\gmail-lab\Dockerfile" "$repoRoot\project\gmail-lab"
    & $wslc build -t aitob-assistant -f "$repoRoot\project\mcp-lab\Dockerfile" "$repoRoot\project\mcp-lab"
    & $wslc build -t aitob-line-bot -f "$repoRoot\project\line-bot\Dockerfile" "$repoRoot\project\line-bot"
}

function Stop-Containers {
    Write-Host "Stopping containers..."
    foreach ($svc in $services) {
        & $wslc stop $svc 2>$null | Out-Null
        & $wslc rm $svc 2>$null | Out-Null
    }
}

function Start-Containers {
    Ensure-Network
    $cfg = Get-EnvMap

    $volumes = & $wslc volume list
    if ($volumes -notmatch "webui-data") {
        & $wslc volume create webui-data | Out-Null
    }
    if ($volumes -notmatch "line-data") {
        & $wslc volume create line-data | Out-Null
    }

    Write-Host "Starting gateway..."
    & $wslc run -d `
        --name gateway `
        --network $networkName `
        -p 127.0.0.1:8000:8000 `
        -v "$repoRoot\project\gateway\credentials\keys.json:/gateway/credentials/keys.json:ro" `
        aitob-gateway | Out-Null

    Write-Host "Starting gmail..."
    & $wslc run -d `
        --name gmail `
        --network $networkName `
        -p 127.0.0.1:8001:8001 `
        -v "$repoRoot\project\gateway:/gateway" `
        -e GATEWAY_URL="http://gateway:8000" `
        aitob-gmail | Out-Null

    Write-Host "Starting assistant..."
    & $wslc run -d `
        --name assistant `
        --network $networkName `
        -p 127.0.0.1:8002:8002 `
        -v "$repoRoot\project\gateway:/gateway" `
        -e GATEWAY_URL="http://gateway:8000" `
        -e GMAIL_BACKEND_URL="http://gmail:8001" `
        aitob-assistant | Out-Null

    $webuiSecret = if ($cfg["WEBUI_SECRET_KEY"]) { $cfg["WEBUI_SECRET_KEY"] } else { "aitob-default-secret-key-32bytes" }
    Write-Host "Starting webui..."
    & $wslc run -d `
        --name webui `
        --network $networkName `
        -p 127.0.0.1:3000:8080 `
        -v "webui-data:/app/backend/data" `
        -e WEBUI_AUTH="false" `
        -e WEBUI_SECRET_KEY="$webuiSecret" `
        ghcr.io/open-webui/open-webui@sha256:4860ba005ae8f19f08d1e12b0868855b7b339ea0dad9927f196820fc0de04575 | Out-Null

    $lineSecret = if ($cfg["LINE_CHANNEL_SECRET"]) { $cfg["LINE_CHANNEL_SECRET"] } else { "" }
    $lineToken = if ($cfg["LINE_CHANNEL_ACCESS_TOKEN"]) { $cfg["LINE_CHANNEL_ACCESS_TOKEN"] } else { "" }
    $llmUrl = if ($cfg["LLM_API_BASE_URL"]) { $cfg["LLM_API_BASE_URL"] } else { "" }
    $llmKey = if ($cfg["LLM_API_KEY"]) { $cfg["LLM_API_KEY"] } else { "" }
    $llmModel = if ($cfg["LLM_MODEL"]) { $cfg["LLM_MODEL"] } else { "ag/gemini-3.8-flash-high" }

    Write-Host "Starting line-bot..."
    & $wslc run -d `
        --name line-bot `
        --network $networkName `
        -p 127.0.0.1:8003:8003 `
        -v "line-data:/home/aitob/data" `
        -e GATEWAY_URL="http://gateway:8000" `
        -e LINE_CHANNEL_SECRET="$lineSecret" `
        -e LINE_CHANNEL_ACCESS_TOKEN="$lineToken" `
        -e LLM_API_BASE_URL="$llmUrl" `
        -e LLM_API_KEY="$llmKey" `
        -e LLM_MODEL="$llmModel" `
        aitob-line-bot | Out-Null

    Write-Host "`nStack started successfully."
    Write-Host "Open WebUI: http://localhost:3000"
    Write-Host "LINE Webhook: http://localhost:8003/webhook"
}

switch ($Action) {
    "build" {
        Build-Images
    }
    "start" {
        Start-Containers
        & $wslc list
    }
    "stop" {
        Stop-Containers
        Write-Host "All services stopped."
    }
    "restart" {
        Stop-Containers
        Start-Containers
        & $wslc list
    }
    "status" {
        & $wslc list
    }
    "logs" {
        if ($Service) {
            & $wslc logs $Service --tail 50
        } else {
            foreach ($svc in $services) {
                Write-Host "--- $svc logs ---"
                & $wslc logs $svc --tail 10
            }
        }
    }
}
