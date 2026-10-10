$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Project Environment Installer - Windows" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir

# ------------------------------------------
# Check Administrator
# ------------------------------------------
$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($currentUser)

if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Please run PowerShell as Administrator." -ForegroundColor Red
    exit 1
}

# ------------------------------------------
# Check Winget
# ------------------------------------------
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: winget is not available." -ForegroundColor Red
    Write-Host "Please install/update App Installer from Microsoft Store."
    exit 1
}

# ------------------------------------------
# Python
# ------------------------------------------
Write-Host "[1/4] Checking Python..." -ForegroundColor Yellow

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python is not installed. Installing..."
    winget install `
        --id Python.Python.3.12 `
        --exact `
        --accept-source-agreements `
        --accept-package-agreements `
    --silent
} else {
    Write-Host "Python is already installed."
}

# ------------------------------------------
# Docker Desktop
# ------------------------------------------
Write-Host ""
Write-Host "[2/4] Checking Docker..." -ForegroundColor Yellow

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker is not installed. Installing Docker Desktop..."
    winget install `
        --id Docker.DockerDesktop `
        --exact `
        --accept-source-agreements `
        --accept-package-agreements `
        --silent
} else {
    Write-Host "Docker is already installed."
}

# ------------------------------------------
# Vagrant
# ------------------------------------------
Write-Host ""
Write-Host "[3/4] Checking Vagrant..." -ForegroundColor Yellow

if (-not (Get-Command vagrant -ErrorAction SilentlyContinue)) {
    Write-Host "Vagrant is not installed. Installing..."
    winget install `
        --id Hashicorp.Vagrant `
        --exact `
        --accept-source-agreements `
        --accept-package-agreements `
        --silent
} else {
    Write-Host "Vagrant is already installed."
}

# ------------------------------------------
# WSL2
# ------------------------------------------
Write-Host ""
Write-Host "[4/4] Checking WSL2..." -ForegroundColor Yellow

$wslInstalled = Get-Command wsl -ErrorAction SilentlyContinue

if (-not $wslInstalled) {
    Write-Host "WSL is not installed. Installing..."
    wsl --install
} else {
    Write-Host "WSL is already installed."
}

# ------------------------------------------
# Verification
# ------------------------------------------
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " Verification" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

$VerificationFailed = $false

# Python
Write-Host ""
Write-Host "[1/4] Python..." -ForegroundColor Yellow

if (Get-Command python -ErrorAction SilentlyContinue) {
    python --version
} else {
    Write-Host "ERROR: Python not found." -ForegroundColor Red
    $VerificationFailed = $true
}

# Docker
Write-Host ""
Write-Host "[2/4] Docker..." -ForegroundColor Yellow

if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker --version
    docker compose version
} else {
    Write-Host "ERROR: Docker not found." -ForegroundColor Red
    $VerificationFailed = $true
}

# Vagrant
Write-Host ""
Write-Host "[3/4] Vagrant..." -ForegroundColor Yellow

if (Get-Command vagrant -ErrorAction SilentlyContinue) {
    vagrant --version
} else {
    Write-Host "ERROR: Vagrant not found." -ForegroundColor Red
    $VerificationFailed = $true
}

# WSL2
Write-Host ""
Write-Host "[4/4] WSL2..." -ForegroundColor Yellow

if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
    wsl --version
} else {
    Write-Host "ERROR: WSL2 not found." -ForegroundColor Red
    $VerificationFailed = $true
}

# ------------------------------------------
# Final result
# ------------------------------------------
Write-Host ""

if ($VerificationFailed) {
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host " Installation completed with errors!" -ForegroundColor Red
    Write-Host "==========================================" -ForegroundColor Red
    exit 1
} else {
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host " Installation and verification completed!" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
}
Write-Host "=========================================="
Write-Host "Done!"
Write-Host "=========================================="