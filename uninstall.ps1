# Uninstall script for supergh (sgh) on Windows
# Usage: irm https://raw.githubusercontent.com/<org>/supergh/main/uninstall.ps1 | iex

$ErrorActionPreference = "Stop"

$Binary = "sgh.exe"
$InstallDir = "$env:LOCALAPPDATA\Programs\sgh"
$BinaryPath = Join-Path $InstallDir $Binary
$ConfigDir = Join-Path $env:USERPROFILE ".supergh"

Write-Host "Uninstalling sgh..."

# Remove binary
if (Test-Path $BinaryPath) {
    Remove-Item $BinaryPath -Force
    Write-Host "  Removed: $BinaryPath"
} else {
    # Check common PATH locations
    $found = Get-Command sgh -ErrorAction SilentlyContinue
    if ($found) {
        Remove-Item $found.Source -Force
        Write-Host "  Removed: $($found.Source)"
    } else {
        Write-Host "  sgh binary not found."
        Write-Host "  If installed via pip: pip uninstall supergh"
    }
}

# Remove install directory if empty
if (Test-Path $InstallDir) {
    $remaining = Get-ChildItem $InstallDir -ErrorAction SilentlyContinue
    if (-not $remaining) {
        Remove-Item $InstallDir -Force
        Write-Host "  Removed: $InstallDir"
    }
}

# Remove from PATH
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -like "*$InstallDir*") {
    $NewPath = ($UserPath.Split(";") | Where-Object { $_ -ne $InstallDir }) -join ";"
    [Environment]::SetEnvironmentVariable("PATH", $NewPath, "User")
    Write-Host "  Removed from PATH"
}

# Config and logs
if (Test-Path $ConfigDir) {
    $response = Read-Host "  Remove config and logs (~/.supergh)? [y/N]"
    if ($response -eq "y" -or $response -eq "Y") {
        Remove-Item $ConfigDir -Recurse -Force
        Write-Host "  Removed: $ConfigDir"
    }
}

# Remove credentials from Windows Credential Manager
try {
    $creds = cmdkey /list 2>$null | Select-String "supergh"
    if ($creds) {
        cmdkey /delete:supergh 2>$null
        Write-Host "  Removed stored credentials"
    }
} catch {}

Write-Host ""
Write-Host "sgh uninstalled."
