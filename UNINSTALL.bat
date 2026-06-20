@echo off
setlocal
set "APPDIR=%~dp0"
set "SCRIPT=%APPDIR%UNINSTALL.ps1"

if exist "%APPDIR%.git\" goto source_guard
if exist "%APPDIR%meme_finder\" goto source_guard
if not exist "%SCRIPT%" goto missing_script

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -InstallDir "%APPDIR%"
exit /b %ERRORLEVEL%

:missing_script
echo UNINSTALL.ps1 was not found next to this file.
pause
exit /b 1

:source_guard
echo This looks like the source workspace, not an installed app folder.
echo Uninstall was cancelled to protect project files.
pause
exit /b 1
