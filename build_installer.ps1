$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Find-InnoSetup {
  $candidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
  )
  $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($found) { return $found }
  $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  return $null
}

function Install-InnoSetup {
  Write-Host "[SeqDPI] Inno Setup bulunamadı, otomatik kurulacak..."
  $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
  if ($winget) {
    Write-Host "[SeqDPI] winget ile Inno Setup kuruluyor..."
    $wingetOutput = & winget install --id JRSoftware.InnoSetup --exact --silent --accept-package-agreements --accept-source-agreements 2>&1
    $wingetOutput | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
      Write-Host "[SeqDPI] winget id ile bulamadı, arama adıyla deneniyor..."
      $wingetOutput = & winget install "Inno Setup" --silent --accept-package-agreements --accept-source-agreements 2>&1
      $wingetOutput | ForEach-Object { Write-Host $_ }
    }
  }

  $iscc = Find-InnoSetup
  if ($iscc) { return $iscc }

  $choco = Get-Command choco.exe -ErrorAction SilentlyContinue
  if ($choco) {
    Write-Host "[SeqDPI] Chocolatey ile Inno Setup kuruluyor..."
    $chocoOutput = & choco install innosetup -y 2>&1
    $chocoOutput | ForEach-Object { Write-Host $_ }
  }

  $iscc = Find-InnoSetup
  if ($iscc) { return $iscc }
  throw "Inno Setup otomatik kurulamadı. Elle çalıştır: winget install --id JRSoftware.InnoSetup --exact"
}

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
@{ asset = $Asset.browser_download_url; bundledAt = (Get-Date).ToString("o") } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $EngineDir "engine-is-turkey-release.json")

$HasRuntime = Get-ChildItem -Path $EngineDir -Recurse -Filter "turkey_dnsredir.cmd" | Select-Object -First 1
if (-not $HasRuntime) { throw "Bundled engine içinde turkey_dnsredir.cmd yok" }

$Iscc = Find-InnoSetup
if (-not $Iscc) { $Iscc = Install-InnoSetup }
$Iscc = [string]$Iscc

Write-Host "[SeqDPI] Inno Setup: $Iscc"
Write-Host "[SeqDPI] Building setup wizard..."
& $Iscc "installer\SeqDPI.iss"

Write-Host "[SeqDPI] Done: dist\installer\SeqDPI-Setup.exe"
