# Install script for supergh (sgh) on Windows
# Usage: irm https://raw.githubusercontent.com/Shubham10-03/supergh/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$Repo = "Shubham10-03/supergh"  # TODO: replace with actual org/repo
$Binary = "sgh.exe"
$Artifact = "sgh-windows-x86_64.exe"
$InstallDir = "$env:LOCALAPPDATA\Programs\sgh"

# Get latest release
$Release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest"
$Tag = $Release.tag_name
$Url = "https://github.com/$Repo/releases/download/$Tag/$Artifact"

Write-Host "Installing sgh $Tag for Windows..."

# Create install directory
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# Download
$OutPath = Join-Path $InstallDir $Binary
Invoke-WebRequest -Uri $Url -OutFile $OutPath

# Add to PATH if not already there
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$UserPath;$InstallDir", "User")
    Write-Host "Added $InstallDir to PATH (restart terminal to take effect)"
}

Write-Host ""
Write-Host "Installed: $OutPath"
Write-Host "Run 'sgh setup' to configure your organization, logging, and authentication."
