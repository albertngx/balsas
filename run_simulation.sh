#!/bin/bash
# Salina Evaporation Simulation Runner for macOS/Linux
# This script runs the pond simulation from the project root

set -e  # Exit on any error

# Check if Python is available
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "Error: Python is not installed or not in PATH"
    echo "Please install Python 3.8+ and try again"
    exit 1
fi

# Determine Python command
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

echo "Salina Evaporation Pond Simulation"
echo "=================================="
echo "Using Python: $(which $PYTHON_CMD)"
echo "Python version: $($PYTHON_CMD --version)"
echo ""

# Check if virtual environment exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
    echo "Using virtual environment Python: $(which python)"
    echo ""
fi

# Check if requirements are installed
echo "Checking dependencies..."
if ! $PYTHON_CMD -c "import pandas, yaml, matplotlib" 2>/dev/null; then
    echo "Warning: Some dependencies may be missing"
    echo "Consider running: pip install -r requirements.txt"
    echo ""
fi

# Run the simulation
echo "Starting simulation..."
echo "Working directory: $(pwd)"
echo ""

$PYTHON_CMD -m src.run "$@"

echo ""
echo "Simulation complete!"
echo "Check experiment_results/ for outputs and plots"
