"""
Configuration loader for environment settings (portable version).
"""
from pathlib import Path
import yaml
import os
from typing import Dict, Any


def load_config(config_path: Path = None) -> Dict[str, Any]:
    """Load configuration from config.yaml file."""
    if config_path is None:
        config_path = Path.cwd() / "config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Allow environment variables to override YAML entries
    config["phreeqc_bin"] = os.getenv("PHREEQC_BIN", config.get("phreeqc_bin"))
    config["phreeqc_database"] = os.getenv("PHREEQC_DB", config.get("phreeqc_database"))

    return config


def resolve_path(config: Dict[str, Any], key: str, workspace_root: Path) -> Path:
    """Resolve a path from config relative to workspace root."""
    relative_path = config.get(key)
    if not relative_path:
        raise KeyError(f"Missing configuration key: {key}")

    # If path is absolute, use it directly
    path = Path(relative_path)
    if path.is_absolute():
        return path
    return workspace_root / path


def get_phreeqc_paths(config: Dict[str, Any], workspace_root: Path) -> tuple[Path, Path]:
    """Get PHREEQC binary and database paths (checking overrides)."""
    phreeqc_bin = resolve_path(config, "phreeqc_bin", workspace_root)
    phreeqc_db = resolve_path(config, "phreeqc_database", workspace_root)

    if not phreeqc_bin.exists():
        raise FileNotFoundError(f"PHREEQC binary not found: {phreeqc_bin}")
    if not phreeqc_db.exists():
        raise FileNotFoundError(f"PHREEQC database not found: {phreeqc_db}")

    return phreeqc_bin, phreeqc_db


def get_data_paths(config: Dict[str, Any], workspace_root: Path) -> tuple[Path, Path]:
    """Get brine and ponds data paths from config."""
    brine_path = resolve_path(config, "brine_data", workspace_root)
    ponds_path = resolve_path(config, "ponds_data", workspace_root)

    if not brine_path.exists():
        raise FileNotFoundError(f"Brine data file not found: {brine_path}")
    if not ponds_path.exists():
        raise FileNotFoundError(f"Ponds data file not found: {ponds_path}")

    return brine_path, ponds_path


def get_evaporation_schedule_path(config: Dict[str, Any], workspace_root: Path) -> Path:
    """Get evaporation schedule path from config."""
    schedule_path = resolve_path(config, "evaporation_schedule", workspace_root)

    if not schedule_path.exists():
        raise FileNotFoundError(f"Evaporation schedule file not found: {schedule_path}")

    return schedule_path
