@echo off
cd /d "%~dp0"
py -3.10 -m meme_finder
if errorlevel 1 pause
