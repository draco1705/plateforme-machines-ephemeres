# Ajoute les entrées lab-*.lab.local dans le fichier hosts
# Doit être exécuté en tant qu'Administrateur
# Usage: .\scripts\update-hosts.ps1

$ErrorActionPreference = "Stop"

# Vérifier les droits admin
$currentUser = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentUser.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "❌ Ce script doit être exécuté en tant qu'Administrateur" -ForegroundColor Red
    Write-Host "   Relancez PowerShell en tant qu'Admin puis réessayez." -ForegroundColor Yellow
    exit 1
}

$hostsFile = "$env:SystemRoot\System32\drivers\etc\hosts"
$marker = "# === LAB HACKER ==="
$endMarker = "# === END LAB HACKER ==="

# Lire le contenu actuel
$content = Get-Content $hostsFile -Raw

# Supprimer ancien bloc si existe
if ($content -match [regex]::Escape($marker)) {
    $content = $content -replace "(?s)$([regex]::Escape($marker)).*?$([regex]::Escape($endMarker))\r?\n?", ""
}

# Construire nouveau bloc
$lines = @()
$lines += $marker
for ($i = 1; $i -le 50; $i++) {
    $lines += "127.0.0.1  lab-$i.lab.local"
}
$lines += $endMarker
$lines += ""
$block = $lines -join "`r`n"

# Ajouter
$newContent = $content + $block
Set-Content -Path $hostsFile -Value $newContent -NoNewline

Write-Host "Fichier hosts mis à jour avec lab-1 → lab-50" -ForegroundColor Green
ipconfig /flushdns | Out-Null
Write-Host "Cache DNS vidé" -ForegroundColor Green