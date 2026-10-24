# AItoB WebUI Asset Deployment Script for Windows / WSL / Docker
param (
    [string]$Engine = "auto"
)

$repoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$deployPy = "$repoRoot\tools\deploy_assets.py"

Write-Host "Deploying AItoB WebUI assets via byte-preserving Python..."
python "$deployPy"
Write-Host "✅ AItoB Get Started assets successfully applied to webui container!"
