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

Set-PipProxyFromSystem
py -3.10 -m pip install -r requirements.txt pyinstaller
$distDir = Join-Path $PSScriptRoot "dist"
$oldOneFile = Join-Path $distDir "MemeFinder.exe"
$appDir = Join-Path $distDir "MemeFinder"
$iconPath = Join-Path $PSScriptRoot "assets\MemeFinder.ico"
$assetsDir = Join-Path $PSScriptRoot "assets"
$assetsData = "$assetsDir;assets"
$dataBackup = $null
$dataDir = Join-Path $appDir "data"
if (Test-Path -LiteralPath $dataDir) {
    $dataBackup = Join-Path $env:TEMP ("MemeFinder-data-" + [guid]::NewGuid().ToString())
    Move-Item -LiteralPath $dataDir -Destination $dataBackup
}

try {
    if (Test-Path -LiteralPath $oldOneFile) {
        Remove-Item -LiteralPath $oldOneFile -Force
    }
    if (Test-Path -LiteralPath $appDir) {
        Remove-Item -LiteralPath $appDir -Recurse -Force
    }

    py -3.10 -m PyInstaller --clean --noconsole --onedir --name "MemeFinder" --icon "$iconPath" --add-data "$assetsData" --hidden-import "PIL._tkinter_finder" --hidden-import "rapidocr_onnxruntime" --collect-all "rapidocr_onnxruntime" --collect-all "onnxruntime" run.py
    py -3.10 -m PyInstaller --clean --noconsole --onefile --name "TagDataEditor" --icon "$iconPath" tag_data_editor.py
    Copy-Item -LiteralPath (Join-Path $distDir "TagDataEditor.exe") -Destination (Join-Path $appDir "TagDataEditor.exe") -Force
    Remove-Item -LiteralPath (Join-Path $distDir "TagDataEditor.exe") -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "portable.mode") -Destination (Join-Path $appDir "portable.mode") -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "UNINSTALL.bat") -Destination (Join-Path $appDir "UNINSTALL.bat") -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "UNINSTALL.ps1") -Destination (Join-Path $appDir "UNINSTALL.ps1") -Force
}
finally {
    if ($dataBackup -and (Test-Path -LiteralPath $dataBackup)) {
        if (-not (Test-Path -LiteralPath $appDir)) {
            New-Item -ItemType Directory -Path $appDir -Force | Out-Null
        }
        $targetDataDir = Join-Path $appDir "data"
        if (Test-Path -LiteralPath $targetDataDir) {
            Remove-Item -LiteralPath $targetDataDir -Recurse -Force
        }
        Move-Item -LiteralPath $dataBackup -Destination $targetDataDir
    }
}

Write-Host "Build finished. App folder: $appDir"
Write-Host "Launch EXE: $appDir\MemeFinder.exe"
