<#
.SYNOPSIS
    1-Command Runner for Ephemeral Machines Platform (Lab Hacker) Demo.
.DESCRIPTION
    Starts Postgres and Traefik in Docker, runs database migrations and seed data,
    and starts both the FastAPI API and the Scheduler daemon.
#>

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Ephemeral Machines Platform - 1-Command Demo Runner" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# Determine absolute path to Python
$apiPython = Join-Path $ProjectDir "api\.venv\Scripts\python.exe"
if (-not (Test-Path $apiPython)) {
    Write-Host "  [ERROR] Virtual environment not found at $apiPython." -ForegroundColor Red
    Write-Host "  Please run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}

# 1. Verify Docker
Write-Host "[1/5] Checking Docker daemon..." -ForegroundColor Yellow
try {
    docker ps 2>&1 | Out-Null
    Write-Host "  Docker is running." -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# 2. Start PostgreSQL and Traefik
Write-Host ""
Write-Host "[2/5] Starting Docker services (Postgres & Traefik)..." -ForegroundColor Yellow
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] Failed to start Docker Compose services." -ForegroundColor Red
    exit 1
}

# Wait for Postgres to be healthy
Write-Host "  Waiting for PostgreSQL to be ready..." -ForegroundColor Gray
$elapsed = 0
$maxWait = 30
$healthy = $false
while ($elapsed -lt $maxWait -and -not $healthy) {
    Start-Sleep -Seconds 2
    $elapsed += 2
    $status = docker inspect --format='{{.State.Health.Status}}' lab-postgres 2>$null
    if ($status -eq "healthy") {
        $healthy = $true
    }
}
if (-not $healthy) {
    Write-Host "  [WARNING] PostgreSQL healthcheck timeout; continuing..." -ForegroundColor Yellow
} else {
    Write-Host "  PostgreSQL is healthy." -ForegroundColor Green
}

# 3. Apply Migrations & Seed
Write-Host ""
Write-Host "[3/5] Applying DB migrations and seed data..." -ForegroundColor Yellow

Push-Location (Join-Path $ProjectDir "api")
try {
    & $apiPython -m alembic upgrade head
    & $apiPython seed.py
} finally {
    Pop-Location
}
Write-Host "  Database initialized and seeded." -ForegroundColor Green

# 4. Run Automated Quick Tests
Write-Host ""
Write-Host "[4/5] Running automated smoke tests..." -ForegroundColor Yellow
& $apiPython -m pytest api/tests/ -q --tb=short
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Smoke tests passed successfully." -ForegroundColor Green
} else {
    Write-Host "  [WARNING] Some smoke tests failed." -ForegroundColor Yellow
}

# 5. Launch API and Scheduler
Write-Host ""
Write-Host "[5/5] Launching API and Scheduler..." -ForegroundColor Yellow

$schedPython = Join-Path $ProjectDir "scheduler\.venv\Scripts\python.exe"

$apiProc = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "cd '$ProjectDir\api'; & '$apiPython' -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" -PassThru
$schedProc = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "cd '$ProjectDir\scheduler'; & '$schedPython' -m app.main" -PassThru

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Demo is UP and RUNNING!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  REST API Docs (Swagger):  http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  Traefik Dashboard:        http://localhost:8080/dashboard/" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Default Demo Credentials:" -ForegroundColor White
Write-Host "    Admin: admin@lab.local / admin12345" -ForegroundColor Gray
Write-Host "    User:  user@lab.local  / user12345" -ForegroundColor Gray
Write-Host ""
Write-Host "  To test via CLI:" -ForegroundColor White
Write-Host "    .\api\.venv\Scripts\python.exe cli/labctl.py login user@lab.local user12345" -ForegroundColor Gray
Write-Host "    .\api\.venv\Scripts\python.exe cli/labctl.py machines" -ForegroundColor Gray
Write-Host "    .\api\.venv\Scripts\python.exe cli/labctl.py reserve --machine kali --duration 15" -ForegroundColor Gray
Write-Host ""
Write-Host "  To stop the background services, close the spawned PowerShell windows" -ForegroundColor Yellow
Write-Host "  or run: docker compose down" -ForegroundColor Yellow
Write-Host ""
