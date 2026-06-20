param(
    [string]$InstallDir = $PSScriptRoot
)

$ErrorActionPreference = "Stop"

function Resolve-InstallDir {
    param([string]$PathValue)
    return [System.IO.Path]::GetFullPath($PathValue).TrimEnd("\")
}

$installDir = Resolve-InstallDir $InstallDir
if (Test-Path -LiteralPath (Join-Path $installDir ".git") -PathType Container -ErrorAction SilentlyContinue) {
    Write-Host "This looks like the source workspace. Uninstall cancelled."
    exit 1
}
if (Test-Path -LiteralPath (Join-Path $installDir "meme_finder") -PathType Container -ErrorAction SilentlyContinue) {
    Write-Host "This looks like the source workspace. Uninstall cancelled."
    exit 1
}

Write-Host "MemeFinder UNINSTALL"
Write-Host ""
Write-Host "Program files folder:"
Write-Host $installDir
Write-Host ""
$confirm = Read-Host "Continue? [Y/N]"
if ($confirm -notin @("Y", "y")) {
    exit 0
}

Write-Host ""
Write-Host "Saved DATA is kept by default."
Write-Host "Portable DATA will be backed up before program files are removed."
$removeDataAnswer = Read-Host "Also remove saved DATA? Default is No [Y/N]"
$removeData = $removeDataAnswer -in @("Y", "y")

$env:MEMEFINDER_UNINSTALL_DIR = $installDir
$env:MEMEFINDER_REMOVE_DATA = if ($removeData) { "1" } else { "0" }

$childCommand = @'
$ErrorActionPreference = "Stop"
$log = Join-Path ([System.IO.Path]::GetTempPath()) "MemeFinder-Uninstall.log"
try {
    Set-Location -LiteralPath ([System.IO.Path]::GetTempPath())
    $installDir = [System.IO.Path]::GetFullPath($env:MEMEFINDER_UNINSTALL_DIR).TrimEnd("\")
    $removeData = $env:MEMEFINDER_REMOVE_DATA -eq "1"
    $desktop = [Environment]::GetFolderPath("Desktop")
    $appData = [Environment]::GetFolderPath("ApplicationData")
    $startMenu = Join-Path $appData "Microsoft\Windows\Start Menu\Programs\MemeFinder"

    Get-Process -Name "MemeFinder","TagDataEditor" -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path.StartsWith($installDir, [System.StringComparison]::OrdinalIgnoreCase) } |
        Stop-Process -Force -ErrorAction SilentlyContinue

    Remove-Item -LiteralPath (Join-Path $desktop "MemeFinder.lnk") -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $startMenu -Recurse -Force -ErrorAction SilentlyContinue

    if ($removeData) {
        Remove-Item -LiteralPath (Join-Path $appData "MemeFinder") -Recurse -Force -ErrorAction SilentlyContinue
    } elseif (Test-Path -LiteralPath (Join-Path $installDir "data")) {
        $backupRoot = Join-Path $appData "MemeFinder"
        New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
        $backup = Join-Path $backupRoot ("portable-data-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
        Move-Item -LiteralPath (Join-Path $installDir "data") -Destination $backup -Force
    }

    Start-Sleep -Seconds 2
    Remove-Item -LiteralPath $installDir -Recurse -Force -ErrorAction Stop
} catch {
    $_ | Out-String | Set-Content -LiteralPath $log -Encoding UTF8
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(("Uninstall failed. Close MemeFinder and check folder permissions. Log: " + $log), "MemeFinder UNINSTALL") | Out-Null
}
'@

Start-Process powershell -WorkingDirectory ([System.IO.Path]::GetTempPath()) -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    $childCommand
)

Write-Host ""
Write-Host "Uninstall has started. This window can close."
exit 0
