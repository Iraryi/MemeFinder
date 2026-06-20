$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Set-PipProxyFromSystem {
    if ($env:HTTP_PROXY -or $env:HTTPS_PROXY) {
        return
    }
    try {
        $proxyJson = py -3.10 -c "import urllib.request, json; print(json.dumps(urllib.request.getproxies()))"
        $proxies = $proxyJson | ConvertFrom-Json
        if ($proxies.http) {
            $env:HTTP_PROXY = [string]$proxies.http
        }
        if ($proxies.https) {
            $httpsProxy = [string]$proxies.https
            if ($httpsProxy -match "^https://127\.0\.0\.1:(\d+)$") {
                $httpsProxy = "http://127.0.0.1:$($Matches[1])"
            }
            $env:HTTPS_PROXY = $httpsProxy
        }
    }
    catch {
        Write-Host "No system proxy was applied for pip."
    }
}

function New-AppPayloadZip {
    param(
        [Parameter(Mandatory = $true)][string]$SourceDir,
        [Parameter(Mandatory = $true)][string]$ZipPath
    )

    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }

    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        $sourceRoot = (Resolve-Path -LiteralPath $SourceDir).Path
        $files = Get-ChildItem -LiteralPath $sourceRoot -Recurse -File
        foreach ($file in $files) {
            $relative = $file.FullName.Substring($sourceRoot.Length + 1).Replace("\", "/")
            if ($relative -eq "data" -or $relative.StartsWith("data/", [System.StringComparison]::OrdinalIgnoreCase)) {
                continue
            }
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip,
                $file.FullName,
                $relative,
                [System.IO.Compression.CompressionLevel]::Optimal
            ) | Out-Null
        }
    }
    finally {
        $zip.Dispose()
    }
}

Set-PipProxyFromSystem
py -3.10 -m pip install pyinstaller

$appDir = Join-Path $PSScriptRoot "dist\MemeFinder"
$appExe = Join-Path $appDir "MemeFinder.exe"
$tagEditorExe = Join-Path $appDir "TagDataEditor.exe"
$uninstallBat = Join-Path $appDir "UNINSTALL.bat"
$uninstallPs1 = Join-Path $appDir "UNINSTALL.ps1"
$sourceUninstallBat = Join-Path $PSScriptRoot "UNINSTALL.bat"
$sourceUninstallPs1 = Join-Path $PSScriptRoot "UNINSTALL.ps1"
$uninstallNeedsRefresh = (-not (Test-Path -LiteralPath $uninstallBat)) -or (-not (Test-Path -LiteralPath $uninstallPs1)) -or ((Get-Item -LiteralPath $sourceUninstallBat).LastWriteTime -gt (Get-Item -LiteralPath $uninstallBat -ErrorAction SilentlyContinue).LastWriteTime) -or ((Get-Item -LiteralPath $sourceUninstallPs1).LastWriteTime -gt (Get-Item -LiteralPath $uninstallPs1 -ErrorAction SilentlyContinue).LastWriteTime)
if ((-not (Test-Path -LiteralPath $appExe)) -or (-not (Test-Path -LiteralPath $tagEditorExe)) -or $uninstallNeedsRefresh) {
    .\build.ps1
}

$setupBuildDir = Join-Path $PSScriptRoot "build\setup_payload"
$payloadZip = Join-Path $setupBuildDir "app_payload.zip"
$releaseDir = Join-Path $PSScriptRoot "release"
$setupName = "MemeFinder-Setup.exe"
$setupDistExe = Join-Path $PSScriptRoot "dist\$setupName"
$setupReleaseExe = Join-Path $releaseDir $setupName
$iconPath = Join-Path $PSScriptRoot "assets\MemeFinder.ico"
$assetsDir = Join-Path $PSScriptRoot "assets"
$assetsData = "$assetsDir;assets"
$payloadData = "$payloadZip;."

if (Test-Path -LiteralPath $setupBuildDir) {
    Remove-Item -LiteralPath $setupBuildDir -Recurse -Force
}
New-Item -ItemType Directory -Path $setupBuildDir -Force | Out-Null
New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null

New-AppPayloadZip -SourceDir $appDir -ZipPath $payloadZip

if (Test-Path -LiteralPath $setupDistExe) {
    Remove-Item -LiteralPath $setupDistExe -Force
}
if (Test-Path -LiteralPath $setupReleaseExe) {
    Remove-Item -LiteralPath $setupReleaseExe -Force
}

py -3.10 -m PyInstaller --clean --noconsole --onefile --name "MemeFinder-Setup" --icon "$iconPath" --add-data "$payloadData" --add-data "$assetsData" installer\setup_installer.py
Copy-Item -LiteralPath $setupDistExe -Destination $setupReleaseExe -Force

if (Test-Path -LiteralPath $setupDistExe) {
    Remove-Item -LiteralPath $setupDistExe -Force
}
if (Test-Path -LiteralPath $setupBuildDir) {
    Remove-Item -LiteralPath $setupBuildDir -Recurse -Force
}
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot "MemeFinder-Setup.spec")) {
    Remove-Item -LiteralPath (Join-Path $PSScriptRoot "MemeFinder-Setup.spec") -Force
}
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot "build\MemeFinder-Setup")) {
    Remove-Item -LiteralPath (Join-Path $PSScriptRoot "build\MemeFinder-Setup") -Recurse -Force
}

Write-Host "Setup build finished: $setupReleaseExe"
