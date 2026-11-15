@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "%~dp0dangbei-setup.exe" (
    "%~dp0dangbei-setup.exe" %*
    exit /b
)
rem Source checkout only. Published Windows archives include the executable.
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 install.py %*
) else (
    python install.py %*
)
echo.
pause
