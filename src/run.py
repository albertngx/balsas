from __future__ import annotations

from pathlib import Path
import argparse
import pandas as pd

from src.domain.phreeqc_runner import PhreeqcRunner
from src.domain.simulation import Simulation
from src.io.loaders import load_input
from src.utils.plots import plot_mineral_masses
from src.utils.plots import plot_overlay
from src.utils.analysis import print_transfer_summary
from src.utils.config import load_config, get_phreeqc_paths, get_data_paths, get_evaporation_schedule_path, resolve_path



def _time_series(df: pd.DataFrame) -> pd.Series:
    # Try common time/step columns first, then fall back to 6th column
    for name in ("time", "Time", "step", "Step", "reaction", "Reaction"):
        if name in df.columns:
            s = pd.to_numeric(df[name], errors="coerce")
            break
    else:
        s = pd.to_numeric(df.iloc[:, 5], errors="coerce")
    return s.fillna(method="ffill").fillna(0)


def main():
    parser = argparse.ArgumentParser(description="Run salina evaporation simulation")
    parser.add_argument("--workspace", type=str, default=str(Path.cwd()), help="Workspace root directory")
    parser.add_argument("--config", type=str, default="env.yaml", help="Configuration file path")
    parser.add_argument("--plot", action="store_true", help="Plot preview for the first stage")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    config_path = workspace / args.config
    
    # Load configuration
    config = load_config(config_path)
    
    # Get paths from configuration
    phreeqc_bin, phreeqc_db = get_phreeqc_paths(config, workspace)
    brine_path, ponds_path = get_data_paths(config, workspace)
    work_dir = resolve_path(config, "work_dir", workspace)
    
    # Get evaporation schedule path
    try:
        evap_schedule_path = get_evaporation_schedule_path(config, workspace)
    except FileNotFoundError:
        evap_schedule_path = None

    runner = PhreeqcRunner.from_paths(
        phreeqc_bin=phreeqc_bin,
        phreeqc_database=phreeqc_db,
        work_dir=work_dir
    )

    data = load_input(brine_path, ponds_path, evap_schedule_path=evap_schedule_path)

    sim = Simulation(plant=data.plant, params=data.params, work_dir=work_dir)

    # Execute the new multi-stage pipeline
    outputs, stage_start_days = sim.run_full_pipeline(runner)

    print(f"Generated {len(outputs)} result files in {runner.output_dir}:")
    for fname in outputs.keys():
        print(f" - {runner.output_dir / fname}")

    # Print comprehensive transfer summary
    print_transfer_summary(outputs, stage_start_days, runner.output_dir)

    # Always save plots under work_dir/plots (same level as 'output')
    plots_dir = Path(runner.work_dir) / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    # Only plot the final stages per pond: 1 (initial), 2, 3, 4, 5, 6
    final_stage_files = [
        ("results.dat", 1),    # Pond 1 initial 100d
        ("results2.dat", 2),   # Pond 2 after first transfer
        ("results5.dat", 3),   # Pond 3 after second transfer
        ("results8.dat", 4),   # Pond 4 after third transfer
        ("results11.dat", 5),  # Pond 5 after fourth transfer
        ("results14.dat", 6),  # Pond 6 after fifth transfer
    ]

    # Mapping from stage N file to corresponding Pond 1 evolution file for overlay
    pond1_overlay_map = {
        2: "results3.dat",
        3: "results6.dat",
        4: "results9.dat",
        5: "results12.dat",
        6: "results13.dat",  # short run to tr5 precedes transfer to pond 6
    }

    def to_abs_time(df: pd.DataFrame, start_day: float) -> pd.Series:
        t = _time_series(df)
        base = float(t.iloc[0]) if pd.notna(t.iloc[0]) else float(t.dropna().iloc[0]) if not t.dropna().empty else 0.0
        return t - base + float(start_day)

    for fname, stage_idx in final_stage_files:
        df = outputs.get(fname)
        if df is None:
            continue
        try:
            # Plot Pond N alone
            time = to_abs_time(df, stage_start_days.get(fname, 0))
            calcite = df.filter(regex="(?i)calcite").iloc[:, 0]
            halite = df.filter(regex="(?i)halite").iloc[:, 0]
            gypsum = df.filter(regex="(?i)gypsum").iloc[:, 0]
            save_path = plots_dir / f"pond{stage_idx}_stage{stage_idx}.png"
            plot_mineral_masses(
                time,
                calcite,
                halite,
                gypsum,
                title=f"Pond {stage_idx} (stage {stage_idx})",
                save_path=save_path,
                show=False,
            )

            # Overlay with Pond 1 for stages > 1
            if stage_idx > 1:
                pond1_file = pond1_overlay_map.get(stage_idx)
                df_p1 = outputs.get(pond1_file)
                if df_p1 is not None:
                    time_p1 = to_abs_time(df_p1, stage_start_days.get(pond1_file, 0))
                    calcite_p1 = df_p1.filter(regex="(?i)calcite").iloc[:, 0]
                    halite_p1 = df_p1.filter(regex="(?i)halite").iloc[:, 0]
                    gypsum_p1 = df_p1.filter(regex="(?i)gypsum").iloc[:, 0]
                    overlay_path = plots_dir / f"overlay_pond1_vs_pond{stage_idx}.png"
                    plot_overlay(
                        time_p1, calcite_p1, halite_p1, gypsum_p1, "Pond 1",
                        time, calcite, halite, gypsum, f"Pond {stage_idx}",
                        title=f"Pond 1 vs Pond {stage_idx}",
                        save_path=overlay_path,
                        show=False,
                    )
        except Exception:
            pass

    # Optional quick plot for first stage (on screen)
    if args.plot and "results.dat" in outputs:
        try:
            df = outputs["results.dat"]
            t = _time_series(df)
            base = float(t.iloc[0]) if pd.notna(t.iloc[0]) else float(t.dropna().iloc[0]) if not t.dropna().empty else 0.0
            time = t - base + float(stage_start_days.get("results.dat", 0))
            calcite = df.filter(regex="(?i)calcite").iloc[:, 0]
            halite = df.filter(regex="(?i)halite").iloc[:, 0]
            gypsum = df.filter(regex="(?i)gypsum").iloc[:, 0]
            plot_mineral_masses(time, calcite, halite, gypsum, title="Pond 1 (preview)", save_path=None, show=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
