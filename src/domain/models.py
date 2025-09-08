from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class MineralProps:
    """Properties of a mineral phase for geochemical calculations.
    
    Used to track mineral formation, calculate volumes, and analyze
    precipitation patterns in evaporation pond systems.
    
    Attributes:
        name: Mineral name (e.g., 'Halite', 'Gypsum', 'Calcite')
        molar_mass_g_mol: Molecular weight in grams per mole
        density_kg_m3: Bulk density in kilograms per cubic meter
    """
    name: str
    molar_mass_g_mol: float
    density_kg_m3: float


@dataclass
class Pond:
    """Evaporation pond with physical dimensions and level tracking.
    
    Represents a single pond in the cascade system, storing its physical
    properties and maintaining a history of liquid and solid levels over time.
    
    Attributes:
        name: Pond identifier (e.g., 'P1', 'P2', etc.)
        area_m2: Surface area in square meters
        init_level_m: Initial liquid level in meters
        max_level_m: Maximum operational level in meters
        level_history: Time series of liquid levels (meters)
        solids_level_history: Time series of accumulated solid levels (meters)
    """
    name: str
    area_m2: float
    init_level_m: float
    max_level_m: float
    level_history: list[float] = field(default_factory=list)
    solids_level_history: list[float] = field(default_factory=list)

    def record_levels(self, liquid_level: float, solids_level: float) -> None:
        """Record liquid and solid levels for this time step.
        
        Args:
            liquid_level: Current liquid level in meters
            solids_level: Current accumulated solids level in meters
        """
        self.level_history.append(liquid_level)
        self.solids_level_history.append(solids_level)


@dataclass
class Brine:
    """Brine composition for PHREEQC geochemical modeling.
    
    Encapsulates the initial brine chemistry as PHREEQC SOLUTION format lines,
    ready for direct use in PHREEQC input files without modification.
    
    Attributes:
        phreeqc_solution_lines: Raw PHREEQC SOLUTION block lines including
                               headers, ionic concentrations, pH, temperature, etc.
    """
    phreeqc_solution_lines: list[str]

    @classmethod
    def from_file(cls, path: Path) -> "Brine":
        """Load brine composition from a PHREEQC SOLUTION format file.
        
        Args:
            path: Path to file containing PHREEQC SOLUTION block
            
        Returns:
            Brine instance with loaded composition data
        """
        with open(path, "r", encoding="utf-8") as f:
            return cls(phreeqc_solution_lines=f.readlines())


@dataclass
class SimulationParams:
    """Parameters controlling evaporation simulation behavior.
    
    Defines evaporation rates, time stepping, convergence controls, and
    computational limits for PHREEQC-based pond simulations.
    
    Attributes:
        evaporation_rate_mol_per_day_L: Base evaporation rate (mol H2O per day per liter)
        level_limit_m: Maximum liquid level before triggering transfers
        nsteps_default_days: Default simulation duration in days
        micro_steps_factor: Sub-daily time step multiplier for convergence (1 = daily steps)
        evap_schedule_mol_per_day_L: Optional seasonal evaporation schedule overriding
                                   constant rate (365 values for daily variation)
        max_evap_step_mol_L: Optional cap on evaporation per PHREEQC step to prevent
                           convergence failures from excessive concentration jumps
        max_total_steps: Maximum PHREEQC steps to prevent runaway simulations
    """
    evaporation_rate_mol_per_day_L: float
    level_limit_m: float
    nsteps_default_days: int = 100
    micro_steps_factor: int = 1
    evap_schedule_mol_per_day_L: Optional[List[float]] = None
    max_evap_step_mol_L: Optional[float] = None
    max_total_steps: int = 500


@dataclass
class Plant:
    """Complete evaporation pond facility model.
    
    Represents the entire salt production facility including all ponds,
    initial brine composition, and mineral property database for the
    6-pond cascade system.
    
    Attributes:
        ponds: List of all ponds in the system (typically P1-P6)
        brine: Initial brine composition for fresh inputs
        minerals: Database of mineral properties for volume calculations
                 and precipitation analysis
    """
    ponds: list[Pond]
    brine: Brine
    minerals: dict[str, MineralProps]

    def get_pond(self, name: str) -> Pond:
        """Retrieve a pond by name.
        
        Args:
            name: Pond identifier (e.g., 'P1', 'P2')
            
        Returns:
            Pond instance with matching name
            
        Raises:
            KeyError: If pond name not found in facility
        """
        for p in self.ponds:
            if p.name == name:
                return p
        raise KeyError(name)
