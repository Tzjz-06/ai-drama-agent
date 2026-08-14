$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$env:PYTHONPATH = "$projectRoot\src"

$outputRoot = Join-Path $projectRoot "outputs\frameforge-desktop"
$distRoot = Join-Path $projectRoot "dist"
$buildRoot = Join-Path $projectRoot "build"
$portableRoot = Join-Path $outputRoot "FrameForgeStudio"
$installerScript = Join-Path $projectRoot "installer\FrameForgeStudio.iss"
$appIcon = Join-Path $projectRoot "installer\jiaozi-creation-studio.ico"

Push-Location (Join-Path $projectRoot "frontend")
npm.cmd run build
Pop-Location
Copy-Item -Path (Join-Path $projectRoot "frontend\dist\*") -Destination (Join-Path $projectRoot "web") -Recurse -Force

function Get-AppVersion {
  $pyprojectPath = Join-Path $projectRoot "pyproject.toml"
  $content = Get-Content -Raw $pyprojectPath
  if ($content -match 'version\s*=\s*"([^"]+)"') {
    return $matches[1]
  }
  throw "Unable to determine app version from pyproject.toml"
}

function Get-InnoSetupCompiler {
  $candidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 7\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe")
  ) | Where-Object { $_ -and (Test-Path $_) }

  if ($candidates.Count -gt 0) {
    return @($candidates)[0]
  }

  $registryKeys = @(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
    "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 7_is1",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 7_is1",
    "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 7_is1"
  )

  foreach ($key in $registryKeys) {
    if (-not (Test-Path $key)) {
      continue
    }
    $installLocation = (Get-ItemProperty $key).InstallLocation
    if (-not $installLocation) {
      continue
    }
    $compiler = Join-Path $installLocation "ISCC.exe"
    if (Test-Path $compiler) {
      return $compiler
    }
  }

  throw "Unable to locate ISCC.exe. Please install Inno Setup 6 or 7 first."
}

if (Test-Path $distRoot) { Remove-Item -Recurse -Force $distRoot }
if (Test-Path $buildRoot) { Remove-Item -Recurse -Force $buildRoot }
if (Test-Path $outputRoot) { Remove-Item -Recurse -Force $outputRoot }

python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onedir `
  --name FrameForgeStudio `
  --icon "$appIcon" `
  --paths "$projectRoot\src" `
  --add-data "$projectRoot\web;web" `
  --add-data "$appIcon;." `
  --collect-all imageio_ffmpeg `
  --exclude-module PyQt5 `
  --exclude-module PyQt6 `
  --exclude-module PySide2 `
  --hidden-import PySide6.QtWebEngineWidgets `
  --hidden-import PySide6.QtWebEngineCore `
  "$projectRoot\src\ai_drama_agent\desktop.py"

New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
Copy-Item -Recurse -Force (Join-Path $distRoot "FrameForgeStudio") $outputRoot
Compress-Archive -Path $portableRoot -DestinationPath (Join-Path $outputRoot "FrameForgeStudio-windows.zip") -Force

$smokeProcess = Start-Process -FilePath (Join-Path $portableRoot "FrameForgeStudio.exe") -ArgumentList "--smoke-test" -Wait -PassThru
if ($smokeProcess.ExitCode -ne 0) {
  throw "Packaged desktop executable smoke test failed with exit code $($smokeProcess.ExitCode)"
}

$appVersion = Get-AppVersion
$iscc = Get-InnoSetupCompiler
& $iscc `
  /Qp `
  "/DAppVersion=$appVersion" `
  "/DSourceDir=$portableRoot" `
  "/DOutputDir=$outputRoot" `
  "/DIconFile=$appIcon" `
  $installerScript
if ($LASTEXITCODE -ne 0) {
  throw "Inno Setup compile failed with exit code $LASTEXITCODE"
}

Write-Output "Desktop package created:"
Write-Output $outputRoot
