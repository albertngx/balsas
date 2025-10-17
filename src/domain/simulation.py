from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

import pandas as pd

from src.domain.models import Pond, Plant, SimulationParams, MineralProps
from src.domain.phreeqc_runner import PhreeqcRunner, PhreeqcJobSpec


@dataclass
class Simulation:
    plant: Plant
    params: SimulationParams
    work_dir: Path

    # ====================== Utilidades internas ======================

    def _evap_mols(self, days: int) -> float:
        return self.params.evaporation_rate_mol_per_day_L * days

    def _pond_volume_L(self, pond: Pond, level_m: float) -> float:
        return pond.area_m2 * level_m * 1000.0  # m3 -> L

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

    # --------- NUEVO: volumen restante a partir del SELECTED_OUTPUT ---------

    def _remaining_vol_from_output(self, df: pd.DataFrame, target_day: int) -> float:
        """
        Calcula el volumen restante en Pond1 (m3) en el día 'target_day' usando:
          - Columna 'reaction' (moles de H2O evaporados acumulados) del SELECTED_OUTPUT
          - initial_pond1_m3 (m3) desde params/config (o capacidad de pond1 si falta)
          - liquid_density_g_per_L (g/L) desde params/config (por defecto 1000)
        Fórmula:
            evap_L = n_evap_mol * 18.01528 (g/mol) / rho (g/L)
            remaining_m3 = max(init_m3 - evap_L/1000, 0)
        """
        # Volumen inicial
        init = getattr(self.params, "initial_pond1_m3", None)
        if init is None:
            caps = getattr(self.params, "pond_capacities_m3", None) or getattr(self.params, "params", {}).get("pond_capacities_m3", {})
            init = float(caps.get("pond1", 0.0))

        # Densidad (g/L)
        rho = getattr(self.params, "liquid_density_g_per_L", None)
        if rho is None:
            rho = getattr(self.params, "params", {}).get("liquid_density_g_per_L", 1000.0)
        rho = float(rho)

        # Series tiempo y reacción (mol H2O)
        time = self._get_column(df, ["time", "Time", "step", "Step", "reaction", "Reaction"], fallback_idx=5)
        reaction = self._get_column(df, ["reaction", "Reaction"], fallback_idx=6)
        t_num = pd.to_numeric(time, errors="coerce")
        r_num = pd.to_numeric(reaction, errors="coerce")

        # Elegir el primer registro con t >= target_day; si no existe, usar el último
        mask = t_num >= float(target_day)
        if mask.any():
            n_evap_mol = float(r_num[mask].dropna().iloc[0])
        else:
            n_evap_mol = float(r_num.dropna().iloc[-1])

        evap_L = n_evap_mol * 18.01528 / rho  # L
        remaining_m3 = max(float(init) - (evap_L / 1000.0), 0.0)

        print(
            f"[POND1 REMAINING] day={target_day} | init={init:.6f} m3 | "
            f"n_evap={n_evap_mol:.6f} mol | rho={rho:.1f} g/L | evap_L={evap_L:.6f} L | "
            f"remaining={remaining_m3:.6f} m3"
        )
        return remaining_m3

    # --------- Control de capacidad (destino vacío, descartar exceso) ---------

    def _cap_transfer(self, source_pond: str, target_pond: str, requested_m3: float) -> Tuple[float, float]:
        """
        Política 'discard_excess' con capacidades máximas (destino vacío).
        Devuelve (allowed_m3, discarded_m3) e imprime el resultado.
        """
        # Capacidades esperadas como dict: {'pond1': m3, ...}
        caps = None
        try:
            caps = getattr(self.params, "pond_capacities_m3", None)
        except Exception:
            caps = None
        if caps is None:
            caps = getattr(self.params, "params", {}).get("pond_capacities_m3", None)

        policy = "discard_excess"
        try:
            policy = getattr(self.params, "transfer_policy", policy)
        except Exception:
            pass

        if not caps or target_pond not in caps:
            print(f"[TRANSFER CHECK] No capacities; assuming no cap: requested={requested_m3:.8f} m3")
            return float(requested_m3), 0.0

        target_max = float(caps[target_pond])
        allowed = min(float(requested_m3), target_max)
        discarded = max(float(requested_m3) - allowed, 0.0)

        print(
            f"[TRANSFER CAPACITY] {source_pond} -> {target_pond} | "
            f"requested={requested_m3:.8f} m3 | target_max={target_max:.8f} m3 | "
            f"allowed={allowed:.8f} m3 | DISCARDED={discarded:.8f} m3 | policy={policy}"
        )
        return allowed, discarded

    # ===================== Bloques y pipeline =====================

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
        """Write a PHREEQC reaction block."""
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

        # Si hay schedule en mol/L/día, emitir incrementos diarios
        if self.params.evap_schedule_mol_per_day_L and steps > 0:
            start = int(schedule_start_day or 0)
            end = start + steps
            full = self.params.evap_schedule_mol_per_day_L
            sched = full[start:end]
            if len(sched) < steps:
                fill = full[-1] if len(full) > 0 else self.params.evaporation_rate_mol_per_day_L
                sched = sched + [fill] * (steps - len(sched))
            print(f"Using schedule slice [{start}:{end}] = {len(sched)} days, first few: {sched[:5]}")

            # Cap por estabilidad numérica (si procede)
            max_step = self.params.max_evap_step_mol_L or float('inf')
            if max_step < float('inf'):
                sched = [min(rate, max_step) for rate in sched]
                print(f"Capped rates above {max_step}, range now: {min(sched):.3f} to {max(sched):.3f}")

            # Cap al nº total de pasos
            if len(sched) > self.params.max_total_steps:
                print(f"WARNING: Capping {len(sched)} days to {self.params.max_total_steps}")
                sched = sched[:self.params.max_total_steps]

            sched_line = " ".join(f"-{x}" for x in sched)
            fh.write(f"{sched_line}\n")
            fh.write("INCREMENTAL_REACTIONS true\n")
        else:
            # Mantener moles totales, con más pasos para estabilidad
            fh.write(f"-{ev_mols} mol in {total_steps} steps\n")
            fh.write("INCREMENTAL_REACTIONS true\n")

        # EQUILIBRIUM_PHASES sólo si no reutilizamos una existente
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
        """Pipeline por etapas (equivalente al legacy)."""
        outputs: dict[str, pd.DataFrame] = {}
        stage_start_days: dict[str, int] = {}
        input_path = runner.work_dir / "input.in"

        # 1) Pond 1 inicial (100 días) -> results.dat y tr1
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

        # Volumen restante en Pond1 al día tr1 (m3)
        requested_12 = self._remaining_vol_from_output(df1, tr1)

        # 2) Transfer a Pond 2 y evolución 100 días -> results2.dat
        with open(input_path, "w", encoding="utf-8") as f:
            self._write_solution_header(f)
            # Carga hasta el punto de transferencia; guardamos SOLUTION 2 / EQ 1
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
            # Control de capacidad y descarte: Pond1 -> Pond2
            self._cap_transfer("pond1", "pond2", requested_12)
            # Evolución Pond 2 (100 días)
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

        # 3) Pond 1 tras transfer a Pond 2 (100 días) -> results3.dat, obtener tr2
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

        # Volumen restante al día tr2
        requested_13 = self._remaining_vol_from_output(df3, tr2)

        # 4) Transfer a Pond 3 (carga hasta tr2-tr1) -> results4.dat; evolución Pond 3 100d -> results5.dat
        with open(input_path, "a", encoding="utf-8") as f:
            # Carga adicional en Pond 1
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
            # Control: Pond1 -> Pond3
            self._cap_transfer("pond1", "pond3", requested_13)
            # Evolución Pond 3
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

        # 5) Pond 1 tras transfer a Pond 3 (100 días) -> results6.dat, obtener tr3
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

        # Volumen restante al día tr3
        requested_14 = self._remaining_vol_from_output(df6, tr3)

        # 6) Transfer a Pond 4 -> results7.dat / results8.dat
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
            # Control: Pond1 -> Pond4
            self._cap_transfer("pond1", "pond4", requested_14)
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

        # 7) Pond 1 tras transfer a Pond 4 (100 días) -> results9.dat, obtener tr4
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

        # Volumen restante al día tr4
        requested_15 = self._remaining_vol_from_output(df9, tr4)

        # 8) Transfer a Pond 5 -> results10.dat / results11.dat
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
            # Control: Pond1 -> Pond5
            self._cap_transfer("pond1", "pond5", requested_15)
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

        # 9) Pond 1 tras transfer a Pond 5 (100 días) -> results12.dat, obtener tr5
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

        # Volumen restante al día tr5
        requested_16 = self._remaining_vol_from_output(df12, tr5)

        # 10) Transfer a Pond 6 -> results13.dat / results14.dat
        with open(input_path, "a", encoding="utf-8") as f:
            # Carga hasta tr5
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
            # Control: Pond1 -> Pond6
            self._cap_transfer("pond1", "pond6", requested_16)
            # Evolución Pond 6
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
