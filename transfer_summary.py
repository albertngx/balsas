#!/usr/bin/env python3
"""
Generate a comprehensive transfer summary showing when transfers occur,
which ponds are involved, and estimated volumes transferred.
"""

import pandas as pd
from pathlib import Path
import sys

def analyze_transfers():
    """Analyze all result files to create a transfer summary."""
    
    output_dir = Path("phreeqc_work/output")
    if not output_dir.exists():
        print("Error: phreeqc_work/output directory not found")
        return
    
    print("=" * 80)
    print("SALINA POND TRANSFER SUMMARY")
    print("=" * 80)
    print()
    
    # Map result files to pond descriptions
    file_descriptions = {
        "results.dat": "Pond 1 - Initial evolution (0-30 days)",
        "results2.dat": "Pond 2 - After 1st transfer from Pond 1",
        "results3.dat": "Pond 1 - Continued evolution after 1st transfer",
        "results4.dat": "Pond 1 - Short run to 2nd transfer point", 
        "results5.dat": "Pond 3 - After 2nd transfer from Pond 1",
        "results6.dat": "Pond 1 - Continued evolution after 2nd transfer",
        "results7.dat": "Pond 1 - Short run to 3rd transfer point",
        "results8.dat": "Pond 4 - After 3rd transfer from Pond 1", 
        "results9.dat": "Pond 1 - Continued evolution after 3rd transfer",
        "results10.dat": "Pond 1 - Short run to 4th transfer point",
        "results11.dat": "Pond 5 - After 4th transfer from Pond 1",
        "results12.dat": "Pond 1 - Continued evolution after 4th transfer",
        "results13.dat": "Pond 1 - Short run to 5th transfer point", 
        "results14.dat": "Pond 6 - After 5th transfer from Pond 1",
    }
    
    # Transfer schedule (from the console output we saw)
    transfers = [
        {"day": 30, "from_pond": 1, "to_pond": 2, "trigger_file": "results.dat"},
        {"day": 76, "from_pond": 1, "to_pond": 3, "trigger_file": "results3.dat"}, 
        {"day": 142, "from_pond": 1, "to_pond": 4, "trigger_file": "results6.dat"},
        {"day": 187, "from_pond": 1, "to_pond": 5, "trigger_file": "results9.dat"},
        {"day": 218, "from_pond": 1, "to_pond": 6, "trigger_file": "results12.dat"},
    ]
    
    print("TRANSFER TIMELINE:")
    print("-" * 50)
    for i, transfer in enumerate(transfers, 1):
        print(f"Transfer {i}: Day {transfer['day']:3d} - Pond {transfer['from_pond']} → Pond {transfer['to_pond']}")
    print()
    
    print("DETAILED FILE ANALYSIS:")
    print("-" * 50)
    
    for filename in sorted(file_descriptions.keys()):
        filepath = output_dir / filename
        if not filepath.exists():
            continue
            
        try:
            df = pd.read_csv(filepath, sep="\t")
            if df.empty:
                continue
                
            # Get time/step column (usually column 5 or 6)
            time_col = None
            for col in ["time", "Time", "step", "Step"]:
                if col in df.columns:
                    time_col = col
                    break
            if time_col is None:
                time_col = df.columns[5] if len(df.columns) > 5 else df.columns[0]
            
            start_day = float(df[time_col].iloc[0]) if not df.empty else 0
            end_day = float(df[time_col].iloc[-1]) if not df.empty else 0
            duration = end_day - start_day
            
            # Get mineral concentrations at the end
            halite_final = 0.0
            calcite_final = 0.0
            gypsum_final = 0.0
            
            for col in df.columns:
                if "halite" in col.lower():
                    halite_final = float(df[col].iloc[-1]) if not df[col].iloc[-1] == 0 else 0.0
                elif "calcite" in col.lower():
                    calcite_final = float(df[col].iloc[-1]) if not df[col].iloc[-1] == 0 else 0.0  
                elif "gypsum" in col.lower():
                    gypsum_final = float(df[col].iloc[-1]) if not df[col].iloc[-1] == 0 else 0.0
            
            print(f"{filename:15s} | {file_descriptions[filename]:45s}")
            print(f"                | Days {start_day:6.1f} - {end_day:6.1f} ({duration:5.1f} days duration)")
            print(f"                | Final minerals: Halite={halite_final:.4f}, Calcite={calcite_final:.4f}, Gypsum={gypsum_final:.4f}")
            print()
            
        except Exception as e:
            print(f"{filename:15s} | ERROR: {e}")
            print()
    
    print("POND SYSTEM SUMMARY:")
    print("-" * 50)
    print("• Pond 1: Primary concentrator - continuously evaporates and transfers concentrate")
    print("• Pond 2: 1st receiving pond - gets concentrate when Pond 1 reaches halite saturation")  
    print("• Pond 3: 2nd receiving pond - gets concentrate from Pond 1's continued operation")
    print("• Pond 4: 3rd receiving pond - gets concentrate from Pond 1's continued operation")
    print("• Pond 5: 4th receiving pond - gets concentrate from Pond 1's continued operation")
    print("• Pond 6: 5th receiving pond - gets concentrate from Pond 1's continued operation")
    print()
    print("OPERATIONAL LOGIC:")
    print("-" * 50)
    print("1. Pond 1 evaporates until halite formation triggers transfer")
    print("2. Concentrated brine transfers to next available pond")
    print("3. Pond 1 continues with fresh/diluted brine")
    print("4. Process repeats creating a cascade of increasingly concentrated ponds")
    print()
    print(f"TOTAL SIMULATION: {end_day:.0f} days ({end_day/365*12:.1f} months) with {len(transfers)} transfers")
    print("VARIABLE EVAPORATION: Using seasonal rates from inputs/evap_diaria.csv")

if __name__ == "__main__":
    analyze_transfers()
