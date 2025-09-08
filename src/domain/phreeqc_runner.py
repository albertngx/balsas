from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.workingTools import phreeqcModel


@dataclass
class PhreeqcJobSpec:
    """Specification for a PHREEQC simulation job.
    
    Defines all parameters needed to generate a PHREEQC input file section,
    including solution composition, reaction parameters, equilibrium phases,
    and output configuration.
    
    Attributes:
        solution_lines: Raw PHREEQC SOLUTION block lines (composition, pH, etc.)
        reaction_mols: Amount of water to evaporate in moles (negative for removal)
        reaction_steps: Number of reaction steps to distribute evaporation over
        eq_phases: List of equilibrium phase names (e.g., ['Halite', 'Gypsum'])
        results_file: Output filename for SELECTED_OUTPUT results
        save_solution_tag: Optional tag for saving solution state between jobs
        save_phases_tag: Optional tag for saving equilibrium phases state
    """
    solution_lines: list[str]
    reaction_mols: float
    reaction_steps: int
    eq_phases: list[str]
    results_file: str
    save_solution_tag: str | None = None
    save_phases_tag: str | None = None


class PhreeqcRunner:
    """PHREEQC simulation executor for evaporation pond modeling.
    
    Manages PHREEQC binary execution, input file generation, and output handling
    for multi-stage evaporation simulations. Provides both workspace discovery
    and explicit path configuration methods.
    
    Attributes:
        work_dir: Working directory for input files and temporary outputs
        output_dir: Directory for PHREEQC result files (work_dir/output)
        model: phreeqcModel instance configured with binary and database paths
    """
    
    def __init__(self, phreeqc_bin: str, phreeqc_db: str, work_dir: Path):
        """Initialize PhreeqcRunner with explicit paths.
        
        Args:
            phreeqc_bin: Path to PHREEQC executable binary
            phreeqc_db: Path to PHREEQC database file (e.g., phreeqc.dat)
            work_dir: Working directory for simulation files
        """
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        # ensure output subfolder
        self.output_dir = self.work_dir / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.model = phreeqcModel()
        self.model.phBin = phreeqc_bin
        self.model.phDb = phreeqc_db
        self.model.inputFile = str((self.work_dir / "input.in").resolve())
        self.model.outputFile = str((self.output_dir / "output.out").resolve())

    @classmethod
    def from_workspace(cls, workspace_root: Path | str, work_dir: Path | str | None = None) -> "PhreeqcRunner":
        """Create PhreeqcRunner by auto-discovering PHREEQC installation.
        
        Searches the workspace for PHREEQC installation directories (phreeqc-*)
        and automatically configures binary and database paths.
        
        Args:
            workspace_root: Root directory to search for PHREEQC installation
            work_dir: Working directory for simulation files (default: root/phreeqc_work)
            
        Returns:
            Configured PhreeqcRunner instance
            
        Raises:
            FileNotFoundError: If PHREEQC binary or database cannot be found
        """
        root = Path(workspace_root).resolve()
        bin_path: Path | None = None
        db_path: Path | None = None
        # Look for folders like 'phreeqc-3.5.0-14000', 'phreeqc-*'
        for d in sorted(root.iterdir()):
            if not d.is_dir():
                continue
            if not d.name.lower().startswith("phreeqc"):
                continue
            candidate_bin = d / "bin" / "phreeqc"
            if candidate_bin.exists():
                # Prefer legacy phreeqc.dat for parity, then Pitzer
                db_candidates = [
                    "phreeqc.dat",
                    "pitzer.dat",
                    "minteq.v4.dat",
                    "llnl.dat",
                ]
                for name in db_candidates:
                    candidate_db = d / "database" / name
                    if candidate_db.exists():
                        bin_path = candidate_bin
                        db_path = candidate_db
                        break
            if bin_path and db_path:
                break
        if not (bin_path and db_path):
            raise FileNotFoundError(
                f"Could not find PHREEQC bin/database under {root}. Expected phreeqc-*/bin/phreeqc and database/*.dat"
            )
        if work_dir is None:
            work_dir = root / "phreeqc_work"
        return cls(str(bin_path), str(db_path), Path(work_dir))

    @classmethod
    def from_paths(cls, phreeqc_bin: Path, phreeqc_database: Path, work_dir: Path | str | None = None) -> "PhreeqcRunner":
        """Create PhreeqcRunner with explicit PHREEQC paths.
        
        Preferred method when paths are known (e.g., from configuration files).
        Provides explicit control over PHREEQC binary and database selection.
        
        Args:
            phreeqc_bin: Path to PHREEQC executable
            phreeqc_database: Path to PHREEQC database file
            work_dir: Working directory for simulation files (default: ./experiment_results)
            
        Returns:
            Configured PhreeqcRunner instance
        """
        if work_dir is None:
            work_dir = Path.cwd() / "experiment_results"
        return cls(
            phreeqc_bin=phreeqc_bin,
            phreeqc_db=phreeqc_database,
            work_dir=Path(work_dir)
        )

    def _write_section(self, fh, text: str) -> None:
        """Write a text section to PHREEQC input file.
        
        Args:
            fh: File handle for writing
            text: Text content to write
        """
        fh.write(text)

    def build_input(self, jobs: Iterable[PhreeqcJobSpec]) -> Path:
        """Generate PHREEQC input file from job specifications.
        
        Creates a complete PHREEQC input file with multiple simulation jobs,
        each representing an evaporation stage with specific reaction parameters,
        equilibrium phases, and output configuration.
        
        Args:
            jobs: Iterable of PhreeqcJobSpec defining simulation stages
            
        Returns:
            Path to generated input file (work_dir/input.in)
            
        Note:
            - First job defines initial SOLUTION composition
            - Subsequent jobs use saved solution states
            - Each job generates separate SELECTED_OUTPUT file
            - Water removal simulated via negative REACTION
        """
        input_path = self.work_dir / "input.in"
        with open(input_path, "w", encoding="utf-8") as f:
            first = True
            for j in jobs:
                if first:
                    f.write("SOLUTION 1\n")
                    for line in j.solution_lines:
                        f.write(line)
                    first = False
                f.write("PHASES\n")
                f.write("Water\n")
                f.write("H2O = H2O\n")
                f.write("log_K 100\n")
                f.write("SAVE SOLUTION 1\n")
                f.write("END\n")
                f.write("USE SOLUTION 1\n")
                f.write("REACTION 1\n")
                f.write("Water\n")
                f.write(f"-{j.reaction_mols} mol in {j.reaction_steps} steps\n")
                f.write("INCREMENTAL_REACTIONS true\n")
                f.write("EQUILIBRIUM_PHASES 1\n")
                for ph in j.eq_phases:
                    f.write(f"{ph} 0.0 0.0\n")
                f.write("SELECTED_OUTPUT\n")
                # ensure results go into output dir
                f.write(f"-file {(self.output_dir / j.results_file).as_posix()}\n")
                f.write("-selected_out true\n")
                f.write("-step true\n")
                f.write("-ph true\n")
                f.write("-reaction true\n")
                f.write("-equilibrium_phases " + " ".join(j.eq_phases) + "\n")
                f.write("-totals Cl Na S K Ca Mg\n")
                if j.save_solution_tag:
                    f.write(f"SAVE SOLUTION {j.save_solution_tag}\n")
                if j.save_phases_tag:
                    f.write(f"SAVE EQUILIBRIUM_PHASES {j.save_phases_tag}\n")
                f.write("END\n")
        return input_path

    def run(self) -> None:
        """Execute PHREEQC simulation with current input file.
        
        Runs the PHREEQC binary using the configured paths and input file.
        Results are written to the output directory as specified in the
        SELECTED_OUTPUT sections of the input file.
        
        Raises:
            RuntimeError: If PHREEQC execution fails
            FileNotFoundError: If PHREEQC binary or database not found
        """
        self.model.runModel()
