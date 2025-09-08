from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
import pandas as pd
import re

from src.domain.models import Brine, Pond, MineralProps, Plant, SimulationParams


@dataclass
class InputData:
    plant: Plant
    params: SimulationParams
    volumes_m3: dict[str, float]


def load_input(brine_path: Path, ponds_path: Path, evap_schedule_path: Path = None, workspace: Path = None) -> InputData:
    # Legacy constants
    maxlevelallowed = 1.5  # m
    levellimit = 2.0       # m
    areas = {
        "Pond 1": 14168.0,
        "Pond 2": 14175.0,
        "Pond 3": 8510.5,
        "Pond 4": 8970.0,
        "Pond 5": 7815.0,
        "Pond 6": 7763.5,
    }

    brine = Brine.from_file(brine_path)

    # pondsData.txt may include a header row like: "volume\tm3"
    ponds_df = pd.read_csv(ponds_path, sep="\t", header=None)
    volumes_m3: dict[str, float] = {}
    ponds: list[Pond] = []

    def canon_name(name: str) -> str:
        m = re.search(r"(\d+)", str(name))
        return f"Pond {int(m.group(1))}" if m else str(name).strip().title()

    for i in range(len(ponds_df)):
        name_raw = str(ponds_df.iloc[i, 0]) if ponds_df.shape[1] > 0 else f"Pond {i+1}"
        name = canon_name(name_raw)
        val = ponds_df.iloc[i, 1] if ponds_df.shape[1] > 1 else 0.0
        try:
            vol = float(val)
        except Exception:
            # Skip header-like rows where volume column isn't numeric (e.g., 'm3')
            continue
        volumes_m3[name] = vol
        area = areas.get(name, 1.0)
        ponds.append(Pond(name=name, area_m2=area, init_level_m=maxlevelallowed, max_level_m=maxlevelallowed))

    minerals = {
        "Calcite": MineralProps("Calcite", 100.0869, 2700.0),
        "Halite": MineralProps("Halite", 58.44, 2170.0),
        "Gypsum": MineralProps("Gypsum", 136.14, 2320.0),
        "Water": MineralProps("Water", 18.01528, 1000.0),
    }

    params = SimulationParams(
        evaporation_rate_mol_per_day_L=0.273,  # match the constant we were testing
        level_limit_m=levellimit,
        nsteps_default_days=100,
        micro_steps_factor=1,  # no micro-stepping for variable schedules (1 step = 1 day)
        max_evap_step_mol_L=0.35,  # cap high summer rates for stability
        max_total_steps=365,  # allow full year simulation
    )

    # Optional daily evaporation schedule from config
    if evap_schedule_path and evap_schedule_path.exists():
        try:
            df_evap = pd.read_csv(evap_schedule_path)
            if "evap_mol_day_L" in df_evap.columns:
                schedule = df_evap["evap_mol_day_L"].astype(float).tolist()
                # Use original CSV values to see natural seasonal variation
                scale_factor = 1.0
                schedule = [rate * scale_factor for rate in schedule]
                avg_rate = sum(schedule) / len(schedule) if schedule else 0.272
                print(f"Loaded evaporation schedule from {evap_schedule_path.name}")
                print(f"Schedule: {len(schedule)} days, avg rate: {avg_rate:.3f} mol/day/L")
                print(f"Rate range: {min(schedule):.3f} to {max(schedule):.3f} mol/day/L")
                params.evap_schedule_mol_per_day_L = schedule
            else:
                print(f"Warning: evap_mol_day_L column not found in {evap_schedule_path}")
        except Exception as e:
            print(f"Failed to load evaporation schedule from {evap_schedule_path}: {e}")
    else:
        print("No evaporation schedule configured - using constant rate")

    plant = Plant(ponds=ponds, brine=brine, minerals=minerals)
    return InputData(plant=plant, params=params, volumes_m3=volumes_m3)
