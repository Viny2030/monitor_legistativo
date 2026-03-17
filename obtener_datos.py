"""
MEL-TP | Scraper de Nómina de Diputados
========================================
Reemplaza obtener_datos.py y scraper_diputados.py.
Extrae TODOS los campos disponibles en la tabla oficial
más el link al perfil individual de cada diputado.

Campos extraídos:
    Nombre, Distrito, Bloque, Mandato,
    Inicio_Mandato, Fin_Mandato, Fecha_Nacimiento,
    URL_Perfil, ID_Oficial

Ejecutar: python obtener_datos.py
Requiere: pip install requests beautifulsoup4 pandas
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
from datetime import datetime

# ── Configuración ──────────────────────────────────────────────
URL_NOMINA    = "https://www.diputados.gov.ar/diputados/"
URL_BASE      = "https://www.diputados.gov.ar"
ARCHIVO_CSV   = "nomina_diputados.csv"
HEADERS       = {"User-Agent": "Mozilla/5.0 (MEL-TP/1.0)"}


# ── Helpers ────────────────────────────────────────────────────

def limpiar_texto(texto):
    """Elimina espacios y saltos de línea extra."""
    return " ".join(texto.split()) if texto else ""


def extraer_id_oficial(url_perfil):
    """
    Del link /diputados/gcaguero/ extrae 'gcaguero'
    que es el ID interno que usa el sitio.
    """
    if not url_perfil:
        return ""
    partes = [p for p in url_perfil.split("/") if p]
    return partes[-1] if partes else ""


def parsear_fecha(texto):
    """Convierte '10/12/2023' → '2023-12-10'. Devuelve vacío si falla."""
    texto = limpiar_texto(texto)
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return texto


# ── Scraper principal ──────────────────────────────────────────

def extraer_diputados():
    print("=" * 55)
    print("  MEL-TP | Extracción de Nómina de Diputados")
    print("=" * 55)
    print(f"  Fuente : {URL_NOMINA}")
    print(f"  Destino: {ARCHIVO_CSV}")
    print()

    # ── Solicitud HTTP ─────────────────────────────────────────
    try:
        res = requests.get(URL_NOMINA, headers=HEADERS, timeout=30)
        res.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Error de conexión: {e}")
        return None

    soup = BeautifulSoup(res.text, "html.parser")
    tabla = soup.find("table")

    if not tabla:
        print("❌ No se encontró la tabla. El sitio puede haber cambiado su estructura.")
        return None

    # ── Leer encabezados reales de la tabla ───────────────────
    encabezados = [limpiar_texto(th.get_text()) for th in tabla.find_all("th")]
    print(f"  Columnas detectadas en la tabla: {encabezados}")
    print()

    # ── Parsear filas ──────────────────────────────────────────
    datos = []
    filas = tabla.find_all("tr")[1:]  # saltamos el encabezado

    for fila in filas:
        cols = fila.find_all("td")
        if len(cols) < 4:
            continue

        # col 0: foto (ignorar)
        # col 1: nombre con link al perfil
        # col 2: distrito
        # col 3: bloque
        # col 4: mandato (ej. "2023-2027")
        # col 5: inicio mandato
        # col 6: fin mandato
        # col 7: fecha nacimiento

        # Nombre y URL del perfil
        celda_nombre = cols[1]
        enlace = celda_nombre.find("a")
        nombre     = limpiar_texto(celda_nombre.get_text())
        url_perfil = ""
        if enlace and enlace.get("href"):
            href = enlace["href"].strip()
            url_perfil = href if href.startswith("http") else URL_BASE + href

        id_oficial = extraer_id_oficial(url_perfil)

        # Resto de columnas — defensivo si la tabla tiene menos cols
        def col_texto(i):
            return limpiar_texto(cols[i].get_text()) if i < len(cols) else ""

        distrito        = col_texto(2)
        bloque          = col_texto(3)
        mandato         = col_texto(4)
        inicio_mandato  = parsear_fecha(col_texto(5))
        fin_mandato     = parsear_fecha(col_texto(6))
        fecha_nac       = parsear_fecha(col_texto(7))

        datos.append({
            "ID_Oficial"     : id_oficial,
            "Nombre"         : nombre,
            "Distrito"       : distrito,
            "Bloque"         : bloque,
            "Mandato"        : mandato,
            "Inicio_Mandato" : inicio_mandato,
            "Fin_Mandato"    : fin_mandato,
            "Fecha_Nacimiento": fecha_nac,
            "URL_Perfil"     : url_perfil,
        })

    if not datos:
        print("⚠️  Se encontró la tabla pero no se pudieron extraer filas.")
        return None

    # ── Crear DataFrame ────────────────────────────────────────
    df = pd.DataFrame(datos)

    # ── Estadísticas ───────────────────────────────────────────
    print(f"✅ Diputados extraídos : {len(df)}")
    print(f"   Con URL de perfil   : {df['URL_Perfil'].astype(bool).sum()}")
    print(f"   Con fecha nacimiento: {(df['Fecha_Nacimiento'] != '').sum()}")
    print()
    print("── Distribución por Bloque ──────────────────────────")
    print(df["Bloque"].value_counts().to_string())
    print()
    print("── Distribución por Distrito ────────────────────────")
    print(df["Distrito"].value_counts().to_string())
    print()
    print("── Muestra (primeros 3) ─────────────────────────────")
    print(df[["ID_Oficial", "Nombre", "Distrito", "Bloque", "Mandato"]].head(3).to_string(index=False))

    # ── Guardar CSV ────────────────────────────────────────────
    df.to_csv(ARCHIVO_CSV, index=False, encoding="utf-8")
    print()
    print(f"💾 CSV guardado: {ARCHIVO_CSV}")
    print(f"   Columnas: {list(df.columns)}")

    return df


# ── Entry point ────────────────────────────────────────────────
if __name__ == "__main__":
    df = extraer_diputados()
