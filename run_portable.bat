@echo off
setlocal ENABLEDELAYEDEXPANSION

REM --- Portable runner for Windows ---

REM 0) Resolve project root as the folder of this .bat
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"

echo Pond Evaporation Simulation
echo ==========================

REM 1) Try conda-run first (no need to activate shell)
where conda >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Conda no está en PATH. Instala Miniconda/Anaconda o añade 'conda' al PATH.
    exit /b 1
)

REM 2) Ensure env exists; if not, create from environment.yml
if not exist ".\environment.yml" (
    echo [WARN] No environment.yml encontrado. Usaré 'requirements.txt' si existe.
) else (
    echo [INFO] Creando/actualizando entorno 'balsas' desde environment.yml (si no existe)...
    conda env list | findstr /r /c:"^balsas " >nul
    if errorlevel 1 (
        conda env create -n balsas -f environment.yml || (
            echo [ERROR] Fallo creando el entorno 'balsas'.
            exit /b 1
        )
    ) else (
        conda env update -n balsas -f environment.yml --prune
    )
)

REM 3) Run steps via conda run (evita activar shell)
echo [STEP] scraper_rad.py
conda run -n balsas python "%SCRIPT_DIR%scraper_rad.py"
if errorlevel 1 (
    echo [ERROR] scraper_rad.py failed
    exit /b 1
)

echo [STEP] evap_rate.py
conda run -n balsas python "%SCRIPT_DIR%evap_rate.py"
if errorlevel 1 (
    echo [ERROR] evap_rate.py failed
    exit /b 1
)

echo [STEP] main simulation: python -m src.run %*
conda run -n balsas python -m src.run %*
if errorlevel 1 (
    echo [ERROR] src.run failed
    exit /b 1
)

echo.
echo [OK] Simulation complete!
popd
exit /b 0
