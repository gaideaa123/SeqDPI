$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "[SeqDPI] Building app executable first..."
./build_exe.ps1

Write-Host "[SeqDPI] Bundling GoodbyeDPI-Turkey engine into setup..."
$EngineDir = Join-Path $Root "dist\engine"
$EngineZip = Join-Path $Root "dist\goodbyedpi-turkey.zip"
if (Test-Path $EngineDir) { Remove-Item $EngineDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $EngineDir | Out-Null

$Release = Invoke-RestMethod -Headers @{ "User-Agent" = "SeqDPI" } -Uri "https://api.github.com/repos/cagritaskn/GoodbyeDPI-Turkey/releases/latest"
$Asset = $Release.assets | Where-Object { $_.name -like "*turkey*.zip" } | Select-Object -First 1
if (-not $Asset) { throw "GoodbyeDPI-Turkey zip asset bulunamadı" }
Invoke-WebRequest -Headers @{ "User-Agent" = "SeqDPI" } -Uri $Asset.browser_download_url -OutFile $EngineZip
Expand-Archive -Path $EngineZip -DestinationPath $EngineDir -Force
@{
  asset = $Asset.browser_download_url
  bundledAt = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $EngineDir "engine-is-turkey-release.json")

$HasRuntime = Get-ChildItem -Path $EngineDir -Recurse -Filter "turkey_dnsredir.cmd" | Select-Object -First 1
if (-not $HasRuntime) { throw "Bundled engine içinde turkey_dnsredir.cmd yok" }

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
