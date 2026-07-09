$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "[SeqDPI] Preparing clean Windows build..."
if (Test-Path dist) { Remove-Item dist -Recurse -Force }
if (Test-Path build) { Remove-Item build -Recurse -Force }

python -m pip install --upgrade pip
python -m pip install pyinstaller pystray pillow

$AddDataArgs = @("--add-data", "SeqDPI.pyw;.")
if (Test-Path "hello.mp3") { $AddDataArgs += @("--add-data", "hello.mp3;.") }
if (Test-Path "dns.mp3") { $AddDataArgs += @("--add-data", "dns.mp3;.") }

Write-Host "[SeqDPI] Building colorful windowed admin exe with tray support..."
pyinstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name SeqDPI `
  --uac-admin `
  --version-file version_info.txt `
  @AddDataArgs `
  SeqDPI_tray.pyw

Write-Host "[SeqDPI] Done: dist\SeqDPI.exe"
