# -*- coding: utf-8 -*-
"""
Created on Wed Aug  6 9:02:14 2025

@author: ines.draaijer

Cálculo diario de tasa de evaporación a partir de radiación (diaria + media mensual),
usando predicción de temperatura diaria de AEMET (Monzón, 7 días).
"""

import os
import numpy as np
import pandas as pd
from pathlib import Path


# --- CONFIGURACIÓN DE ENTRADAS/SALIDA ---

SCRIPT_DIR = Path(__file__).resolve().parent

DAILY_CSV   = SCRIPT_DIR / "radiacion_monzon.csv"               # columnas esperadas: date, Radiacion_Wm2
MONTHLY_CSV = SCRIPT_DIR / "radiacion_media_mensual.csv"        # columnas esperadas: mes, radiacion_wm2
TEMP_CSV    = SCRIPT_DIR / "weather" / "Weather_Data" / "monzon_7dias.csv"

OUT_CSV     = SCRIPT_DIR / "evap_diaria.csv"


# --- CONSTANTES FÍSICAS Y PARÁMETROS ---

p     = 101325        # Pa - presión atm estándar
temp  = 273.15 + 15.2 # K - fallback absoluto si falta T
hvap  = 2.257e6       # J/kg - calor latente de vaporización
rhow  = 998           # kg/m3 - densidad agua
M_H2O = 0.01801528    # kg/mol - masa molar agua

ALBEDO = 0.07   # fracción reflejada
K_LW   = 0.8   # factor corrector onda larga: Rn = K_LW(1-albedo)Rs

# Climatología mensual de Monzón (temperatura media, °C)
monzon_climate = {
    1: 6,   2: 7,   3: 11,  4: 13,
    5: 17,  6: 22,  7: 25,  8: 25,
    9: 20, 10: 15, 11: 10, 12: 6
}

# --- FUNCIONES AUXILIARES ---

def rn_from_rs(rs_wm2, albedo=ALBEDO, k_lw=K_LW):
    if pd.isna(rs_wm2):
        return np.nan
    return max(0.0, k_lw * (1.0 - albedo) * float(rs_wm2))

def get_temp_kelvin(row):
    """Devuelve la temperatura en Kelvin con fallback jerárquico:
       1) predicción diaria
       2) climatología mensual
       3) valor fijo definido arriba
    """
    if pd.notna(row["daily_t_mean"]):
        return 273.15 + float(row["daily_t_mean"])
    month = row["date"].month
    if month in monzon_climate:
        return 273.15 + monzon_climate[month]
    return float(temp)


# --- RADIACIÓN: DIARIA Y MENSUAL ---

df_daily = pd.read_csv(DAILY_CSV, encoding="utf-8")
df_daily.columns = df_daily.columns.str.strip()

# Normalizar nombres
if "Radiacion_Wm2" in df_daily.columns:
    df_daily = df_daily.rename(columns={"Radiacion_Wm2": "Rs_Wm2"})
elif "radiacion_Wm2" in df_daily.columns:
    df_daily = df_daily.rename(columns={"radiacion_Wm2": "Rs_Wm2"})
elif "Rs_Wm2" not in df_daily.columns:
    raise ValueError("No se encuentra columna de radiación diaria ('Radiacion_Wm2'/'Rs_Wm2').")

# Asegurar columna date
df_daily = df_daily.rename(columns={"Fecha": "date"})
df_daily["date"] = pd.to_datetime(df_daily["date"], errors="raise").dt.normalize()
df_daily = df_daily.sort_values("date")

print("Radiación diaria:", df_daily["date"].min().date(), "→", df_daily["date"].max().date())

# Mensual
df_month = pd.read_csv(MONTHLY_CSV, encoding="utf-8")
df_month.columns = df_month.columns.str.strip().str.lower()

if "mes" not in df_month.columns:
    raise ValueError("El CSV mensual debe tener columna 'mes'.")

if "radiacion_wm2" not in df_month.columns:
    for cand in ["Radiacion_Wm2", "rs_wm2", "rn_wm2"]:
        if cand.lower() in df_month.columns:
            df_month = df_month.rename(columns={cand: "radiacion_wm2"})
            break
    if "radiacion_wm2" not in df_month.columns:
        raise ValueError("El CSV mensual debe tener columna 'radiacion_wm2'.")

df_month["mes"] = df_month["mes"].astype(int)
month_map = dict(zip(df_month["mes"], df_month["radiacion_wm2"]))

print("Radiación mensual cargada (mes → valor):", month_map)

# Calendario completo
start = df_daily["date"].min().normalize()
calendar = pd.DataFrame({"date": pd.date_range(start=start, periods=365, freq="D")})

df = calendar.merge(df_daily[["date", "Rs_Wm2"]], on="date", how="left")

# Rellenar huecos con media mensual
df["Mes"] = df["date"].dt.month
df["Rs_Wm2"] = df.apply(
    lambda r: month_map.get(int(r["Mes"])) if pd.isna(r["Rs_Wm2"]) and int(r["Mes"]) in month_map else r["Rs_Wm2"],
    axis=1
)
df["Rs_Wm2"] = pd.to_numeric(df["Rs_Wm2"], errors="coerce")


# --- TEMPERATURA: PREDICCIÓN AEMET (Monzón, 7 días) ---

if not TEMP_CSV.exists():
    raise FileNotFoundError(f"No encuentro el CSV de temperatura en: {TEMP_CSV}")

temp_df = pd.read_csv(TEMP_CSV, sep=",", encoding="utf-8")

if "date" not in temp_df.columns or "daily_t_mean" not in temp_df.columns:
    raise ValueError("El CSV debe contener columnas 'date' y 'daily_t_mean'.")

temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.normalize()

# Unimos directamente con el DataFrame principal
df = df.merge(temp_df[["date", "daily_t_mean"]], on="date", how="left")

# Aplicamos fallback jerárquico
df["T_k"] = df.apply(get_temp_kelvin, axis=1)

print("Primeras filas con radiación + temperatura integrada:")
print(df[["date", "Rs_Wm2", "daily_t_mean", "T_k"]].head(10).to_string(index=False))

n_missing = df["daily_t_mean"].isna().sum()
print(f"Días sin predicción (rellenados con clima mensual o valor fijo): {n_missing}")


# --- CÁLCULOS DE EVAPORACIÓN ---

df["Rn_Wm2"] = df["Rs_Wm2"].apply(rn_from_rs)

T_k = df["T_k"].astype(float)
delta = (p/760.0) * (5336.0 / (T_k**2)) * np.exp(21.07 - (5336.0 / T_k))
gam   = 0.0016286 * p / hvap

df["erate_kg_m2_s"] = (delta * df["Rn_Wm2"]) / (hvap * (delta + gam))

# Tasa molar mol/(día·L)
df["evap_mol_day_L"] = (df["erate_kg_m2_s"] * 86400.0) / (1000.0 * M_H2O)

print("Evaporación (mol/día·L):", float(df["evap_mol_day_L"].min()), "→", float(df["evap_mol_day_L"].max()))


# --- SALIDA FINAL ---

df_out = pd.DataFrame({
    "date": df["date"],
    "evap_mol_day_L": df["evap_mol_day_L"],
    "T_k": df["T_k"],
    "Rs_Wm2": df["Rs_Wm2"],
    "Rn_Wm2": df["Rn_Wm2"]
})

# Guardar con 3 decimales en todos los valores flotantes
df_out.to_csv(OUT_CSV, index=False, float_format="%.3f")

print(f"CSV creado: {OUT_CSV} (filas={len(df_out)})")
print(df_out.head(10).to_string(index=False))