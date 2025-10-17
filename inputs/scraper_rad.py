# -*- coding: utf-8 -*-
"""
Created on Wed Jul  30 10:09:40 2025

@author: ines.draaijer

Web scraper del pronóstico del valor diario de radiación para los próximos 15 días

"""

from playwright.sync_api import sync_playwright
import csv
from datetime import datetime
import locale
from pathlib import Path

# Forzar nombres de meses en español
locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')

URL = "https://www.tutiempo.net/radiacion-solar/monzon.html"

# Carpeta donde guardar el CSV (mismo directorio del script)
SCRIPT_DIR = Path(__file__).resolve().parent
OUT_CSV = SCRIPT_DIR / "radiacion_monzon.csv"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto(URL)

    # aceptar cookies
    try:
        page.wait_for_selector("button.fc-button.fc-cta-consent.fc-primary-button", timeout=5000)
        page.click("button.fc-button.fc-cta-consent.fc-primary-button")
        print("✓ Cookies aceptadas.")
    except:
        print("No apareció el aviso de cookies.")

    # dar el tiempo suficiente para esperar a la carga completa del contenido
    page.wait_for_selector("div.diauv", timeout=10000)
    page.wait_for_timeout(3000)

    bloques = page.query_selector_all("div.diauv")
    print(f"Número de bloques encontrados: {len(bloques)}")

    data = []

    for i, b in enumerate(bloques):
        try:
            print(f"\nBloque {i+1}:")
            inner = b.inner_html()
            print(inner[:300])  # imprimir solo los primeros caracteres

            day_elem = b.query_selector("span")         # contiene la fecha
            val_elem = b.query_selector("div.dayval")   # contiene el valor de radiación

            if not day_elem:
                print("Err: Elemento de fecha no encontrado.")
            if not val_elem:
                print("Err: Elemento de radiación no encontrado.")
                continue

            fecha_raw = day_elem.text_content().strip()
            valor_raw = val_elem.text_content().strip()

            print(f"Fecha: {fecha_raw}")
            print(f"Radiación: {valor_raw}")

            valor = int(valor_raw.split()[0])   # valor en Wh/m²
            valor_W = valor / 24                # conversión a W/m² medios diarios

            # extraer la fecha completa
            año_actual = datetime.now().year

            try:
                fecha_obj = datetime.strptime(f"{fecha_raw} {año_actual}", "%d de %B %Y")
                fecha = fecha_obj.strftime("%Y-%m-%d")
            except ValueError:
                fecha = fecha_raw

            data.append((fecha, valor_W))  # ya convertido a W/m²
        except Exception as e:
            print(f"[!] Error en el bloque {i+1}: {e}")

    # guardar CSV si hay datos
    if data:
        with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Fecha", "Radiacion_Wm2"])
            writer.writerows(data)
        print(f"\n✓ Archivo CSV guardado en: {OUT_CSV}")
    else:
        print("🛇 No se extrajo ningún dato.")

    browser.close()