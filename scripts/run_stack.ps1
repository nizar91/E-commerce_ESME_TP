Param(
    [switch]$Services,
    [switch]$Front
)

if (-not ($Services -or $Front)) {
    Write-Host "Usage:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/run_stack.ps1 -Services"
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/run_stack.ps1 -Front"
    Write-Host ""
    Write-Host "Use -Services to ouvrir les 4 microservices (user -> auth -> orders -> gateway)."
    Write-Host "Use -Front pour lancer l'UI Flask une fois les services dispo."
    exit 1
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonCmd = "python"

function Start-ServiceProcess {
    param(
        [string]$DisplayName,
        [string]$ScriptPath
    )

    $absolute = Join-Path $repoRoot $ScriptPath
    if (-not (Test-Path $absolute)) {
        Write-Host "Fichier introuvable : $absolute" -ForegroundColor Red
        exit 1
    }

    $workDir = Split-Path -Parent $absolute
    Write-Host "-> Demarrage $DisplayName"
    $windowTitle = "Microservice - $DisplayName"
    $psCommand = "& { `$host.UI.RawUI.WindowTitle = '$windowTitle'; Set-Location `"$workDir`"; $pythonCmd `"$absolute`" }"
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command", $psCommand
    )
}

function Start-FrontProcess {
    param(
        [string]$DisplayName,
        [string]$ScriptPath
    )

    $absolute = Join-Path $repoRoot $ScriptPath
    if (-not (Test-Path $absolute)) {
        Write-Host "Fichier introuvable : $absolute" -ForegroundColor Red
        exit 1
    }

    $workDir = Split-Path -Parent $absolute
    $windowTitle = "Front - $DisplayName"
    $psCommand = "& { `$host.UI.RawUI.WindowTitle = '$windowTitle'; Set-Location `"$workDir`"; $pythonCmd `"$absolute`" }"
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command", $psCommand
    )
}

if ($Services) {
    Start-ServiceProcess -DisplayName "User Service (5001)" -ScriptPath "services\user_service\app.py"
    Start-Sleep -Seconds 1
    Start-ServiceProcess -DisplayName "Auth Service (5002)" -ScriptPath "services\auth_service\app.py"
    Start-Sleep -Seconds 1
    Start-ServiceProcess -DisplayName "Orders Service (5003)" -ScriptPath "services\orders_service\app.py"
    Start-Sleep -Seconds 1
    Start-ServiceProcess -DisplayName "API Gateway (5000)" -ScriptPath "services\api_gateway\app.py"
    Write-Host "Tous les services ont ete lances dans des fenetres PowerShell separees."
}

if ($Front) {
    Start-FrontProcess -DisplayName "Flask UI (8000)" -ScriptPath "app.py"
    Write-Host "Front lance. Ouvrir http://127.0.0.1:8000"
}
