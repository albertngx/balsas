@echo off
REM Salina Evaporation Simulation Runner for Windows
REM This script runs the pond simulation from the project root

echo Salina Evaporation Pond Simulation
echo ==================================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

echo Using Python: 
python --version
echo.

REM Check if virtual environment exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
    echo Using virtual environment Python:
    where python
    echo.
)

REM Check if requirements are installed
echo Checking dependencies...
python -c "import pandas, yaml, matplotlib" >nul 2>&1
if errorlevel 1 (
    echo Warning: Some dependencies may be missing
    echo Consider running: pip install -r requirements.txt
    echo.
)

REM Run the simulation
echo Starting simulation...
echo Working directory: %CD%
echo.

python -m src.run %*

if errorlevel 1 (
    echo.
    echo Error: Simulation failed
    pause
    exit /b 1
)

echo.
echo Simulation complete!
echo Check experiment_results\ for outputs and plots
pause
