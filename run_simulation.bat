@echo off
REM --- Full Simulation Runner using conda environment 'balsas' ---

echo Pond Evaporation Simulation
echo ==========================

REM 1. Activate Miniconda and environment 'balsas'
CALL "C:\Users\ines.draaijer\AppData\Local\miniconda3\Scripts\activate.bat" balsas
echo balsas env activated

REM 2. Change to project directory
cd /d "C:\Users\ines.draaijer\Desktop\Proyectos\Tografa\code_transfers"
echo inside code_transfers

REM 3. Generate radiation input
echo Running scraper_rad.py...
python "C:\Users\ines.draaijer\Desktop\Proyectos\Tografa\code_transfers\inputs\scraper_rad.py"
if errorlevel 1 (
    echo Error: scraper_rad.py failed
    pause
    exit /b 1
)
echo scraper_rad executed

REM 4. Extract temperature (7-day forecast Monzón)
echo Running extract_temp.py...
python "C:\Users\ines.draaijer\Desktop\Proyectos\Tografa\code_transfers\inputs\weather\extract_temp.py"
if errorlevel 1 (
    echo Error: extract_temp.py failed
    pause
    exit /b 1
)
echo extract_temp executed

REM 5. Compute evaporation rates
echo Running evap_rate.py...
python "C:\Users\ines.draaijer\Desktop\Proyectos\Tografa\code_transfers\inputs\evap_rate.py"
if errorlevel 1 (
    echo Error: evap_rate.py failed
    pause
    exit /b 1
)
echo evap_rate executed

REM 6. Run the main simulation
echo Starting main simulation...
python -m src.run %*

echo.
echo Simulation complete!
pause
