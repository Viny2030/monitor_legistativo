"""
scrapers/sil.py
================
Scraper del Sistema de Información Legislativa (SIL) — HCDN Argentina.

Datos obtenidos:
  1. Proyectos con fecha_ingreso y fecha_dictamen → TPMP
  2. Proyectos por autor/diputado → Proyectos por Diputado (v1.1)

Estrategia de fuentes (en orden de prioridad):
  A) API CKAN datos.hcdn.gob.ar  — dataset proyectos (detección dinámica de campos)
  B) HTML hcdn.gob.ar/proyectos/ — páginas de Órdenes del Día (estado=OD)
  C) Fallback: valores estimados con nota de advertencia

Genera:
  data/sil_proyectos.csv       — proyectos con fechas (expediente, autor, ingreso, dictamen, días)
  data/sil_por_diputado.csv    — resumen por diputado (presentados, con_dictamen, tasa_exito_pct)
  data/tpmp_resultado.json     — TPMP calculado + metadatos de fuente

Uso:
    python -m scrapers.sil
    from scrapers.sil import calcular_tpmp, obtener_proyectos_por_diputado
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, date
from typing import Optional

import requests
import pandas as pd
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; MonitorLegislativo/1.1; "
        "+https://monitorlegistativo-production.up.railway.app)"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}
TIMEOUT = 30

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# CKAN API — datos.hcdn.gob.ar
CKAN_BASE = "https://datos.hcdn.gob.ar/api/3/action"
# Resource ID del dataset de proyectos parlamentarios (confirmado v1.0)
RESOURCE_ID_PROYECTOS = "22b2d52c-7a0e-426b-ac0a-a3326c388ba6"

# HTML — HCDN proyectos
HCDN_PROYECTOS_BASE = "https://www.hcdn.gob.ar/proyectos"
PAUSA_ENTRE_REQUESTS = 0.5  # segundos — respetar al servidor HCDN

# Duración máxima razonable en días para un proyecto (filtrar outliers)
MAX_DIAS_MADURACION = 730  # 2 años


# ---------------------------------------------------------------------------
# Helper: parsear fechas en formatos argentinos
# ---------------------------------------------------------------------------
_FORMATOS_FECHA = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"]


def _parse_fecha(s: str) -> Optional[date]:
    """Intenta parsear una fecha en varios formatos. Retorna None si falla."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip().split("T")[0]  # quitar parte de hora si existe
    for fmt in _FORMATOS_FECHA:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _normalizar_apellido(nombre: str) -> str:
    """Extrae y normaliza el apellido de un nombre tipo 'APELLIDO, Nombre'."""
    if not nombre:
        return ""
    return nombre.split(",")[0].strip().upper()


# ---------------------------------------------------------------------------
# FUENTE A: API CKAN — descubrimiento dinámico de campos
# ---------------------------------------------------------------------------
def _ckan_info_campos() -> list[str]:
    """Consulta la API de CKAN para descubrir los campos disponibles en el dataset."""
    url = f"{CKAN_BASE}/datastore_info"
    try:
        r = requests.get(url, params={"id": RESOURCE_ID_PROYECTOS},
                         headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        campos = [f["id"] for f in data.get("result", {}).get("fields", [])]
        print(f"  [SIL-CKAN] Campos disponibles: {campos}")
        return campos
    except Exception as e:
        print(f"  [SIL-CKAN] Error al consultar datastore_info: {e}")
        return []


def _ckan_buscar_campos_fecha(campos: list[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Identifica los campos de fecha_ingreso y fecha_dictamen entre los campos disponibles.
    Retorna (campo_ingreso, campo_dictamen) o (None, None).
    """
    campo_ingreso = None
    campo_dictamen = None

    patrones_ingreso = ["ingreso", "presentacion", "fecha_in", "fecha_p"]
    patrones_dictamen = ["dictamen", "despacho", "comision", "comisión", "fecha_d", "orden"]

    for c in campos:
        cl = c.lower()
        if not campo_ingreso and any(p in cl for p in patrones_ingreso):
            campo_ingreso = c
        if not campo_dictamen and any(p in cl for p in patrones_dictamen):
            campo_dictamen = c

    return campo_ingreso, campo_dictamen


def _ckan_descargar_proyectos(anio: int, campos_extra: list[str] = None) -> pd.DataFrame:
    """
    Descarga proyectos del dataset CKAN con paginación.
    Retorna DataFrame con columnas normalizadas.
    """
    url = f"{CKAN_BASE}/datastore_search"
    limit = 1000
    offset = 0
    registros = []
    anio_str = str(anio)
    anio_prev = str(anio - 1)

    print(f"  [SIL-CKAN] Descargando proyectos {anio_prev}-{anio_str}...")

    while True:
        try:
            r = requests.get(
                url,
                params={"resource_id": RESOURCE_ID_PROYECTOS,
                        "limit": limit, "offset": offset},
                headers=HEADERS,
                timeout=60
            )
            r.raise_for_status()
            data = r.json()
            records = data.get("result", {}).get("records", [])
            if not records:
                break

            total = data.get("result", {}).get("total", 0)

            for row in records:
                expediente = str(row.get("EXP_DIPUTADOS") or row.get("EXPEDIENTE") or "")
                if anio_str not in expediente and anio_prev not in expediente:
                    continue

                autor = str(row.get("AUTOR") or row.get("FIRMANTES") or "").upper().strip()
                tipo = str(row.get("TIPO") or row.get("TIPO_EXPEDIENTE") or "").upper().strip()
                estado = str(row.get("ESTADO") or row.get("TRAMITE") or "").upper().strip()

                # Fechas: buscar en todos los campos posibles
                fecha_ingreso_raw = ""
                fecha_dictamen_raw = ""
                if campos_extra:
                    for c in campos_extra:
                        cl = c.lower()
                        if any(p in cl for p in ["ingreso", "presentacion"]):
                            fecha_ingreso_raw = str(row.get(c) or "")
                        if any(p in cl for p in ["dictamen", "despacho", "orden"]):
                            fecha_dictamen_raw = str(row.get(c) or "")

                # También intentar nombres genéricos de fecha
                if not fecha_ingreso_raw:
                    for fname in ["FECHA_INGRESO", "FECHA", "FECHA_PRESENTACION"]:
                        val = row.get(fname)
                        if val:
                            fecha_ingreso_raw = str(val)
                            break

                if not fecha_dictamen_raw:
                    for fname in ["FECHA_DICTAMEN", "FECHA_DESPACHO", "FECHA_OD"]:
                        val = row.get(fname)
                        if val:
                            fecha_dictamen_raw = str(val)
                            break

                registros.append({
                    "expediente": expediente,
                    "autor": autor,
                    "tipo": tipo,
                    "estado": estado,
                    "fecha_ingreso_raw": fecha_ingreso_raw,
                    "fecha_dictamen_raw": fecha_dictamen_raw,
                })

            offset += limit
            if offset >= total:
                break

            time.sleep(PAUSA_ENTRE_REQUESTS)

        except Exception as e:
            print(f"  [SIL-CKAN] Error en paginación offset={offset}: {e}")
            break

    print(f"  [SIL-CKAN] {len(registros)} proyectos del período {anio_prev}-{anio_str}")
    return pd.DataFrame(registros) if registros else pd.DataFrame()


# ---------------------------------------------------------------------------
# FUENTE B: HTML — páginas de resultados de proyectos HCDN
# ---------------------------------------------------------------------------
def _html_scrape_ordenes_del_dia(anio: int, max_paginas: int = 20) -> list[dict]:
    """
    Scrapea las páginas de Órdenes del Día del HCDN.
    Las OD son proyectos que ya tienen dictamen de comisión.
    Retorna lista de: {expediente, tipo, fecha_ingreso_raw, fecha_od_raw, resumen}

    URL: https://www.hcdn.gob.ar/proyectos/resultadoList.html?tipo=1&estado=&periodo={anio}&pagina=N
    tipo=1 → Orden del Día (ya tiene dictamen de comisión)
    """
    resultados = []
    base_url = f"{HCDN_PROYECTOS_BASE}/resultadoList.html"

    print(f"  [SIL-HTML] Scrapeando Órdenes del Día {anio}...")

    for pagina in range(1, max_paginas + 1):
        params = {
            "tipo": "1",        # Orden del Día
            "estado": "",
            "periodo": str(anio),
            "pagina": str(pagina),
        }
        try:
            r = requests.get(base_url, params=params, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            # Buscar la tabla de resultados
            tabla = soup.find("table", {"class": re.compile("table", re.I)})
            if not tabla:
                tabla = soup.find("table")

            if not tabla:
                if pagina == 1:
                    print(f"  [SIL-HTML] No se encontró tabla en página {pagina}")
                break

            filas = tabla.find_all("tr")[1:]  # saltar header
            if not filas:
                break

            pagina_vacia = True
            for fila in filas:
                cols = fila.find_all("td")
                if len(cols) < 3:
                    continue

                pagina_vacia = False
                textos = [c.get_text(strip=True) for c in cols]

                # Buscar expediente (patrón: NNNN-tipo-YYYY)
                expediente = ""
                for t in textos:
                    if re.match(r"\d{4}-[A-Z]-\d{4}", t):
                        expediente = t
                        break

                # Si no hay expediente directo, buscarlo en links
                if not expediente:
                    links = fila.find_all("a", href=True)
                    for link in links:
                        m = re.search(r"(\d{4}-[A-Za-z]+-\d{4})", link.get("href", ""))
                        if m:
                            expediente = m.group(1).upper()
                            break

                # Buscar fechas (formato dd/mm/yyyy)
                fechas = []
                for t in textos:
                    m = re.search(r"\d{2}/\d{2}/\d{4}", t)
                    if m:
                        fechas.append(m.group(0))

                fecha_ingreso_raw = fechas[0] if len(fechas) > 0 else ""
                fecha_od_raw = fechas[1] if len(fechas) > 1 else ""

                # Tipo y resumen
                tipo = textos[1] if len(textos) > 1 else ""
                resumen = textos[-1][:200] if textos else ""

                if expediente:
                    resultados.append({
                        "expediente": expediente,
                        "tipo": tipo,
                        "fecha_ingreso_raw": fecha_ingreso_raw,
                        "fecha_od_raw": fecha_od_raw,
                        "resumen": resumen,
                    })

            if pagina_vacia:
                break

        except Exception as e:
            print(f"  [SIL-HTML] Error en página {pagina}: {e}")
            break

        time.sleep(PAUSA_ENTRE_REQUESTS)

    print(f"  [SIL-HTML] {len(resultados)} Órdenes del Día encontradas")
    return resultados


def _html_scrape_proyectos_general(anio: int, max_paginas: int = 30) -> list[dict]:
    """
    Scrapea el listado general de proyectos del HCDN con fecha de ingreso.
    URL: https://www.hcdn.gob.ar/proyectos/resultadoList.html?tipo=0&estado=0&periodo={anio}&pagina=N
    """
    resultados = []
    base_url = f"{HCDN_PROYECTOS_BASE}/resultadoList.html"

    print(f"  [SIL-HTML] Scrapeando proyectos generales {anio}...")

    for pagina in range(1, max_paginas + 1):
        params = {
            "tipo": "0",
            "estado": "0",
            "periodo": str(anio),
            "pagina": str(pagina),
        }
        try:
            r = requests.get(base_url, params=params, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            tabla = soup.find("table")
            if not tabla:
                break

            filas = tabla.find_all("tr")[1:]
            if not filas:
                break

            pagina_vacia = True
            for fila in filas:
                cols = fila.find_all("td")
                if len(cols) < 3:
                    continue

                pagina_vacia = False
                textos = [c.get_text(strip=True) for c in cols]

                # Expediente
                expediente = ""
                for t in textos:
                    if re.match(r"\d{4}-[A-Z]+-\d{4}", t) or re.match(r"\d{4}-[A-Z]-\d{4}", t):
                        expediente = t.upper()
                        break

                if not expediente:
                    links = fila.find_all("a", href=True)
                    for link in links:
                        m = re.search(r"(\d{4}-[A-Za-z]+-\d{4})", link.get("href", ""))
                        if m:
                            expediente = m.group(1).upper()
                            break

                # Autor / firmantes
                autor = ""
                for col in cols:
                    texto = col.get_text(strip=True)
                    # El autor suele estar en mayúsculas: "APELLIDO, Nombre"
                    if re.match(r"[A-ZÁÉÍÓÚÑ]{3,}", texto) and "," in texto:
                        autor = texto.upper()
                        break

                # Fecha
                fecha_ingreso_raw = ""
                for t in textos:
                    m = re.search(r"\d{2}/\d{2}/\d{4}", t)
                    if m:
                        fecha_ingreso_raw = m.group(0)
                        break

                # Estado
                estado = textos[2] if len(textos) > 2 else ""

                if expediente:
                    resultados.append({
                        "expediente": expediente,
                        "autor": autor,
                        "fecha_ingreso_raw": fecha_ingreso_raw,
                        "estado": estado,
                    })

            if pagina_vacia:
                break

        except Exception as e:
            print(f"  [SIL-HTML] Error página {pagina}: {e}")
            break

        time.sleep(PAUSA_ENTRE_REQUESTS)

    print(f"  [SIL-HTML] {len(resultados)} proyectos generales encontrados")
    return resultados


# ---------------------------------------------------------------------------
# Cálculo de TPMP
# ---------------------------------------------------------------------------
def _calcular_tpmp(df: pd.DataFrame) -> dict:
    """
    Calcula el TPMP a partir de un DataFrame con columnas:
      fecha_ingreso (date), fecha_dictamen (date)

    Retorna dict con:
      valor        : float (días promedio)
      n_proyectos  : int (proyectos con ambas fechas disponibles)
      min_dias     : int
      max_dias     : int
      mediana_dias : float
      fuente       : str
    """
    if df.empty or "fecha_ingreso" not in df.columns or "fecha_dictamen" not in df.columns:
        return _tpmp_fallback("DataFrame vacío o sin columnas de fecha")

    # Calcular diferencias
    df = df.dropna(subset=["fecha_ingreso", "fecha_dictamen"]).copy()
    if df.empty:
        return _tpmp_fallback("Sin proyectos con ambas fechas")

    df["dias"] = (df["fecha_dictamen"] - df["fecha_ingreso"]).dt.days

    # Filtrar negativos y outliers
    df = df[(df["dias"] >= 0) & (df["dias"] <= MAX_DIAS_MADURACION)]
    if df.empty:
        return _tpmp_fallback("Sin proyectos con días válidos")

    valor = round(df["dias"].mean(), 1)
    return {
        "valor": valor,
        "unidad": "días",
        "n_proyectos": len(df),
        "min_dias": int(df["dias"].min()),
        "max_dias": int(df["dias"].max()),
        "mediana_dias": round(df["dias"].median(), 1),
        "fuente": "SIL real",
        "nota": f"TPMP calculado sobre {len(df)} proyectos con dictamen",
    }


def _tpmp_fallback(razon: str) -> dict:
    """Retorna el valor de referencia cuando no hay datos reales."""
    print(f"  [SIL] Usando TPMP de referencia — {razon}")
    return {
        "valor": 105.0,
        "unidad": "días",
        "n_proyectos": 0,
        "min_dias": None,
        "max_dias": None,
        "mediana_dias": None,
        "fuente": "estimación (rango histórico 30-180 días)",
        "nota": f"Dato de referencia. Razón: {razon}",
        "advertencia": "⚠️ Requiere conexión al SIL para valor real",
    }


# ---------------------------------------------------------------------------
# Función principal: calcular_tpmp
# ---------------------------------------------------------------------------
def calcular_tpmp(anio: int = None) -> dict:
    """
    Calcula el TPMP usando las mejores fuentes disponibles.

    Estrategia:
      1. Intenta CKAN API — si tiene campos de fecha, los usa
      2. Intenta HTML scraping de Órdenes del Día (fecha_ingreso + fecha_od)
      3. Fallback a valor de referencia

    Retorna:
      dict con valor, fuente, metadatos
    """
    anio = anio or datetime.now().year
    print(f"\n{'='*55}")
    print(f"  TPMP — Tiempo Promedio de Maduración de Proyectos")
    print(f"  Año: {anio}")
    print(f"{'='*55}")

    proyectos_df = pd.DataFrame()
    fuente_usada = "ninguna"

    # ── Intentar CKAN API ─────────────────────────────────────────────────────
    try:
        campos = _ckan_info_campos()
        campo_ingreso, campo_dictamen = _ckan_buscar_campos_fecha(campos)

        df_ckan = _ckan_descargar_proyectos(anio, campos_extra=campos)

        if not df_ckan.empty:
            # Parsear fechas
            df_ckan["fecha_ingreso"] = pd.to_datetime(
                df_ckan["fecha_ingreso_raw"].apply(_parse_fecha),
                errors="coerce"
            )
            if campo_dictamen:
                df_ckan["fecha_dictamen"] = pd.to_datetime(
                    df_ckan["fecha_dictamen_raw"].apply(_parse_fecha),
                    errors="coerce"
                )
            else:
                df_ckan["fecha_dictamen"] = pd.NaT

            # Verificar si tenemos fechas de dictamen reales
            con_dictamen = df_ckan["fecha_dictamen"].notna().sum()
            print(f"  [SIL-CKAN] Proyectos con fecha_dictamen: {con_dictamen}")

            if con_dictamen > 10:
                proyectos_df = df_ckan[["expediente", "autor", "tipo", "estado",
                                        "fecha_ingreso", "fecha_dictamen"]].copy()
                fuente_usada = "CKAN API"

    except Exception as e:
        print(f"  [SIL-CKAN] Falló: {e}")

    # ── Si CKAN no tiene dictamen, intentar HTML cruzando OD con proyectos ───
    if proyectos_df.empty or proyectos_df["fecha_dictamen"].notna().sum() < 5:
        try:
            print(f"\n  [SIL-HTML] Intentando scraping HTML...")

            # Obtener OD (proyectos con dictamen) con ambas fechas
            od_list = _html_scrape_ordenes_del_dia(anio, max_paginas=15)

            if od_list:
                df_od = pd.DataFrame(od_list)
                df_od["fecha_ingreso"] = pd.to_datetime(
                    df_od["fecha_ingreso_raw"].apply(_parse_fecha),
                    errors="coerce"
                )
                df_od["fecha_dictamen"] = pd.to_datetime(
                    df_od["fecha_od_raw"].apply(_parse_fecha),
                    errors="coerce"
                )
                df_od = df_od.rename(columns={"fecha_od_raw": "fecha_dictamen_raw"})
                df_od["autor"] = ""  # OD no siempre tiene autor en el listado
                df_od["estado"] = "Con dictamen"

                # Si tenemos datos de proyectos generales, cruzar para obtener autores
                if not proyectos_df.empty and "autor" in proyectos_df.columns:
                    autor_map = proyectos_df.dropna(subset=["expediente"]).set_index(
                        "expediente"
                    )["autor"].to_dict()
                    df_od["autor"] = df_od["expediente"].map(autor_map).fillna("")
                else:
                    # Intentar scraping general para autores
                    gen_list = _html_scrape_proyectos_general(anio, max_paginas=20)
                    if gen_list:
                        df_gen = pd.DataFrame(gen_list)
                        autor_map = df_gen.dropna(subset=["expediente"]).set_index(
                            "expediente"
                        )["autor"].to_dict()
                        df_od["autor"] = df_od["expediente"].map(autor_map).fillna("")

                proyectos_df = df_od
                fuente_usada = "HTML HCDN (Órdenes del Día)"

            elif od_list == []:
                # Sin resultados HTML, intentar año anterior
                anio_prev = anio - 1
                print(f"  [SIL-HTML] Sin resultados para {anio}, probando {anio_prev}...")
                od_list = _html_scrape_ordenes_del_dia(anio_prev, max_paginas=10)
                if od_list:
                    df_od = pd.DataFrame(od_list)
                    df_od["fecha_ingreso"] = pd.to_datetime(
                        df_od["fecha_ingreso_raw"].apply(_parse_fecha), errors="coerce"
                    )
                    df_od["fecha_dictamen"] = pd.to_datetime(
                        df_od["fecha_od_raw"].apply(_parse_fecha), errors="coerce"
                    )
                    df_od["autor"] = ""
                    df_od["estado"] = "Con dictamen"
                    proyectos_df = df_od
                    fuente_usada = f"HTML HCDN OD ({anio_prev})"

        except Exception as e:
            print(f"  [SIL-HTML] Falló: {e}")

    # ── Calcular TPMP ─────────────────────────────────────────────────────────
    resultado = _calcular_tpmp(proyectos_df)
    resultado["fuente"] = fuente_usada if resultado.get("n_proyectos", 0) > 0 else resultado.get("fuente")
    resultado["anio"] = anio
    resultado["timestamp"] = datetime.now().isoformat()

    print(f"\n  📊 TPMP = {resultado['valor']} días ({resultado['fuente']})")
    if resultado.get("n_proyectos"):
        print(f"     Proyectos: {resultado['n_proyectos']} | "
              f"Min: {resultado.get('min_dias')} | "
              f"Mediana: {resultado.get('mediana_dias')} | "
              f"Max: {resultado.get('max_dias')}")

    # ── Guardar proyectos ─────────────────────────────────────────────────────
    if not proyectos_df.empty:
        ruta_proy = os.path.join(DATA_DIR, "sil_proyectos.csv")
        proyectos_df.to_csv(ruta_proy, index=False, encoding="utf-8-sig")
        print(f"  💾 Guardado: {ruta_proy} ({len(proyectos_df)} proyectos)")

    # ── Guardar resultado JSON ────────────────────────────────────────────────
    ruta_json = os.path.join(DATA_DIR, "tpmp_resultado.json")
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"  💾 Guardado: {ruta_json}")

    return resultado


# ---------------------------------------------------------------------------
# Función: obtener_proyectos_por_diputado
# ---------------------------------------------------------------------------
def obtener_proyectos_por_diputado(anio: int = None) -> pd.DataFrame:
    """
    Obtiene el resumen de proyectos por diputado desde el SIL.

    Campos por diputado:
      apellido, presentados, con_dictamen, tasa_dictamen_pct

    Fuentes:
      - CKAN API (principal)
      - HTML scraping general (fallback)

    Retorna DataFrame listo para merge con data/diputados.json
    """
    anio = anio or datetime.now().year
    print(f"\n  [SIL] Proyectos por diputado — año {anio}")

    df = pd.DataFrame()

    # ── Intentar desde CSV ya generado por calcular_tpmp ─────────────────────
    ruta_proy = os.path.join(DATA_DIR, "sil_proyectos.csv")
    if os.path.exists(ruta_proy):
        try:
            df = pd.read_csv(ruta_proy, encoding="utf-8-sig")
            print(f"  [SIL] Usando sil_proyectos.csv ({len(df)} registros)")
        except Exception:
            pass

    # ── Si no hay CSV, intentar CKAN ─────────────────────────────────────────
    if df.empty:
        try:
            campos = _ckan_info_campos()
            df = _ckan_descargar_proyectos(anio, campos_extra=campos)
        except Exception as e:
            print(f"  [SIL] CKAN falló: {e}")

    # ── Si no hay datos, intentar HTML ───────────────────────────────────────
    if df.empty:
        try:
            gen_list = _html_scrape_proyectos_general(anio, max_paginas=25)
            if gen_list:
                df = pd.DataFrame(gen_list)
        except Exception as e:
            print(f"  [SIL] HTML falló: {e}")

    if df.empty:
        print("  [SIL] Sin datos de proyectos — retornando DataFrame vacío")
        return pd.DataFrame()

    # ── Normalizar autor → apellido ───────────────────────────────────────────
    if "autor" not in df.columns:
        df["autor"] = ""

    df["apellido"] = df["autor"].apply(_normalizar_apellido)
    df = df[df["apellido"].str.len() >= 3]

    # ── Estado: detectar si tiene dictamen ───────────────────────────────────
    if "estado" not in df.columns:
        df["estado"] = ""

    def _tiene_dictamen(estado: str) -> bool:
        e = str(estado).upper()
        return any(x in e for x in ["DICTAMEN", "OD", "SANCIONADO", "LEY", "APROBADO"])

    df["con_dictamen"] = df["estado"].apply(_tiene_dictamen)

    # ── Si tenemos fecha_dictamen como columna, usarla también ───────────────
    if "fecha_dictamen" in df.columns:
        df["con_dictamen"] = df["con_dictamen"] | df["fecha_dictamen"].notna()

    # ── Agregar por apellido ──────────────────────────────────────────────────
    resumen = (
        df.groupby("apellido")
        .agg(
            presentados=("apellido", "count"),
            con_dictamen=("con_dictamen", "sum"),
        )
        .reset_index()
    )
    resumen["con_dictamen"] = resumen["con_dictamen"].astype(int)
    resumen["tasa_dictamen_pct"] = (
        resumen["con_dictamen"] / resumen["presentados"] * 100
    ).round(1)

    # ── Guardar ───────────────────────────────────────────────────────────────
    ruta_out = os.path.join(DATA_DIR, "sil_por_diputado.csv")
    resumen.to_csv(ruta_out, index=False, encoding="utf-8-sig")
    print(f"  💾 sil_por_diputado.csv — {len(resumen)} diputados")

    # Resumen top
    top = resumen.nlargest(5, "presentados")
    print(f"\n  🏆 Top 5 por proyectos presentados:")
    for _, r in top.iterrows():
        print(f"     {r['apellido']}: {r['presentados']} proyectos "
              f"({r['con_dictamen']} con dictamen, {r['tasa_dictamen_pct']}%)")

    return resumen


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    anio = datetime.now().year
    print("=" * 60)
    print(f"  SCRAPER SIL — Monitor Legislativo v1.1")
    print(f"  Año: {anio}")
    print("=" * 60)

    tpmp = calcular_tpmp(anio)
    print(f"\n✅ TPMP: {tpmp['valor']} días")

    df_dip = obtener_proyectos_por_diputado(anio)
    print(f"✅ Proyectos por diputado: {len(df_dip)} diputados")