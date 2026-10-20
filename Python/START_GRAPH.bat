@echo off
cd /d "%~dp0"
py mpu_graph.py
if errorlevel 1 (
  echo.
  echo The graph could not start. Check the instructions in README.md.
)
pause
