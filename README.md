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
├── inputs/                        # Input data
│   ├── brineData.txt             # Initial brine composition (PHREEQC SOLUTION format)
│   ├── pondsData.txt             # Pond specifications (names and volumes)
│   └── evap_diaria.csv           # Daily evaporation rates (365 days, seasonal)
├── phreeqc-3.5.0-14000/         # PHREEQC installation
│   ├── bin/phreeqc               # PHREEQC executable
│   └── database/phreeqc.dat      # Geochemical database
└── env.yaml                      # Configuration file (all paths and settings)
```

## Experiment Inputs

### Input Files (inputs/ directory):
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

## Technical Implementation

- **PHREEQC Integration**: Wrapped in `src.workingTools.phreeqcModel` with absolute paths
- **Variable Evaporation**: 1 step = 1 day with seasonal rate scheduling
- **Transfer Logic**: Automatic triggering based on halite saturation thresholds
- **Multi-stage Pipeline**: P1 → P6 cascade with legacy filename compatibility
- **Robust Parsing**: Centralized selected-output processing with error handling

## Troubleshooting

### Common Issues:
- **PHREEQC not found**: Check `env.yaml` phreeqc_bin path
- **Input files missing**: Ensure all files exist in `inputs/` directory
- **Convergence failures**: Adjust `max_evap_step_mol_L` in code if needed
- **Import errors**: Run from project root with `python -m src.run`

### Performance Notes:
- Simulation typically completes in ~2-3 seconds
- Variable evaporation creates realistic 9-10 month operation cycles  
- System handles 365-day seasonal schedules efficiently

- If imports for pandas/matplotlib show unresolved in VS Code, select the `.venv` interpreter.
- If PHREEQC is not found, verify the folder `phreeqc-*/bin/phreeqc` exists and that a database file like `phreeqc.dat` is under `phreeqc-*/database/`.

## Frequently Asked Questions (FAQ)

### **Q: How do variable evaporation rates work?**

The system uses a 365-day CSV file to simulate realistic seasonal evaporation patterns instead of constant rates.

**File Format** (`inputs/evap_diaria.csv`):
```csv
Fecha,evap_mol_day_L
2023-09-01,0.1938
2023-09-02,0.3973
2023-09-03,0.3762
...365 rows total...
```

**Implementation Flow**:
1. **CSV Loading**: System reads `evap_mol_day_L` column into a 365-day schedule
2. **Daily Mapping**: Each CSV row = 1 simulation day = 1 PHREEQC reaction step  
3. **Progressive Slicing**: Each pond stage uses the next slice of the annual cycle
4. **PHREEQC Generation**: Creates variable-rate REACTION blocks like:
   ```phreeqc
   REACTION 1
   Water
   -0.1938 mol    # Day 1 rate
   -0.3973 mol    # Day 2 rate
   -0.3762 mol    # Day 3 rate
   30 steps       # Total days in this stage
   ```

**Seasonal Behavior**:
- **Summer**: High rates (0.4-0.5 mol/day/L) → faster halite formation
- **Winter**: Low rates (0.1-0.2 mol/day/L) → slower concentration  
- **Transitions**: Realistic spring/fall variations

### **Q: How do I add my own evaporation data?**

**Step 1**: Create your CSV file with this exact format:
```csv
Fecha,evap_mol_day_L
2024-01-01,0.150
2024-01-02,0.155
2024-01-03,0.148
...continue for 365 days...
```

**Step 2**: Place the file in the `inputs/` directory (e.g., `inputs/my_rates.csv`)

**Step 3**: Update `env.yaml` configuration:
```yaml
evaporation_schedule: "inputs/my_rates.csv"
```

**Step 4**: Run simulation - it will automatically use your rates!

**Tips**:
- **Units**: Use `mol/day/L` (moles of water per day per liter of brine)
- **Range**: Typical values 0.1-0.5, higher values may need rate capping
- **Length**: Must be exactly 365 days for annual cycle
- **Column**: Must have `evap_mol_day_L` header (case-sensitive)

### **Q: What if I don't have evaporation data?**

No problem! The system falls back to constant rates if:
- No CSV file is configured
- CSV file is missing or invalid
- Column `evap_mol_day_L` not found

It will use the default constant rate (0.273 mol/day/L) and show:
```
No evaporation schedule configured - using constant rate
```

### **Q: How is the rate data validated?**

The system includes several safety features:
- **Rate Capping**: High values automatically capped at 0.35 mol/day/L for stability
- **Missing Data**: Falls back to constant rate if CSV problems occur
- **Console Reporting**: Shows loaded schedule statistics:
  ```
  Loaded evaporation schedule from evap_diaria.csv
  Schedule: 365 days, avg rate: 0.320 mol/day/L
  Rate range: 0.118 to 0.507 mol/day/L
  ```

### **Q: Can I use different time periods?**

Currently the system expects exactly 365 days. For shorter/longer periods:
- **Shorter**: Repeat your data to reach 365 days
- **Longer**: The system will cycle back to day 1 after day 365
- **Custom lengths**: Would require modifying `src/io/loaders.py`

### **Q: How do I verify variable rates are working?**

Look for these indicators in the console output:
1. **Loading confirmation**: `"Loaded evaporation schedule from [filename]"`
2. **Variable slices**: Different rate ranges per stage:
   ```
   Using schedule slice [0:30] = 30 days, first few: [0.194, 0.397, 0.376...]
   Using schedule slice [30:76] = 46 days, first few: [0.237, 0.237, 0.237...]
   ```
3. **Realistic timing**: Transfer days that vary with seasonal rates
4. **Plot variation**: Saved plots show non-linear mineral evolution curves

### **Q: Where is this implemented in the code?**

**Key Files**:
- `src/io/loaders.py`: CSV loading and validation
- `src/domain/simulation.py`: Schedule slicing and PHREEQC generation  
- `src/utils/config.py`: Path resolution from env.yaml
- `env.yaml`: Configuration file specifying CSV location

**Core Functions**:
- `load_input()`: Loads CSV into `params.evap_schedule_mol_per_day_L`
- `_get_evap_steps_variable_schedule()`: Slices schedule by simulation days
- `_write_reaction_block()`: Generates variable-rate PHREEQC input blocks

### **Q: How exactly are the rates implemented - is it a matrix?**

**No, it's not a matrix approach.** The system uses **PHREEQC's sequential multi-step reaction system** instead.

**Sequential Steps Implementation:**

**1. CSV → PHREEQC Steps (Not Matrix)**
```python
# Your CSV data:
# Day 1: 0.1938 mol/day/L
# Day 2: 0.3973 mol/day/L  
# Day 3: 0.3762 mol/day/L

# Gets converted to PHREEQC input:
REACTION 1
Water
-0.1938 mol    # Step 1 (Day 1)
-0.3973 mol    # Step 2 (Day 2)
-0.3762 mol    # Step 3 (Day 3)
3 steps        # Total reaction steps
```

**2. Code Implementation** (`src/domain/simulation.py`):
```python
def _write_reaction_block(self, fh, ...):
    if self.params.evap_schedule_mol_per_day_L:  # Variable rates
        # Get slice of schedule for this simulation stage
        sched = full[start:end]  # e.g., days 76-142
        
        # Write each day as a separate PHREEQC step
        sched_line = " ".join(f"-{rate}" for rate in sched)
        fh.write(f"{sched_line}\n")  # One line with all rates
        fh.write("INCREMENTAL_REACTIONS true\n")
```

**3. PHREEQC Execution Process:**
- **Step 1**: Remove 0.1938 mol water → calculate equilibrium → check mineral precipitation
- **Step 2**: Remove 0.3973 mol water → calculate equilibrium → check mineral precipitation
- **Step 3**: Remove 0.3762 mol water → calculate equilibrium → check mineral precipitation
- **Result**: Each step builds on the previous step's chemistry

**Why Sequential Steps (Not Matrix)?**
- **Chemical Accuracy**: Each step calculates proper equilibrium before next step
- **PHREEQC Native**: Uses built-in multi-step reaction capability
- **Mineral Tracking**: Halite formation depends on actual concentration at each step
- **Memory Efficient**: No large matrices needed in memory
- **Matrix Problems**: Chemical equilibrium is non-linear, can't be pre-calculated

**Real Example from Console:**
```
Using schedule slice [76:142] = 66 days, first few: [0.237, 0.237, 0.237, 0.237, 0.237]
```
Creates PHREEQC input with 66 sequential reaction steps, each removing the exact amount for that day.

**Key Point**: **1 CSV row** = **1 PHREEQC step** = **1 simulation day** with proper geochemical modeling at each time step.
