$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "[SeqDPI] Building app executable first..."
./build_exe.ps1

$IsccCandidates = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)

$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
  throw "Inno Setup 6 bulunamadı. Kur: winget install JRSoftware.InnoSetup veya choco install innosetup"
}

Write-Host "[SeqDPI] Building setup wizard..."
& $Iscc "installer\SeqDPI.iss"

Write-Host "[SeqDPI] Done: dist\installer\SeqDPI-Setup.exe"
