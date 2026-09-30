# Génère les certificats auto-signés pour *.lab.local
# Usage: .\scripts\generate-certs.ps1

$ErrorActionPreference = "Stop"
$certDir = Join-Path $PSScriptRoot "..\certs"

if (-not (Test-Path $certDir)) {
    New-Item -ItemType Directory -Path $certDir | Out-Null
}

$crtFile = Join-Path $certDir "lab.local.crt"
$keyFile = Join-Path $certDir "lab.local.key"

if ((Test-Path $crtFile) -and (Test-Path $keyFile)) {
    Write-Host "Certificats déjà présents — skip" -ForegroundColor Green
    exit 0
}

Write-Host "🔐 Génération des certificats pour *.lab.local..." -ForegroundColor Cyan

$pwd = (Get-Location).Path
docker run --rm `
    -v "${pwd}/certs:/certs" `
    alpine/openssl req -x509 -nodes -days 365 `
    -newkey rsa:2048 `
    -keyout /certs/lab.local.key `
    -out /certs/lab.local.crt `
    -subj "/CN=*.lab.local" `
    -addext "subjectAltName=DNS:*.lab.local,DNS:lab.local"

Write-Host "✅ Certificats générés dans certs/" -ForegroundColor Green