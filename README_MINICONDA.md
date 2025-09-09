# Salina Simulation - Miniconda/Anaconda Setup Guide

This guide is for users running **Miniconda** or **Anaconda** on Windows.

## Quick Start (Recommended)

### Option 1: Use the Automated Script
1. **Open Anaconda Prompt** (or Command Prompt if conda is in PATH)
2. Navigate to the project folder:
   ```cmd
   cd path\to\salina-new
   ```
3. Run the Miniconda-specific script:
   ```cmd
   run_miniconda.bat
   ```

The script will automatically:
- Create a `salina` conda environment (if it doesn't exist)
- Install all required dependencies
- Run the simulation

### Option 2: Manual Setup
If you prefer manual control:

1. **Open Anaconda Prompt**
2. Navigate to project folder
3. Create and activate environment:
   ```cmd
   conda create -n salina python=3.10
   conda activate salina
   ```
4. Install dependencies:
   ```cmd
   conda install pandas pyyaml matplotlib -y
   ```
5. Run simulation:
   ```cmd
   python -m src.run
   ```

## Troubleshooting

### "Conda is not recognized"
- Make sure you're using **Anaconda Prompt** (not regular Command Prompt)
- Or add Miniconda to your PATH during installation

### "Failed to activate environment"
- Try running in **Anaconda Prompt** instead of regular Command Prompt
- Or manually activate: `conda activate salina`

### "Module not found" errors
- Ensure you're in the correct directory (where `src` folder exists)
- Verify environment is activated: `conda env list` (active env has *)

### Dependencies issues
- Try: `conda update conda`
- Then: `conda install pandas pyyaml matplotlib -y`
- As fallback: `pip install -r requirements.txt`

## Environment Management

### View all environments:
```cmd
conda env list
```

### Activate the salina environment:
```cmd
conda activate salina
```

### Remove the environment (if needed):
```cmd
conda env remove -n salina
```

### Update dependencies:
```cmd
conda activate salina
conda update --all
```

## Alternative: Using Base Environment

If you don't want to create a separate environment:

1. **Open Anaconda Prompt**
2. Install dependencies in base:
   ```cmd
   conda install pandas pyyaml matplotlib -y
   ```
3. Navigate to project and run:
   ```cmd
   python -m src.run
   ```

## Output Location

Results will be saved in:
- `experiment_results\output\` - Simulation data files
- `experiment_results\plots\` - Generated plots  
- `experiment_results\run_summary\` - Analysis reports

## Command Line Options

You can pass additional options:
```cmd
run_miniconda.bat --plot
```

Or with manual execution:
```cmd
python -m src.run --plot --config custom_config.yaml
```

## Notes for Advanced Users

- The simulation uses PHREEQC for geochemical modeling
- Configuration is in `env.yaml`
- Input data is in `inputs\` folder
- The system creates multiple pond simulations with transfers

## Getting Help

If you encounter issues:
1. Check that your Miniconda installation is working: `conda --version`
2. Verify Python installation: `python --version`
3. Check the project structure exists (src folder, etc.)
4. Try running in a fresh Anaconda Prompt

For more details, see the main README.md file.
