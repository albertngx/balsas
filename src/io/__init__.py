"""Input/output handling for salina evaporation simulation.

This package contains data loaders for brine composition, pond specifications,
and evaporation schedules used in the PHREEQC-based pond simulation system.
"""

from .loaders import load_input, InputData

__all__ = ["load_input", "InputData"]
