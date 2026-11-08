@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo L'environnement Python du projet est absent.
  echo Consultez docs\ARCHITECTURE.md pour le demarrage et les dependances.
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" -B "%~dp0lancer.py"
if errorlevel 1 pause
