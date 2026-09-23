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
Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow

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
Write-Host "[2/5] Checking Docker..." -ForegroundColor Yellow

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
Write-Host "[3/5] Checking Vagrant..." -ForegroundColor Yellow

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
Write-Host "[4/5] Checking WSL2..." -ForegroundColor Yellow

$wslInstalled = Get-Command wsl -ErrorAction SilentlyContinue

if (-not $wslInstalled) {
    Write-Host "WSL is not installed. Installing..."
    wsl --install
} else {
    Write-Host "WSL is already installed."
}

# ------------------------------------------
# Python virtual environment
# ------------------------------------------
Write-Host ""
Write-Host "[5/5] Setting up Python virtual environment..." -ForegroundColor Yellow

if (-not (Test-Path ".venv")) {
    Write-Host "Creating .venv..."
    python -m venv .venv
} else {
    Write-Host ".venv already exists."
}

# ------------------------------------------
# Install Python dependencies
# ------------------------------------------
Write-Host ""
Write-Host "Installing Python dependencies..."
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip

if (Test-Path "requirements.txt") {
    & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
} else {
    Write-Host "WARNING: requirements.txt not found." -ForegroundColor Yellow
}

# ------------------------------------------
# Verification
# ------------------------------------------
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
Write-Host "[1/6] Python..." -ForegroundColor Yellow

if (Get-Command python -ErrorAction SilentlyContinue) {
    python --version
} else {
    Write-Host "ERROR: Python not found." -ForegroundColor Red
    $VerificationFailed = $true
}

# Docker
Write-Host ""
Write-Host "[2/6] Docker..." -ForegroundColor Yellow

if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker --version
    docker compose version
} else {
    Write-Host "ERROR: Docker not found." -ForegroundColor Red
    $VerificationFailed = $true
}

# Vagrant
Write-Host ""
Write-Host "[3/6] Vagrant..." -ForegroundColor Yellow

if (Get-Command vagrant -ErrorAction SilentlyContinue) {
    vagrant --version
} else {
    Write-Host "ERROR: Vagrant not found." -ForegroundColor Red
    $VerificationFailed = $true
}

# WSL2
Write-Host ""
Write-Host "[4/6] WSL2..." -ForegroundColor Yellow

if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
    wsl --version
} else {
    Write-Host "ERROR: WSL2 not found." -ForegroundColor Red
    $VerificationFailed = $true
}

# Python virtual environment
Write-Host ""
Write-Host "[5/6] Python virtual environment..." -ForegroundColor Yellow

$VenvPython = ".\.venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
    & $VenvPython --version
} else {
    Write-Host "ERROR: .venv not found." -ForegroundColor Red
    $VerificationFailed = $true
}

# Python packages
Write-Host ""
Write-Host "[6/6] Python packages..." -ForegroundColor Yellow

if (Test-Path $VenvPython) {

    & $VenvPython -m pip show ansible

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Ansible is not installed in .venv." -ForegroundColor Red
        $VerificationFailed = $true
    }

    & $VenvPython -m pip show docker

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker Python package is not installed in .venv." -ForegroundColor Red
        $VerificationFailed = $true
    }

} else {
    Write-Host "ERROR: Cannot verify Python packages." -ForegroundColor Red
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

"=========================================="
Write-Host "Done!"
Write-Host "=========================================="