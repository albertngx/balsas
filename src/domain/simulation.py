from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.domain.models import Pond, Plant, SimulationParams, MineralProps
from src.domain.phreeqc_runner import PhreeqcRunner, PhreeqcJobSpec


@dataclass
class Simulation:
    plant: Plant
    params: SimulationParams
    work_dir: Path

    def _evap_mols(self, days: int) -> float:
        return self.params.evaporation_rate_mol_per_day_L * days

    def _pond_volume_L(self, pond: Pond, level_m: float) -> float:
        return pond.area_m2 * level_m * 1000.0  # m3 to L

    def _get_column(self, df: pd.DataFrame, candidates: list[str], fallback_idx: int | None = None) -> pd.Series:
        cols_low = {c.lower(): c for c in df.columns}
        for name in candidates:
            c = cols_low.get(name.lower())
            if c is not None:
                return df[c]
        if fallback_idx is not None and fallback_idx < df.shape[1]:
            return df.iloc[:, fallback_idx]
        raise KeyError(f"None of the columns {candidates} found and no valid fallback index provided")

    def _find_phase_moles(self, df: pd.DataFrame, phase_name: str, fallback_idx: int | None) -> pd.Series:
        for col in df.columns:
            if phase_name.lower() in str(col).lower():
                return df[col]
        if fallback_idx is not None and fallback_idx < df.shape[1]:
            return df.iloc[:, fallback_idx]
        raise KeyError(f"Could not locate column for phase '{phase_name}' in selected output")

    def find_transfer_day_halite(self, df: pd.DataFrame) -> float | None:
        time = self._get_column(df, ["time", "Time", "step", "Step"], fallback_idx=5)
        halite = self._find_phase_moles(df, "Halite", fallback_idx=17)
        gt0 = halite[halite > 0]
        if not gt0.empty:
            first_idx = gt0.index[0]
            day = float(time.loc[first_idx])
            print(f"A transfer is advised at day {day}")
            return day
        return None

    def run_initial(self, runner: PhreeqcRunner) -> pd.DataFrame:
        days = self.params.nsteps_default_days
        evmols = self._evap_mols(days)
        job = PhreeqcJobSpec(
            solution_lines=self.plant.brine.phreeqc_solution_lines,
            reaction_mols=evmols,
            reaction_steps=days,
            eq_phases=["Calcite", "Gypsum", "Halite"],
            results_file="results.dat",
        )
        runner.build_input([job])
        runner.run()
        df = pd.read_csv(runner.output_dir / "results.dat", sep="\t")
        self.find_transfer_day_halite(df)
        return df

    def _write_solution_header(self, fh) -> None:
        fh.write("SOLUTION 1\n")
        for line in self.plant.brine.phreeqc_solution_lines:
            fh.write(line)
        fh.write("PHASES\n")
        fh.write("Water\n")
        fh.write("H2O = H2O\n")
        fh.write("log_K 100\n")
        fh.write("SAVE SOLUTION 1\n")
        fh.write("END\n")

    def _write_reaction_block(
        self,
        fh,
        *,
        reaction_id: int,
        steps: int,
        ev_mols: float,
        results_file: str,
        eq_phases_id: int | None = 1,
        use_solution_tag: str | None = None,
        use_phases_tag: str | None = None,
        save_solution_tag: str | None = None,
        save_phases_tag: str | None = None,
        schedule_start_day: int | None = None,
    ) -> None:
        """Write a PHREEQC reaction block.
        If use_phases_tag is provided, reuse that saved EQUILIBRIUM_PHASES set and do NOT redefine a new set.
        Only define a new EQUILIBRIUM_PHASES when not reusing an existing one.
        When an evaporation schedule is provided, slice it with an absolute day offset.
        """
        factor = max(1, int(self.params.micro_steps_factor))
        total_steps = steps * factor
        if use_solution_tag:
            fh.write(f"USE SOLUTION {use_solution_tag}\n")
        else:
            fh.write("USE SOLUTION 1\n")
        if use_phases_tag:
            fh.write(f"USE EQUILIBRIUM_PHASES {use_phases_tag}\n")
        fh.write(f"REACTION {reaction_id}\n")
        fh.write("Water\n")
        # If a variable daily schedule is present, emit a line with variable increments
        if self.params.evap_schedule_mol_per_day_L and steps > 0:
            start = int(schedule_start_day or 0)
            end = start + steps
            full = self.params.evap_schedule_mol_per_day_L
            # Clip to available schedule, pad with last known value if needed
            sched = full[start:end]
            if len(sched) < steps:
                fill = full[-1] if len(full) > 0 else self.params.evaporation_rate_mol_per_day_L
                sched = sched + [fill] * (steps - len(sched))
            print(f"Using schedule slice [{start}:{end}] = {len(sched)} days, first few: {sched[:5]}")
            
            # For variable schedules, maintain 1 step = 1 day relationship
            # Cap individual rates if they're too high for stability
            max_step = self.params.max_evap_step_mol_L or float('inf')
            if max_step < float('inf'):
                sched = [min(rate, max_step) for rate in sched]
                print(f"Capped rates above {max_step}, range now: {min(sched):.3f} to {max(sched):.3f}")
            
            # Cap total days to prevent PHREEQC overload
            if len(sched) > self.params.max_total_steps:
                print(f"WARNING: Capping {len(sched)} days to {self.params.max_total_steps}")
                sched = sched[:self.params.max_total_steps]
            
            sched_line = " ".join(f"-{x}" for x in sched)
            fh.write(f"{sched_line}\n")
            fh.write("INCREMENTAL_REACTIONS true\n")
        else:
            # Keep total mol removed equal to ev_mols, just increase steps for stability
            fh.write(f"-{ev_mols} mol in {total_steps} steps\n")
            fh.write("INCREMENTAL_REACTIONS true\n")
        # Define an EQUILIBRIUM_PHASES set only if not reusing an existing one
        if eq_phases_id is not None and not use_phases_tag:
            fh.write(f"EQUILIBRIUM_PHASES {eq_phases_id}\n")
            fh.write("Calcite 0.0 0.0\n")
            fh.write("Gypsum 0.0 0.0\n")
            fh.write("Halite 0.0 0.0\n")
        fh.write("SELECTED_OUTPUT\n")
        fh.write(f"-file {results_file}\n")
        fh.write("-selected_out true\n")
        fh.write("-step true\n")
        fh.write("-ph true\n")
        fh.write("-reaction true\n")
        fh.write("-equilibrium_phases Calcite Halite Gypsum\n")
        fh.write("-totals Cl Na S K Ca Mg\n")
        if save_solution_tag:
            fh.write(f"SAVE SOLUTION {save_solution_tag}\n")
        if save_phases_tag:
            fh.write(f"SAVE EQUILIBRIUM_PHASES {save_phases_tag}\n")
        fh.write("END\n")

    def run_full_pipeline(self, runner: PhreeqcRunner, max_stages: int = 12) -> tuple[dict[str, pd.DataFrame], dict[str, int]]:
        """Replicate the legacy Codev1 staged orchestration with SAVE/USE tags and halite-triggered transfers.
        Produces the same results*.dat files as the legacy script. Also returns a mapping of results file -> absolute start day.
        """
        outputs: dict[str, pd.DataFrame] = {}
        stage_start_days: dict[str, int] = {}
        input_path = runner.work_dir / "input.in"

        # 1) Initial POND 1 evolution (100 days) -> results.dat and tr1
        with open(input_path, "w", encoding="utf-8") as f:
            self._write_solution_header(f)
            self._write_reaction_block(
                f,
                reaction_id=1,
                steps=self.params.nsteps_default_days,
                ev_mols=self._evap_mols(self.params.nsteps_default_days),
                results_file=(runner.output_dir / "results.dat").as_posix(),
                eq_phases_id=1,
                schedule_start_day=0,
            )
        runner.run()
        df1 = pd.read_csv(runner.output_dir / "results.dat", sep="\t")
        outputs["results.dat"] = df1
        stage_start_days["results.dat"] = 0
        tr1_local = self.find_transfer_day_halite(df1)
        if tr1_local is None:
            return outputs, stage_start_days
        tr1 = int(max(1, int(tr1_local)))

        # 2) Prepare transfer to POND 2 at day tr1, then full 100d in POND 2 -> results2.dat
        with open(input_path, "w", encoding="utf-8") as f:
            self._write_solution_header(f)
            # Short run to transfer point; save SOLUTION 2 and EQ 1 (uses days 0..tr1-1)
            self._write_reaction_block(
                f,
                reaction_id=1,
                steps=tr1,
                ev_mols=self._evap_mols(tr1),
                results_file=(runner.output_dir / "results.dat").as_posix(),
                eq_phases_id=1,
                save_solution_tag="2",
                save_phases_tag="1",
                schedule_start_day=0,
            )
            # Transfer into POND 2, 100 days (uses days tr1..tr1+99)
            self._write_reaction_block(
                f,
                reaction_id=2,
                steps=self.params.nsteps_default_days,
                ev_mols=self._evap_mols(self.params.nsteps_default_days),
                results_file=(runner.output_dir / "results2.dat").as_posix(),
                eq_phases_id=100,
                use_solution_tag="2",
                schedule_start_day=tr1,
            )
        runner.run()
        df2 = pd.read_csv(runner.output_dir / "results2.dat", sep="\t")
        outputs["results2.dat"] = df2
        stage_start_days["results2.dat"] = tr1

        # 3) Evolution of POND 1 after transfer to POND 2 (100 days) -> results3.dat, get tr2 (uses days tr1..tr1+99)
        with open(input_path, "a", encoding="utf-8") as f:
            self._write_reaction_block(
                f,
                reaction_id=3,
                steps=self.params.nsteps_default_days,
                ev_mols=self._evap_mols(self.params.nsteps_default_days),
                results_file=(runner.output_dir / "results3.dat").as_posix(),
                eq_phases_id=101,
                use_solution_tag="1",
                use_phases_tag="1",
                schedule_start_day=tr1,
            )
        runner.run()
        df3 = pd.read_csv(runner.output_dir / "results3.dat", sep="\t")
        outputs["results3.dat"] = df3
        stage_start_days["results3.dat"] = tr1
        tr2_local = self.find_transfer_day_halite(df3)
        if tr2_local is None:
            return outputs, stage_start_days
        tr2 = int(tr1 + int(max(1, int(tr2_local))))

        # 4) Transfer to POND 3: short run on POND 1 to (tr2 - tr1), save SOLUTION 3/EQ 2 -> results4.dat; then 100d in POND 3 -> results5.dat
        with open(input_path, "a", encoding="utf-8") as f:
            # Short run (charge) on POND 1 (uses days tr1..tr2-1)
            self._write_reaction_block(
                f,
                reaction_id=4,
                steps=tr2 - tr1,
                ev_mols=self._evap_mols(tr2 - tr1),
                results_file=(runner.output_dir / "results4.dat").as_posix(),
                eq_phases_id=2,
                use_solution_tag="1",
                use_phases_tag="1",
                save_solution_tag="3",
                save_phases_tag="2",
                schedule_start_day=tr1,
            )
            # POND 3 evolution 100 days (uses days tr2..tr2+99)
            self._write_reaction_block(
                f,
                reaction_id=5,
                steps=self.params.nsteps_default_days,
                ev_mols=self._evap_mols(self.params.nsteps_default_days),
                results_file=(runner.output_dir / "results5.dat").as_posix(),
                eq_phases_id=102,
                use_solution_tag="3",
                schedule_start_day=tr2,
            )
        runner.run()
        try:
            outputs["results4.dat"] = pd.read_csv(runner.output_dir / "results4.dat", sep="\t")
        except Exception:
            pass
        df5 = pd.read_csv(runner.output_dir / "results5.dat", sep="\t")
        outputs["results5.dat"] = df5
        stage_start_days["results5.dat"] = tr2

        # 5) Evolution of POND 1 after transfer to POND 3 (100 days) -> results6.dat, get tr3 (uses days tr2..tr2+99)
        with open(input_path, "a", encoding="utf-8") as f:
            self._write_reaction_block(
                f,
                reaction_id=6,
                steps=self.params.nsteps_default_days,
                ev_mols=self._evap_mols(self.params.nsteps_default_days),
                results_file=(runner.output_dir / "results6.dat").as_posix(),
                eq_phases_id=103,
                use_solution_tag="1",
                use_phases_tag="2",
                schedule_start_day=tr2,
            )
        runner.run()
        df6 = pd.read_csv(runner.output_dir / "results6.dat", sep="\t")
        outputs["results6.dat"] = df6
        stage_start_days["results6.dat"] = tr2
        tr3_local = self.find_transfer_day_halite(df6)
        if tr3_local is None:
            return outputs, stage_start_days
        tr3 = int(tr2 + int(max(1, int(tr3_local))))

        # 6) Transfer to POND 4: short run on POND 1 to (tr3 - tr2), save SOLUTION 4/EQ 3 -> results7.dat; then 100d in POND 4 -> results8.dat
        with open(input_path, "a", encoding="utf-8") as f:
            self._write_reaction_block(
                f,
                reaction_id=7,
                steps=tr3 - tr2,
                ev_mols=self._evap_mols(tr3 - tr2),
                results_file=(runner.output_dir / "results7.dat").as_posix(),
                eq_phases_id=3,
                use_solution_tag="1",
                use_phases_tag="2",
                save_solution_tag="4",
                save_phases_tag="3",
                schedule_start_day=tr2,
            )
            self._write_reaction_block(
                f,
                reaction_id=8,
                steps=self.params.nsteps_default_days,
                ev_mols=self._evap_mols(self.params.nsteps_default_days),
                results_file=(runner.output_dir / "results8.dat").as_posix(),
                eq_phases_id=104,
                use_solution_tag="4",
                schedule_start_day=tr3,
            )
        runner.run()
        try:
            outputs["results7.dat"] = pd.read_csv(runner.output_dir / "results7.dat", sep="\t")
        except Exception:
            pass
        df8 = pd.read_csv(runner.output_dir / "results8.dat", sep="\t")
        outputs["results8.dat"] = df8
        stage_start_days["results8.dat"] = tr3

        # 7) Evolution of POND 1 after transfer to POND 4 (100 days) -> results9.dat, get tr4 (uses days tr3..tr3+99)
        with open(input_path, "a", encoding="utf-8") as f:
            self._write_reaction_block(
                f,
                reaction_id=9,
                steps=self.params.nsteps_default_days,
                ev_mols=self._evap_mols(self.params.nsteps_default_days),
                results_file=(runner.output_dir / "results9.dat").as_posix(),
                eq_phases_id=105,
                use_solution_tag="1",
                use_phases_tag="3",
                schedule_start_day=tr3,
            )
        runner.run()
        df9 = pd.read_csv(runner.output_dir / "results9.dat", sep="\t")
        outputs["results9.dat"] = df9
        stage_start_days["results9.dat"] = tr3
        tr4_local = self.find_transfer_day_halite(df9)
        if tr4_local is None:
            return outputs, stage_start_days
        tr4 = int(tr3 + int(max(1, int(tr4_local))))

        # 8) Transfer to POND 5: short run on POND 1 to (tr4 - tr3), save SOLUTION 5/EQ 4 -> results10.dat; then 100d in POND 5 -> results11.dat
        with open(input_path, "a", encoding="utf-8") as f:
            self._write_reaction_block(
                f,
                reaction_id=10,
                steps=tr4 - tr3,
                ev_mols=self._evap_mols(tr4 - tr3),
                results_file=(runner.output_dir / "results10.dat").as_posix(),
                eq_phases_id=4,
                use_solution_tag="1",
                use_phases_tag="3",
                save_solution_tag="5",
                save_phases_tag="4",
                schedule_start_day=tr3,
            )
            self._write_reaction_block(
                f,
                reaction_id=11,
                steps=self.params.nsteps_default_days,
                ev_mols=self._evap_mols(self.params.nsteps_default_days),
                results_file=(runner.output_dir / "results11.dat").as_posix(),
                eq_phases_id=106,
                use_solution_tag="5",
                schedule_start_day=tr4,
            )
        runner.run()
        try:
            outputs["results10.dat"] = pd.read_csv(runner.output_dir / "results10.dat", sep="\t")
        except Exception:
            pass
        df11 = pd.read_csv(runner.output_dir / "results11.dat", sep="\t")
        outputs["results11.dat"] = df11
        stage_start_days["results11.dat"] = tr4

        # 9) Evolution of POND 1 after transfer to POND 5 (100 days) -> results12.dat, get tr5 (uses days tr4..tr4+99)
        with open(input_path, "a", encoding="utf-8") as f:
            self._write_reaction_block(
                f,
                reaction_id=12,
                steps=self.params.nsteps_default_days,
                ev_mols=self._evap_mols(self.params.nsteps_default_days),
                results_file=(runner.output_dir / "results12.dat").as_posix(),
                eq_phases_id=107,
                use_solution_tag="1",
                use_phases_tag="4",
                schedule_start_day=tr4,
            )
        runner.run()
        df12 = pd.read_csv(runner.output_dir / "results12.dat", sep="\t")
        outputs["results12.dat"] = df12
        stage_start_days["results12.dat"] = tr4
        tr5_local = self.find_transfer_day_halite(df12)
        if tr5_local is None:
            return outputs, stage_start_days
        tr5 = int(tr4 + int(max(1, int(tr5_local))))

        # 10) Transfer to POND 6: short run on POND 1 to (tr5 - tr4), save SOLUTION 6/EQ 5 -> results13.dat; then 100d in POND 6 -> results14.dat
        with open(input_path, "a", encoding="utf-8") as f:
            # Short run to reach transfer 5 (uses days tr4..tr5-1)
            self._write_reaction_block(
                f,
                reaction_id=13,
                steps=tr5 - tr4,
                ev_mols=self._evap_mols(tr5 - tr4),
                results_file=(runner.output_dir / "results13.dat").as_posix(),
                eq_phases_id=5,
                use_solution_tag="1",
                use_phases_tag="4",
                save_solution_tag="6",
                save_phases_tag="5",
                schedule_start_day=tr4,
            )
            # Pond 6 evolution 100 days (uses days tr5..tr5+99)
            self._write_reaction_block(
                f,
                reaction_id=14,
                steps=self.params.nsteps_default_days,
                ev_mols=self._evap_mols(self.params.nsteps_default_days),
                results_file=(runner.output_dir / "results14.dat").as_posix(),
                eq_phases_id=108,
                use_solution_tag="6",
                schedule_start_day=tr5,
            )
        runner.run()
        try:
            outputs["results13.dat"] = pd.read_csv(runner.output_dir / "results13.dat", sep="\t")
            stage_start_days["results13.dat"] = tr4
        except Exception:
            pass
        df14 = pd.read_csv(runner.output_dir / "results14.dat", sep="\t")
        outputs["results14.dat"] = df14
        stage_start_days["results14.dat"] = tr5

        return outputs, stage_start_days
