@echo off
REM Salina Evaporation Simulation Runner for Miniconda/Anaconda
REM This script is optimized for conda environments

echo Salina Evaporation Pond Simulation - Conda Version
echo ==================================================

REM Initialize conda for batch file usage
call conda info >nul 2>&1
if errorlevel 1 (
    echo Error: Conda is not installed or not in PATH
    echo Please install Miniconda/Anaconda and restart your command prompt
    echo Download from: https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)

echo Conda version:
conda --version
echo.

REM Check if we're already in a conda environment
if defined CONDA_DEFAULT_ENV (
    echo Already in conda environment: %CONDA_DEFAULT_ENV%
    goto :install_deps
)

REM Check if salina environment exists, create if not
echo Checking for 'salina' conda environment...
conda env list | findstr /C:"salina" >nul 2>&1
if errorlevel 1 (
    echo Creating new conda environment 'salina' with Python 3.10...
    conda create -n salina python=3.10 -y
    if errorlevel 1 (
        echo Error: Failed to create conda environment
        pause
        exit /b 1
    )
)

REM Activate the salina environment
echo Activating conda environment: salina
call conda activate salina
if errorlevel 1 (
    echo Error: Failed to activate conda environment 'salina'
    echo Try running this in an Anaconda Prompt instead
    pause
    exit /b 1
)

:install_deps
echo Using Python from environment: %CONDA_DEFAULT_ENV%
echo Python location:
where python
echo Python version:
python --version
echo.

REM Install/check dependencies using conda
echo Installing/checking dependencies with conda...
conda install pandas pyyaml matplotlib -y
if errorlevel 1 (
    echo Warning: Conda install failed, trying pip...
    pip install -r requirements.txt
)

REM Verify installation
echo Verifying dependencies...
python -c "import pandas, yaml, matplotlib; print('✓ All dependencies available')" 2>&1
if errorlevel 1 (
    echo Error: Dependencies could not be installed or imported
    echo Please check your conda environment setup
    pause
    exit /b 1
)

echo.

REM Run the simulation
echo Starting simulation...
echo Working directory: %CD%
echo Environment: %CONDA_DEFAULT_ENV%
echo.

python -m src.run %*

if errorlevel 1 (
    echo.
    echo Error: Simulation failed
    echo Check the error messages above for details
    pause
    exit /b 1
)

echo.
echo Simulation complete!
echo Check experiment_results\ for outputs and plots
echo.
echo To run again, you can use:
echo   conda activate salina
echo   python -m src.run
pause
