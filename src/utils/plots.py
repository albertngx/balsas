from __future__ import annotations

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def plot_mineral_masses(time, calcite_tm, halite_tm, gypsum_tm, title: str, save_path: Path | str | None = None, show: bool = True) -> None:
    fig, ax = plt.subplots()
    ax.set_xlabel("Days")
    ax.set_ylabel("Mass (Tm)")
    ax.set_title(title)
    ax.plot(time, calcite_tm, "b-", label="Calcite")
    ax.plot(time, halite_tm, "r-", label="Halite")
    ax.plot(time, gypsum_tm, "g-", label="Gypsum")
    ax.legend(loc="upper left")
    fig.tight_layout()
    if save_path is not None:
        sp = Path(save_path)
        sp.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(sp, dpi=150)
    if show:
        plt.show()
    plt.close(fig)


def plot_overlay(
    time_a, calcite_a, halite_a, gypsum_a, label_a,
    time_b, calcite_b, halite_b, gypsum_b, label_b,
    title: str,
    save_path: Path | str | None = None,
    show: bool = False,
):
    fig, ax = plt.subplots()
    ax.set_xlabel("Days")
    ax.set_ylabel("Mass (Tm)")
    ax.set_title(title)
    # Pond A
    ax.plot(time_a, calcite_a, "b-", label=f"Calcite ({label_a})")
    ax.plot(time_a, halite_a, "r-", label=f"Halite ({label_a})")
    ax.plot(time_a, gypsum_a, "g-", label=f"Gypsum ({label_a})")
    # Pond B
    ax.plot(time_b, calcite_b, "b--", label=f"Calcite ({label_b})")
    ax.plot(time_b, halite_b, "r--", label=f"Halite ({label_b})")
    ax.plot(time_b, gypsum_b, "g--", label=f"Gypsum ({label_b})")
    ax.legend(loc="upper left", ncol=2)
    fig.tight_layout()
    if save_path is not None:
        sp = Path(save_path)
        sp.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(sp, dpi=150)
    if show:
        plt.show()
    plt.close(fig)
