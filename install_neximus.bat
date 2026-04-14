@echo off
title Neximus AI Agent - Installer
echo.
echo ============================================================
echo  NEXIMUS AI AGENT - INSTALLER
echo ============================================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.11 or higher.
    echo Download from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

:: Launch the installer GUI
echo Launching installer...
python neximus_installer.py

pause