# -*- coding: utf-8 -*-
# Utility functions for pond capacity checks
# src/utils/ponds.py

from pathlib import Path
import pandas as pd

def get_transfer_volume(
    ponds_file: Path,
    target_pond: str,
    requested_volume_m3: float,
    target_current_m3: float = 0.0,
    source_pond: str | None = None
) -> float:
    """Devuelve cuánto cabe en la balsa destino (sin detener el programa)."""
    df = pd.read_csv(ponds_file, sep="\t")
    df = df.set_index(df.columns[0])

    if target_pond not in df.index:
        raise ValueError(f"Target pond '{target_pond}' not found in {ponds_file}")

    max_capacity_m3 = float(df.loc[target_pond, "m3"])
    remaining_capacity_m3 = max(max_capacity_m3 - float(target_current_m3), 0.0)

    allowed_m3 = min(float(requested_volume_m3), remaining_capacity_m3)

    src = source_pond if source_pond is not None else "source"
    print(
        f"[TRANSFER CAPACITY] {src} -> {target_pond} | "
        f"requested={requested_volume_m3:.8f} m3 | "
        f"target_current={target_current_m3:.8f} m3 | "
        f"target_max={max_capacity_m3:.8f} m3 | "
        f"target_remaining={remaining_capacity_m3:.8f} m3 | "
        f"allowed={allowed_m3:.8f} m3"
    )
    return allowed_m3


def cap_and_transfer(
    ponds_file: Path,
    source_pond: str,
    target_pond: str,
    requested_volume_m3: float,
    target_current_m3: float = 0.0
) -> tuple[float, float]:
    """
    Aplica el tope por capacidad y devuelve:
      (transferred_m3, discarded_m3)
    Nunca lanza excepción por falta de capacidad: imprime y continúa.
    """
    allowed = get_transfer_volume(
        ponds_file=ponds_file,
        target_pond=target_pond,
        requested_volume_m3=requested_volume_m3,
        target_current_m3=target_current_m3,
        source_pond=source_pond
    )
    discarded = max(requested_volume_m3 - allowed, 0.0)

    if discarded > 0:
        print(
            f"[TRANSFER RESULT] {source_pond} -> {target_pond} | "
            f"transferred={allowed:.8f} m3 | DISCARDED={discarded:.8f} m3"
        )
    else:
        print(
            f"[TRANSFER RESULT] {source_pond} -> {target_pond} | "
            f"transferred={allowed:.8f} m3 | DISCARDED=0.00000000 m3"
        )
    return allowed, discarded
