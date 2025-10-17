# -*- coding: utf-8 -*-
"""
Created on Wed Aug  6 10:00:09 2025

@author: ines.draaijer
"""

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import datetime
import pytz
from io import StringIO
import os
import xml.etree.ElementTree as ET


# LECTURA DE ESTACIONES DISPONIBLES AEMET

# Ruta al archivo CSV con las estaciones disponibles
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
estacions_AEMET_open = os.path.join(SCRIPT_DIR, "Estacions_disponibles_AEMET.csv")

# Carpeta de los archivos resultantes
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "Weather_Data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Leer el archivo CSV (decimal con coma)
estacions_AEMET_df = pd.read_csv(estacions_AEMET_open, sep=";", encoding="utf-8-sig", decimal=",")

# Convertir coordenadas a float
estacions_AEMET_df["Latitud"] = estacions_AEMET_df["Latitud"].astype(float)
estacions_AEMET_df["Longitud"] = estacions_AEMET_df["Longitud"].astype(float)


# DEFINICIÓN DEL ÁREA DE MONZÓN (HUESCA)

x_min = 0.1   # longitud mínima
x_max = 0.4   # longitud máxima
y_min = 41.7  # latitud mínima
y_max = 42.8  # latitud máxima

print("Área de filtrado ajustada a Monzón (Huesca):")
print(f"x (longitud): {x_min} → {x_max}")
print(f"y (latitud): {y_min} → {y_max}")


# FILTRADO DE ESTACIONES

filtro = (
    (estacions_AEMET_df["Longitud"] >= x_min) & (estacions_AEMET_df["Longitud"] <= x_max) &
    (estacions_AEMET_df["Latitud"] >= y_min) & (estacions_AEMET_df["Latitud"] <= y_max)
)

Stations_list = estacions_AEMET_df[filtro].reset_index(drop=True)
n_estacions_AEMET = len(Stations_list)

print(f"Se han detectado {n_estacions_AEMET} estaciones dentro del área especificada.")
print(Stations_list.iloc[:, 0])


# WEBSCRAPING DE DATOS METEOROLÓGICOS

all_data = []  # lista vacía para acumular todas las estaciones

for i in range(len(Stations_list)):
    req = requests.get(Stations_list["Link"][i])
    soup = BeautifulSoup(req.text, "lxml")

    table = soup.find_all("table")
    df = pd.read_html(StringIO(str(table)))[0]

    # Obtener coordenadas del HTML
    coord = soup.find_all("abbr")
    lat_text = coord[0].text
    lon_text = coord[1].text

    lat_num = re.findall(r'\d+', lat_text)
    lon_num = re.findall(r'\d+', lon_text)

    lat_deg, lat_min, lat_sec = map(int, lat_num)
    lon_deg, lon_min, lon_sec = map(int, lon_num)

    lat_decimal = lat_deg + lat_min / 60 + lat_sec / 3600
    lon_decimal = lon_deg + lon_min / 60 + lon_sec / 3600

    df["Latitude"] = lat_decimal
    df["Longitude"] = lon_decimal
    df["Stations"] = Stations_list["Estaciones"][i] if "Estaciones" in Stations_list.columns else Stations_list.iloc[i, 0]

    df["Fecha y hora oficial"] = pd.to_datetime(df["Fecha y hora oficial"], dayfirst=True, errors="coerce")
    df = df.sort_values("Fecha y hora oficial")

    # --- Normalizar columnas ---
    rename_map = {
        "Fecha y hora oficial": "date",
        "Temp. (°C)": "temp_c",
        "V. vien. (km/h)": "wind_vel_kmh",
        "Dir. viento": "wind_dir",
        "Racha (km/h)": "gust_kmh",
        "Dir. racha": "gust_dir",
        "Prec. (mm)": "prec_mm",
        "Presión (hPa)": "pressure_hpa",
        "Tend. (hPa)": "pressure_trend_hpa",
        "Humedad (%)": "humidity_pct",
        "Latitude": "latitude",
        "Longitude": "longitude",
        "Stations": "station_name"
    }
    df = df.rename(columns=rename_map)

    # Guardar CSV individual
    filename = os.path.join(OUTPUT_DIR, f"{i+1}_weather.csv")
    df.to_csv(filename, sep=";", index=False)

    all_data.append(df)

# --- Concatenar todos los DataFrames al final ---
if all_data:
    all_weather = pd.concat(all_data, ignore_index=True)
    combined_path = os.path.join(OUTPUT_DIR, "all_weather_fc.csv")
    all_weather.to_csv(combined_path, sep=";", index=False)
    print(f"Archivo combinado creado: {combined_path}")
else:
    print("⚠ No se generó ningún DataFrame, no se puede crear all_weather_fc.csv")

# PARÁMETROS TEMPORALES

spain_timezone = pytz.timezone('Europe/Madrid')
data_inicial = datetime.datetime(2025, 8, 5, 10, 30).astimezone(spain_timezone)
temps_calcul = 1200  # segundos
data_final = data_inicial - datetime.timedelta(seconds=temps_calcul)


# LECTURA Y FILTRADO DE CSVs POR ESTACIÓN

data_AEMET_open = {}
data_AEMET_none = {}

for i in range(n_estacions_AEMET):
    data_path = os.path.join(OUTPUT_DIR, f"{i+1}_weather.csv")
    data_AEMET_open[i + 1] = np.loadtxt(data_path, delimiter=";", skiprows=1, dtype=str)

    n_rows = data_AEMET_open[i + 1].shape[0]
    data_AEMET_none[i + 1] = np.empty((n_rows, 7), dtype=object)

    for it in range(n_rows):
        try:
            fecha_hora = data_AEMET_open[i + 1][it, 0]
            it_data = datetime.datetime.strptime(fecha_hora, '%Y-%m-%d %H:%M:%S').astimezone(spain_timezone)

            if data_final - datetime.timedelta(minutes=30) <= it_data <= data_inicial:
                print('here', it_data)
                data_str = it_data.strftime("%Y-%m-%d %H:%M")

                data_AEMET_none[i + 1][it, 0] = data_str
                data_AEMET_none[i + 1][it, 1] = float(data_AEMET_open[i + 1][it, 11])  # Longitud
                data_AEMET_none[i + 1][it, 2] = float(data_AEMET_open[i + 1][it, 10])  # Latitud

                if data_AEMET_open[i + 1][it, 2] == '':
                    data_AEMET_none[i + 1][it, 3:7] = [np.nan] * 4
                else:
                    v = float(data_AEMET_open[i + 1][it, 2])
                    direction = data_AEMET_open[i + 1][it, 3]

                    data_AEMET_none[i + 1][it, 3] = v
                    data_AEMET_none[i + 1][it, 4] = direction

                    wind_components = {
                        '1-Calma':     (0, 0),
                        '2-Norte':     (0, -1),
                        '3-Nordeste':  (-np.sqrt(2)/2, -np.sqrt(2)/2),
                        '4-Este':      (-1, 0),
                        '5-Sudeste':   (-np.sqrt(2)/2, np.sqrt(2)/2),
                        '6-Sur':       (0, 1),
                        '7-Sudoeste':  (np.sqrt(2)/2, np.sqrt(2)/2),
                        '8-Oeste':     (1, 0),
                        '9-Noroeste':  (np.sqrt(2)/2, -np.sqrt(2)/2)
                    }

                    if direction in wind_components:
                        u_factor, v_factor = wind_components[direction]
                        data_AEMET_none[i + 1][it, 5] = u_factor * v
                        data_AEMET_none[i + 1][it, 6] = v_factor * v
                    else:
                        data_AEMET_none[i + 1][it, 5:7] = [np.nan, np.nan]
        except:
            continue


# --- LECTURA DE PREDICCIÓN MUNICIPAL AEMET (Monzón, 7 días) ---

XML_URL = "https://www.aemet.es/xml/municipios/localidad_22158.xml"
pred_file = os.path.join(OUTPUT_DIR, "monzon_7dias.csv")

def get_daily_mean_from_aemet(xml_url):
    resp = requests.get(xml_url)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    records = []
    for dia in root.findall(".//dia"):
        fecha = dia.attrib.get("fecha")

        # Extraer Tmax y Tmin
        tmax = dia.findtext("temperatura/maxima")
        tmin = dia.findtext("temperatura/minima")

        # Extraer temperaturas horarias (si existen)
        hourly = [d.text for d in dia.findall("temperatura/dato") if d.text is not None]

        tmean = None
        if hourly:
            vals = [float(v) for v in hourly if v.strip() != ""]
            if vals:
                tmean = sum(vals) / len(vals)
        if tmean is None and tmax and tmin:
            tmean = (float(tmax) + float(tmin)) / 2.0

        if fecha and tmean is not None:
            records.append({
                "date": pd.to_datetime(fecha),
                "daily_t_mean": tmean
            })

    return pd.DataFrame(records)

# Generar CSV
try:
    pred_df = get_daily_mean_from_aemet(XML_URL)
    pred_df.to_csv(pred_file, index=False)
    print(f"CSV de predicción creado: {pred_file} (filas={len(pred_df)})")
    print(pred_df)
except Exception as e:
    print("Error al obtener predicción de AEMET:", e)