<#
.SYNOPSIS
    Configure the Ephemeral Machines Platform project.
.DESCRIPTION
    Creates the venvs (api/, scheduler/), installs dependencies,
    generates SSL certificates, starts Docker Compose, applies migrations.
    Does NOT require Admin rights (except for /etc/hosts - done by another script).
#>

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir

Write-Host ""
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  Lab Hacker - Project Setup" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------
# 1. Check Docker
# ---------------------------------------------------------
Write-Host "> [1/7] Checking Docker..." -ForegroundColor Yellow
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker not found. Run install.ps1 first" -ForegroundColor Red
    exit 1
}
docker --version | ForEach-Object { Write-Host "  $_" }
docker compose version | ForEach-Object { Write-Host "  $_" }

# Verify that Docker is actually running
$dockerOk = $false
try {
    docker ps 2>&1 | Out-Null
    $dockerOk = $true
} catch {
    $dockerOk = $false
}
if (-not $dockerOk) {
    Write-Host "Docker Desktop is not running." -ForegroundColor Red
    Write-Host "Open Docker Desktop and wait for the icon to turn green." -ForegroundColor Yellow
    exit 1
}
Write-Host "Docker is operational" -ForegroundColor Green

# ---------------------------------------------------------
# 2. Create .env from .env.example
# ---------------------------------------------------------
Write-Host ""
Write-Host "> [2/7] Configuring .env..." -ForegroundColor Yellow

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host ".env created from .env.example" -ForegroundColor Green
    } else {
        Write-Host ".env.example not found - creating default" -ForegroundColor Yellow

        @(
            "DATABASE_URL=postgresql+pg8000://lab:labpass@127.0.0.1:5432/labdb"
            "JWT_SECRET=change-me-in-production"
            "JWT_ALGORITHM=HS256"
            "JWT_EXPIRE_MINUTES=60"
            "ENV=dev"
        ) | Set-Content -Path ".env" -Encoding UTF8

        Write-Host "default .env created" -ForegroundColor Green
    }
} else {
    Write-Host ".env already exists" -ForegroundColor Green
}

# ---------------------------------------------------------
# 3. Generate SSL certificates
# ---------------------------------------------------------
Write-Host ""
Write-Host "> [3/7] Generating SSL certificates..." -ForegroundColor Yellow
if (-not (Test-Path "certs")) { New-Item -ItemType Directory -Path "certs" | Out-Null }

if ((Test-Path "certs/lab.local.crt") -and (Test-Path "certs/lab.local.key")) {
    Write-Host "Certificates already present" -ForegroundColor Green
} else {
    Write-Host "generating..." -ForegroundColor Gray
    $pwd = (Get-Location).Path
    docker run --rm -v "${pwd}/certs:/certs" alpine/openssl req -x509 -nodes -days 365 `
        -newkey rsa:2048 `
        -keyout /certs/lab.local.key `
        -out /certs/lab.local.crt `
        -subj "/CN=*.lab.local" `
        -addext "subjectAltName=DNS:*.lab.local,DNS:lab.local"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to generate certificates" -ForegroundColor Red
        exit 1
    }
    Write-Host "Certificates generated" -ForegroundColor Green
}

# ---------------------------------------------------------
# 4. Create venv (api + scheduler)
# ---------------------------------------------------------
Write-Host ""
Write-Host "> [4/7] Creating virtual environments..." -ForegroundColor Yellow

foreach ($service in @("api", "scheduler")) {
    $venvPath = "$service\.venv"
    Write-Host "  * $service..."
    if (-not (Test-Path $venvPath)) {
        C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe -m venv $venvPath
        if ($LASTEXITCODE -ne 0) {
            Write-Host "failed to create venv" -ForegroundColor Red
            exit 1
        }
        Write-Host ".venv created" -ForegroundColor Green
    } else {
        Write-Host " .venv already exists" -ForegroundColor Green
    }
}

# ---------------------------------------------------------
# 5. Install dependencies
# ---------------------------------------------------------
Write-Host ""
Write-Host "> [5/7] Installing Python dependencies..." -ForegroundColor Yellow

foreach ($service in @("api", "scheduler")) {
    if (Test-Path ".\$service\.venv\Scripts\python.exe") {
        $py = ".\$service\.venv\Scripts\python.exe"
    } else {
        $py = ".\$service\.venv\bin\python.exe"
    }
    $req = "$service\requirements.txt"

    if (Test-Path $req) {
        Write-Host "  * $service : pip install -r $req" -ForegroundColor Gray
        & $py -m pip install --upgrade pip --quiet
        & $py -m pip install -r $req --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Host "    [X] installation failed" -ForegroundColor Red
            exit 1
        }
        Write-Host "dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "$req not found" -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------
# 6. Start Docker Compose (wait for healthy)
# ---------------------------------------------------------
Write-Host ""
Write-Host "> [6/7] Starting infrastructure (Postgres + Traefik)..." -ForegroundColor Yellow

docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "docker compose up failed" -ForegroundColor Red
    exit 1
}

# Wait for Postgres to be healthy (max 60s)
Write-Host "waiting for PostgreSQL (healthy)..." -ForegroundColor Gray
$maxWait = 60
$elapsed = 0
$healthy = $false

while ($elapsed -lt $maxWait -and -not $healthy) {
    Start-Sleep -Seconds 2
    $elapsed += 2

    $status = docker inspect --format='{{.State.Health.Status}}' lab-postgres 2>$null
    if ($status -eq "healthy") {
        $healthy = $true
    } else {
        Write-Host "... ($elapsed s) status=$status" -ForegroundColor DarkGray
    }
}

if (-not $healthy) {
    Write-Host "PostgreSQL did not become healthy within $maxWait s" -ForegroundColor Red
    Write-Host "Check with: docker logs lab-postgres" -ForegroundColor Yellow
    exit 1
}
Write-Host "PostgreSQL is ready" -ForegroundColor Green

# Wait a bit for Traefik to start as well
Start-Sleep -Seconds 3
docker compose ps

# ---------------------------------------------------------
# 7. Migrations + Seed
# ---------------------------------------------------------
Write-Host ""
Write-Host "> [7/7] Migrations and seed..." -ForegroundColor Yellow

Push-Location api

if (Test-Path ".\.venv\Scripts\python.exe") {
    $apiPython = ".\.venv\Scripts\python.exe"
} else {
    $apiPython = ".\.venv\bin\python.exe"
}

Write-Host "  ... alembic upgrade head..." -ForegroundColor Gray
& $apiPython -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "alembic upgrade failed" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "migrations applied" -ForegroundColor Green

Write-Host "seed..." -ForegroundColor Gray
& $apiPython seed.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "seed failed" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "seed data inserted" -ForegroundColor Green

Pop-Location

# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------
Write-Host ""
Write-Host "===================================================" -ForegroundColor Green
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Start the services in 2 terminals:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Terminal 1 - API :" -ForegroundColor White
Write-Host "    cd api" -ForegroundColor Gray
Write-Host "    .\.venv\Scripts\Activate.ps1 (or .\.venv\bin\Activate.ps1)" -ForegroundColor Gray
Write-Host "    uvicorn app.main:app --reload" -ForegroundColor Gray
Write-Host ""
Write-Host "  Terminal 2 - Scheduler :" -ForegroundColor White
Write-Host "    cd scheduler" -ForegroundColor Gray
Write-Host "    .\.venv\Scripts\Activate.ps1 (or .\.venv\bin\Activate.ps1)" -ForegroundColor Gray
Write-Host "    python -m app.main" -ForegroundColor Gray
Write-Host ""
Write-Host "Then open:" -ForegroundColor Cyan
Write-Host "  * API Swagger : http://localhost:8000/docs" -ForegroundColor White
Write-Host "  * Traefik     : http://localhost:8080" -ForegroundColor White
Write-Host ""
Write-Host "To resolve *.lab.local, run (Admin):" -ForegroundColor Yellow
Write-Host "    .\scripts\update-hosts.ps1" -ForegroundColor Gray
Write-Host ""
