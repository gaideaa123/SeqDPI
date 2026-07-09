$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "[SeqDPI] Preparing clean Windows build..."
if (Test-Path dist) { Remove-Item dist -Recurse -Force }
if (Test-Path build) { Remove-Item build -Recurse -Force }

python -m pip install --upgrade pip
python -m pip install pyinstaller

Write-Host "[SeqDPI] Building colorful windowed admin exe..."
pyinstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name SeqDPI `
  --uac-admin `
  --version-file version_info.txt `
  SeqDPI.pyw

Write-Host "[SeqDPI] Done: dist\SeqDPI.exe"
