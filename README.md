# Salina Evaporation Pond System

This project simulates a **6-pond cascade evaporation system** for salt production using PHREEQC geochemical modeling. The system implements variable seasonal evaporation rates and automatic transfer triggering based on halite formation.

## Experiment Overview - Balsas

The simulation models a real-world salt production facility with:

- **Primary Pond (Pond 1)**: Continuous concentrator that receives fresh brine
- **Receiving Ponds (2-6)**: Sequential cascade for concentrated brine storage
- **Variable Evaporation**: Seasonal rates from real meteorological data
- **Automatic Transfers**: Triggered when halite saturation is reached
- **Geochemical Modeling**: Complete mineral precipitation (halite, gypsum, calcite)

### System Operation
1. Pond 1 concentrates brine through evaporation until halite formation
2. Concentrated brine transfers to next available pond (2→3→4→5→6) 
3. Pond 1 restarts with fresh/diluted brine
4. Process continues creating increasingly concentrated ponds
5. System generates 5 transfers over ~9-10 months of operation

## Quick Start

### 1. Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuration
The system uses `env.yaml` for all paths and settings:
- PHREEQC binary and database paths
- Input data file locations  
- Output directory configuration
- Simulation parameters

### 3. Run Simulation

**Easy Option - Use Platform Scripts:**
```bash
# macOS/Linux
./run_simulation.sh

# Windows  
run_simulation.bat

# With optional plot preview
./run_simulation.sh --plot
```

**Direct Python Option:**
```bash
python -m src.run
```

**Note**: All paths are configured in `env.yaml` - no command line arguments needed!

## Project Structure

```
salina-new/
├── src/                          # Main source code
│   ├── domain/                   # Core models and simulation logic  
│   ├── io/                       # Input/output handling
│   ├── utils/                    # Plotting, analysis, and configuration
│   ├── workingTools/             # PHREEQC integration wrapper
│   └── run.py                    # Main entry point
├── experiment_results/           # All experiment outputs
│   ├── output/                   # PHREEQC result files (results.dat, results2.dat, ...)
│   ├── plots/                    # Generated visualizations (pond1_stage1.png, ...)
│   └── run_summary/              # Transfer analysis reports
├── files/                        # Input data
│   ├── brineData.txt             # Initial brine composition (PHREEQC SOLUTION format)
│   ├── pondsData.txt             # Pond specifications (names and volumes)
│   └── evap_diaria.csv           # Daily evaporation rates (365 days, seasonal)
├── phreeqc-3.5.0-14000/         # PHREEQC installation
│   ├── bin/phreeqc               # PHREEQC executable
│   └── database/phreeqc.dat      # Geochemical database
└── env.yaml                      # Configuration file (all paths and settings)
```

## Experiment Inputs

### Input Files (files/ directory):
- **brineData.txt**: Initial brine composition in PHREEQC SOLUTION format
- **pondsData.txt**: Pond specifications (tab-separated: name, volume in m³)
- **evap_diaria.csv**: 365-day seasonal evaporation schedule (mol/day/L)

### Configuration (env.yaml):
- PHREEQC binary and database paths
- Input/output directory configuration
- Simulation parameters (steps, rate caps, etc.)

## Experiment Outputs

### Result Files (experiment_results/output/):
- **results.dat**: Pond 1 initial evolution (days 0-36)
- **results2.dat**: Pond 2 after 1st transfer (days 36-135)
- **results3.dat**: Pond 1 continued evolution after 1st transfer
- **results5.dat**: Pond 3 after 2nd transfer (days 71-170)
- **results8.dat**: Pond 4 after 3rd transfer (days 107-206)
- **results11.dat**: Pond 5 after 4th transfer (days 142-241)
- **results14.dat**: Pond 6 after 5th transfer (days 177-276)
- *[Additional intermediate files for transfer preparations]*

### Visualizations (experiment_results/plots/):
- **pond1_stage1.png**: Pond 1 mineral evolution
- **pond2_stage2.png**: Pond 2 mineral evolution
- **pond3_stage3.png**: Pond 3 mineral evolution
- **pond4_stage4.png**: Pond 4 mineral evolution
- **pond5_stage5.png**: Pond 5 mineral evolution
- **pond6_stage6.png**: Pond 6 mineral evolution
- **overlay_pond1_vs_pond{N}.png**: Comparative analysis plots

### Analysis Reports (experiment_results/run_summary/):
- **SYSTEM_OVERVIEW.txt**: Complete system performance summary
- **TRANSFER_DETAILS.txt**: Detailed transfer log with timing and volumes
- **POND_ANALYSIS.txt**: Individual pond operations and seasonal impacts

### Console Output:
- Real-time transfer timeline with day-by-day progression
- Comprehensive transfer summary with pond performance metrics
- System efficiency indicators and halite concentration tracking

## 🔧 Technical Implementation

- **PHREEQC Integration**: Wrapped in `src.workingTools.phreeqcModel` with absolute paths
- **Variable Evaporation**: 1 step = 1 day with seasonal rate scheduling
- **Transfer Logic**: Automatic triggering based on halite saturation thresholds
- **Multi-stage Pipeline**: P1 → P6 cascade with legacy filename compatibility
- **Robust Parsing**: Centralized selected-output processing with error handling

## Troubleshooting

### Common Issues:
- **PHREEQC not found**: Check `env.yaml` phreeqc_bin path
- **Input files missing**: Ensure all files exist in `files/` directory
- **Convergence failures**: Adjust `max_evap_step_mol_L` in code if needed
- **Import errors**: Run from project root with `python -m src.run`

### Performance Notes:
- Simulation typically completes in ~2-3 seconds
- Variable evaporation creates realistic 9-10 month operation cycles  
- System handles 365-day seasonal schedules efficiently

- If imports for pandas/matplotlib show unresolved in VS Code, select the `.venv` interpreter.
- If PHREEQC is not found, verify the folder `phreeqc-*/bin/phreeqc` exists and that a database file like `phreeqc.dat` is under `phreeqc-*/database/`.
