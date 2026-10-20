@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Install failed. Check that Python is installed and internet is available.
  pause
  exit /b 1
)
echo.
echo Libraries installed. You can now run START_GRAPH.bat.
pause
