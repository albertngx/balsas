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
    #Extract time series from the phreeqc output dataframe, trying common time/step column names
    for name in ("time", "Time", "step", "Step", "reaction", "Reaction"):
        if name in df.columns:
            #Convert chosen column to numeric (coerce errors to NaN)
            s = pd.to_numeric(df[name], errors="coerce")
            break
    else:
        #Fallback: use the 6th column (index 5) if no known column exists
        s = pd.to_numeric(df.iloc[:, 5], errors="coerce")
    #Fill NaN values by forward fill, then fallback to 0
    return s.fillna(method="ffill").fillna(0)


def main():
    #Parse command line arguments
    parser = argparse.ArgumentParser(description="Run pond evaporation simulation")
    parser.add_argument("--workspace", type=str, default=str(Path.cwd()), help="Workspace root directory")
    parser.add_argument("--config", type=str, default="config.yaml", help="Configuration file path")
    parser.add_argument("--plot", action="store_true", help="Plot preview for the first stage")
    args = parser.parse_args()

    #Resolve workspace and config file path
    workspace = Path(args.workspace).resolve()
    config_path = workspace / args.config
    
    #Load configuration from YAML file
    config = load_config(config_path)
    
    #Extract paths for PHREEQC binary, database, and input data
    phreeqc_bin, phreeqc_db = get_phreeqc_paths(config, workspace)
    brine_path, ponds_path = get_data_paths(config, workspace)
    work_dir = resolve_path(config, "work_dir", workspace)
    
    #Optional evaporation schedule path (CSV con mol/L/día)
    try:
        evap_schedule_path = get_evaporation_schedule_path(config, workspace)
    except FileNotFoundError:
        evap_schedule_path = None

    #Initialize PHREEQC runner with binary and database
    runner = PhreeqcRunner.from_paths(
        phreeqc_bin=phreeqc_bin,
        phreeqc_database=phreeqc_db,
        work_dir=work_dir
    )

    #Load input data (brine, ponds, evaporation schedule)
    data = load_input(brine_path, ponds_path, evap_schedule_path=evap_schedule_path)

    # ========= INSERT 1: capacidades y política de transferencia =========
    # Leemos pondsData.txt (tabulado) y construimos un dict { 'pond1': m3, ..., 'pond6': m3 }
    try:
        df_caps = pd.read_csv(ponds_path, sep="\t")
        pond_capacities_m3 = {str(row[0]).strip(): float(row[1]) for _, row in df_caps.iterrows()}
    except Exception as e:
        raise RuntimeError(f"Failed to read pond capacities from {ponds_path}: {e}")

    # Política: si no cabe todo en la balsa destino, transferir solo lo que cabe y DESCARTAR el resto
    transfer_policy = "discard_excess"  # usado por Simulation
    # Inyectamos en params para que Simulation lo use
    if isinstance(data.params, dict):
        data.params["pond_capacities_m3"] = pond_capacities_m3
        data.params["transfer_policy"] = transfer_policy
    else:
        # Si params no es dict (por ejemplo, un dataclass), intenta atributo .pond_capacities_m3
        setattr(data.params, "pond_capacities_m3", pond_capacities_m3)
        setattr(data.params, "transfer_policy", transfer_policy)
    # ========= FIN INSERT 1 =========

    # ========= INSERT: volumen inicial y densidad para cálculo de volumen restante =========
    # Leemos de config.yaml (ya has puesto liquid_density_g_per_L: 1200)
    try:
        initial_pond1_m3 = float(config.get("initial_pond1_m3", float(pond_capacities_m3.get("pond1", 0.0))))
    except Exception:
        initial_pond1_m3 = float(pond_capacities_m3.get("pond1", 0.0))

    try:
        liquid_density_g_per_L = float(config.get("liquid_density_g_per_L", 1000.0))
    except Exception:
        liquid_density_g_per_L = 1000.0

    # Inyección en params (dict o dataclass)
    if isinstance(data.params, dict):
        data.params["initial_pond1_m3"] = initial_pond1_m3
        data.params["liquid_density_g_per_L"] = liquid_density_g_per_L
    else:
        setattr(data.params, "initial_pond1_m3", initial_pond1_m3)
        setattr(data.params, "liquid_density_g_per_L", liquid_density_g_per_L)
    # ========= FIN INSERT =========


    # ========= INSERT 2: evaporación diaria en mol/L/día =========
    # Si existe evap_diaria.csv (o el archivo indicado en config), leemos la columna 'evap_mol_day_L'
    # y la pasamos a Simulation como lista de floats. Unidades: mol/L/día.
    evap_schedule_mol_per_day_L = None
    if evap_schedule_path is not None and Path(evap_schedule_path).exists():
        try:
            df_ev = pd.read_csv(evap_schedule_path)
            # Columna esperada (según tu archivo): 'evap_mol_day_L'
            if "evap_mol_day_L" in df_ev.columns:
                evap_schedule_mol_per_day_L = df_ev["evap_mol_day_L"].astype(float).tolist()
            else:
                # Si tu CSV tuviera otro nombre de columna, añade aquí alias alternativos:
                for alt in ("evap_L_mol_day", "evap_mol_per_L_day", "evaporation_mol_L_day"):
                    if alt in df_ev.columns:
                        evap_schedule_mol_per_day_L = df_ev[alt].astype(float).tolist()
                        break
                if evap_schedule_mol_per_day_L is None:
                    print(f"WARNING: Column 'evap_mol_day_L' not found in {evap_schedule_path}. Schedule will be ignored.")
        except Exception as e:
            print(f"WARNING: Could not parse evaporation schedule from {evap_schedule_path}: {e}")

    # Inyección en params (solo si hay datos válidos)
    if evap_schedule_mol_per_day_L is not None:
        if isinstance(data.params, dict):
            data.params["evap_schedule_mol_per_day_L"] = evap_schedule_mol_per_day_L
        else:
            setattr(data.params, "evap_schedule_mol_per_day_L", evap_schedule_mol_per_day_L)
    # ========= FIN INSERT 2 =========

    #Initialize simulation with plant configuration and parameters
    sim = Simulation(plant=data.plant, params=data.params, work_dir=work_dir)

    #Run full multi-stage simulation pipeline
    outputs, stage_start_days = sim.run_full_pipeline(runner)

    #Report generated output files
    print(f"Generated {len(outputs)} result files in {runner.output_dir}:")
    for fname in outputs.keys():
        print(f" - {runner.output_dir / fname}")

    #Print summary of liquid transfers across ponds
    print_transfer_summary(outputs, stage_start_days, runner.output_dir)

    #Prepare plots directory under work_dir
    plots_dir = Path(runner.work_dir) / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    #Define key result files per pond stage for plotting
    final_stage_files = [
        ("results.dat", 1),    #Pond 1 initial run 100d
        ("results2.dat", 2),   #Pond 2 after first transfer
        ("results5.dat", 3),   #Pond 3 after second transfer
        ("results8.dat", 4),   #Pond 4 after third transfer
        ("results11.dat", 5),  #Pond 5 after fourth transfer
        ("results14.dat", 6),  #Pond 6 after fifth transfer
    ]

    #Map Pond1 evolution files to overlay against later ponds
    pond1_overlay_map = {
        2: "results3.dat",
        3: "results6.dat",
        4: "results9.dat",
        5: "results12.dat",
        6: "results13.dat",  #short Pond1 run before transfer to Pond 6
    }

    #Helper function: adjust relative time to absolute timeline
    def to_abs_time(df: pd.DataFrame, start_day: float) -> pd.Series:
        t = _time_series(df)
        base = float(t.iloc[0]) if pd.notna(t.iloc[0]) else float(t.dropna().iloc[0]) if not t.dropna().empty else 0.0
        return t - base + float(start_day)

    #Loop over final pond stage results
    for fname, stage_idx in final_stage_files:
        df = outputs.get(fname)
        if df is None:
            continue
        try:
            #Extract time and mineral masses for plotting
            time = to_abs_time(df, stage_start_days.get(fname, 0))
            calcite = df.filter(regex="(?i)calcite").iloc[:, 0]
            halite = df.filter(regex="(?i)halite").iloc[:, 0]
            gypsum = df.filter(regex="(?i)gypsum").iloc[:, 0]
            save_path = plots_dir / f"pond{stage_idx}_stage{stage_idx}.png"

            #Plot mineral evolution for current pond stage
            plot_mineral_masses(
                time,
                calcite,
                halite,
                gypsum,
                title=f"Pond {stage_idx} (stage {stage_idx})",
                save_path=save_path,
                show=False,
            )

            #If stage >1, overlay current pond with Pond1 evolution
            if stage_idx > 1:
                pond1_file = pond1_overlay_map.get(stage_idx)
                df_p1 = outputs.get(pond1_file)
                if df_p1 is not None:
                    time_p1 = to_abs_time(df_p1, stage_start_days.get(pond1_file, 0))
                    calcite_p1 = df_p1.filter(regex="(?i)calcite").iloc[:, 0]
                    halite_p1 = df_p1.filter(regex="(?i)halite").iloc[:, 0]
                    gypsum_p1 = df_p1.filter(regex="(?i)gypsum").iloc[:, 0]
                    overlay_path = plots_dir / f"overlay_pond1_vs_pond{stage_idx}.png"

                    #Generate overlay plot comparing Pond1 vs PondN
                    plot_overlay(
                        time_p1, calcite_p1, halite_p1, gypsum_p1, "Pond 1",
                        time, calcite, halite, gypsum, f"Pond {stage_idx}",
                        title=f"Pond 1 vs Pond {stage_idx}",
                        save_path=overlay_path,
                        show=False,
                    )
        except Exception:
            #Ignore plotting errors silently
            pass

    #Optional quick on-screen plot for Pond1 first stage
    if args.plot and "results.dat" in outputs:
        try:
            df = outputs["results.dat"]
            t = _time_series(df)
            base = float(t.iloc[0]) if pd.notna(t.iloc[0]) else float(t.dropna().iloc[0]) if not t.dropna().empty else 0.0
            time = t - base + float(stage_start_days.get("results.dat", 0))
            calcite = df.filter(regex="(?i)calcite").iloc[:, 0]
            halite = df.filter(regex="(?i)halite").iloc[:, 0]
            gypsum = df.filter(regex="(?i)gypsum").iloc[:, 0]

            #Show plot for Pond1 evolution
            plot_mineral_masses(time, calcite, halite, gypsum, title="Pond 1 (preview)", save_path=None, show=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
