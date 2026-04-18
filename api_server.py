"""
scraper_pipeline.py
===================
Pipeline unificado de automatizacion de datos para monitor_legistativo (Diputados).
Genera data/diputados.json con todos los campos necesarios para el dashboard.

Fuentes:
  - diputados.gov.ar          → nomina + genero
  - hcdn.gob.ar/secparl/dclp  → asistencia por diputado
  - hcdn.gob.ar/proyectos/     → proyectos presentados / aprobados
  - presupuestoabierto.gob.ar  → ejecucion presupuestaria (API REST)
  - votaciones.hcdn.gob.ar     → votaciones nominales (IQP)

NO modifica ningun archivo HTML existente.
El HTML debe leer data/diputados.json en tiempo de ejecucion (cuando sirve desde Railway).
Para entorno local file:// el JSON se inyecta via inject_json_to_html.py (ver abajo).

Uso:
    python scraper_pipeline.py              # corre todo el pipeline
    python scraper_pipeline.py --step nomina
    python scraper_pipeline.py --step asistencia
    python scraper_pipeline.py --step proyectos
    python scraper_pipeline.py --step presupuesto
    python scraper_pipeline.py --step votaciones
"""

import argparse
import json
import os
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "diputados.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MonitorLegislativo/1.0)"}
TIMEOUT = 60  # el SIL es lento

# Nombres femeninos frecuentes en Argentina para deteccion de genero
# (fallback heuristico; el campo genero del scraper tiene prioridad)
_NOMBRES_F = {
    "maria", "ana", "laura", "sandra", "carolina", "andrea", "patricia",
    "monica", "claudia", "vanesa", "natalia", "silvana", "roxana", "graciela",
    "marcela", "liliana", "karina", "alejandra", "veronica", "gabriela",
    "paula", "cecilia", "florencia", "lucia", "mariana", "victoria", "beatriz",
    "norma", "susana", "stella", "mabel", "alba", "irma", "nilda", "elsa",
    "rosa", "olga", "mirta", "gladys", "silvia", "cristina", "romina",
    "lorena", "sabrina", "yamila", "celeste", "brenda", "magali", "soledad",
    "cintia", "noelia", "melisa", "valeria", "agustina", "micaela", "jimena",
    "antonella", "josefina", "belen", "pilar", "mercedes", "ines", "teresa",
    "nora", "alicia", "amanda", "esther", "estela", "amalia", "elvira",
    "adelaida", "griselda", "alejandrina", "rebeca", "eugenia", "marta"
}


def _detect_gender(nombre):
    """Heuristica de genero por primer nombre. Devuelve 'F', 'M' o 'ND'."""
    parts = nombre.lower().split()
    if not parts:
        return "ND"
    # apellido primero: "GARCIA, Maria" → tomar despues de la coma
    if "," in nombre:
        after_comma = nombre.split(",", 1)[1].strip().lower().split()
        primer = after_comma[0] if after_comma else parts[0]
    else:
        primer = parts[0]
    primer = re.sub(r"[^a-z]", "", primer)
    if primer in _NOMBRES_F:
        return "F"
    return "M"


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_existing():
    """Carga el JSON existente para hacer merge incremental."""
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"meta": {}, "diputados": [], "presupuesto": {}, "votaciones": {}}


def save(data):
    data["meta"]["ultima_actualizacion"] = datetime.now().isoformat()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] {OUTPUT_FILE} guardado ({len(data['diputados'])} diputados)")


# ---------------------------------------------------------------------------
# STEP 1 — Nomina + Genero
# ---------------------------------------------------------------------------
def scrape_nomina():
    """
    Fuente: https://www.diputados.gov.ar/diputados/
    Campos obtenidos: nombre, distrito, bloque, mandato_hasta, genero
    """
    print("[STEP 1] Scraping nomina de diputados...")
    url = "https://www.diputados.gov.ar/diputados/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        tabla = soup.find("table")
        if not tabla:
            print("[WARN] No se encontro tabla en diputados.gov.ar")
            return []

        diputados = []
        filas = tabla.find_all("tr")[1:]
        for fila in filas:
            cols = fila.find_all("td")
            if len(cols) < 4:
                continue
            nombre = cols[1].get_text(strip=True)
            distrito = cols[2].get_text(strip=True)
            bloque = cols[3].get_text(strip=True)
            # Columna de mandato puede variar; intentar col 4 si existe
            mandato_hasta = cols[4].get_text(strip=True) if len(cols) > 4 else ""
            diputados.append({
                "nombre": nombre,
                "distrito": distrito,
                "bloque": bloque,
                "mandato_hasta": mandato_hasta,
                "genero": _detect_gender(nombre),  # mejorar con datos oficiales
                "asistencia_pct": None,
                "proyectos_presentados": None,
                "proyectos_aprobados": None,
                "iqp": None
            })
        print(f"[OK] {len(diputados)} diputados encontrados")
        return diputados
    except Exception as e:
        print(f"[ERROR] scrape_nomina: {e}")
        return []


# ---------------------------------------------------------------------------
# STEP 2 — Asistencia por diputado
# ---------------------------------------------------------------------------
def scrape_asistencia(diputados):
    """
    Fuente: PDF de estadisticas de asistencia en www3.hcdn.gob.ar
    El sitio www2.hcdn.gob.ar/secparl/dclp/asistencia.html lista los PDFs por periodo.
    Descargamos el PDF del periodo ordinario mas reciente y parseamos con pdfplumber.

    El PDF tiene lineas con formato: "APELLIDO, Nombre   distrito   sesiones   presentes   %"
    """
    print("[STEP 2] Descargando PDF de asistencia (periodo 143 ordinario 2025)...")

    # PDF del periodo 143 ordinario 2025 (antes de la renovacion de diciembre 2025)
    # Es el mas reciente con datos de todo el anio legislativo de los 257 actuales
    PDF_URL = "https://www3.hcdn.gob.ar/dependencias/dclp/asistencia/periodo%20143/ESTADISTICAS.pdf"

    try:
        import pdfplumber
    except ImportError:
        print("[WARN] pdfplumber no instalado. Instalar con: pip install pdfplumber")
        print("       Saltando step de asistencia.")
        return diputados

    try:
        res = requests.get(PDF_URL, headers=HEADERS, timeout=TIMEOUT, stream=True)
        res.raise_for_status()

        import io
        pdf_bytes = io.BytesIO(res.content)
        asistencia_map = {}

        with pdfplumber.open(pdf_bytes) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for line in text.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    # Buscar lineas con porcentaje al final: numero con % o numero decimal
                    parts = line.split()
                    if len(parts) < 3:
                        continue
                    # El porcentaje suele ser el ultimo campo
                    pct_raw = parts[-1].replace("%", "").replace(",", ".")
                    try:
                        pct = float(pct_raw)
                        if 0 <= pct <= 100:
                            # El nombre es el inicio de la linea (todo en mayusculas)
                            nombre_raw = " ".join(parts[:-3]).upper().strip()
                            if nombre_raw:
                                asistencia_map[nombre_raw] = pct
                    except ValueError:
                        pass

        print(f"[INFO] {len(asistencia_map)} entradas en el PDF de asistencia")

        # Match por apellido (primera palabra antes de la coma)
        matched = 0
        for d in diputados:
            nombre_key = d["nombre"].upper().strip()
            apellido = nombre_key.split(",")[0].strip()

            # Match exacto primero
            if nombre_key in asistencia_map:
                d["asistencia_pct"] = asistencia_map[nombre_key]
                matched += 1
                continue

            # Match por apellido parcial
            for k, v in asistencia_map.items():
                if apellido and apellido in k:
                    d["asistencia_pct"] = v
                    matched += 1
                    break

        # Calcular NAPE
        for d in diputados:
            if d.get("asistencia_pct") is not None:
                d["nape"] = round(1 - d["asistencia_pct"] / 100, 4)

        print(f"[OK] Asistencia matcheada para {matched}/{len(diputados)} diputados")

    except Exception as e:
        print(f"[ERROR] scrape_asistencia: {e}")

    return diputados


# ---------------------------------------------------------------------------
# STEP 3 — Proyectos (SIL / hcdn.gob.ar/proyectos)
# ---------------------------------------------------------------------------
def scrape_proyectos(diputados):
    """
    Fuente: API CKAN de datos.hcdn.gob.ar con paginacion.
    Resource ID fijo: 22b2d52c-7a0e-426b-ac0a-a3326c388ba6
    Incluye proyectos del anio actual Y el anterior (el periodo 144 arranca en marzo 2026
    pero el dataset puede tener datos cargados bajo expedientes -D-2025).
    """
    print("[STEP 3] Consultando API CKAN de proyectos parlamentarios...")
    anio = str(datetime.now().year)
    anio_prev = str(int(anio) - 1)

    RESOURCE_ID = "22b2d52c-7a0e-426b-ac0a-a3326c388ba6"
    API_URL = "https://datos.hcdn.gob.ar/api/3/action/datastore_search"

    proyectos_map = {}
    offset = 0
    limit = 1000
    total_procesados = 0

    try:
        while True:
            res = requests.get(
                API_URL,
                params={"resource_id": RESOURCE_ID, "limit": limit, "offset": offset},
                headers=HEADERS,
                timeout=60
            )
            res.raise_for_status()
            data = res.json()
            records = data.get("result", {}).get("records", [])
            if not records:
                break

            for row in records:
                # Campo real: EXP_DIPUTADOS con formato "1234-D-2025"
                expediente = str(row.get("EXP_DIPUTADOS") or "")
                if anio not in expediente and anio_prev not in expediente:
                    continue

                # Campo real: AUTOR (un solo autor por fila, no multiples)
                firmantes_raw = (row.get("AUTOR") or "").upper()
                estado = (row.get("TIPO") or "").upper()
                total_procesados += 1

                # AUTOR tiene formato "APELLIDO, NOMBRE" — tomar apellido
                apellido = firmantes_raw.split(",")[0].strip()
                if len(apellido) < 3:
                    continue
                if apellido not in proyectos_map:
                    proyectos_map[apellido] = {"presentados": 0, "aprobados": 0}
                proyectos_map[apellido]["presentados"] += 1
                if any(x in estado for x in ("LEY", "SANCIONADO", "APROBADO")):
                    proyectos_map[apellido]["aprobados"] += 1

            total_available = data.get("result", {}).get("total", 0)
            offset += limit
            if offset >= total_available:
                break

        print(f"[INFO] {total_procesados} proyectos ({anio_prev}-{anio}), {len(proyectos_map)} autores")

        matched = 0
        for d in diputados:
            apellido = d["nombre"].split(",")[0].strip().upper()
            if len(apellido) >= 3 and apellido in proyectos_map:
                d["proyectos_presentados"] = proyectos_map[apellido]["presentados"]
                d["proyectos_aprobados"] = proyectos_map[apellido]["aprobados"]
                matched += 1

        print(f"[OK] Proyectos matcheados para {matched}/{len(diputados)} diputados")

    except Exception as e:
        print(f"[ERROR] scrape_proyectos: {e}")

    return diputados


# ---------------------------------------------------------------------------
# STEP 4 — Ejecucion presupuestaria (Presupuesto Abierto API REST)
# ---------------------------------------------------------------------------
def scrape_presupuesto():
    """
    Fuente: API de ejecucion presupuestaria de la ONP (Oficina Nacional de Presupuesto).
    URL: https://www.economia.gob.ar/onp/ejecucion/
    Endpoint de datos abiertos que devuelve ejecucion por jurisdiccion en JSON.
    Jurisdiccion 01 = Poder Legislativo / Congreso de la Nacion.

    Alternativa: presupuestoabierto.gob.ar tiene CSV descargables por anio.
    """
    print("[STEP 4] Consultando ejecucion presupuestaria (ONP)...")
    anio = datetime.now().year

    # La ONP publica archivos CSV de ejecucion presupuestaria en datos abiertos
    # URL del CSV de ejecucion anual (estructura: jurisdiccion, credito, devengado)
    # Nota: para 2025/2026 Argentina prorrogo el presupuesto 2023 (Dec. 88/2023)
    CSV_URLS = [
        f"https://www.presupuestoabierto.gob.ar/datasets/credito_jurisdiccion_{anio}.csv",
        f"https://www.presupuestoabierto.gob.ar/datasets/credito_{anio}.csv",
        # El archivo de ejecucion historica consolidada
        "https://infra.datos.gob.ar/catalog/modernizacion/dataset/7/distribution/7.1/download/presupuesto-nacionale-gasto-por-finalidad-funcion-desde-1963.csv",
    ]

    import csv, io
    for url in CSV_URLS:
        try:
            res = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if res.status_code != 200:
                continue
            content = res.content.decode("utf-8", errors="replace")
            reader = csv.DictReader(io.StringIO(content))
            credito = devengado = 0.0
            for row in reader:
                jur = str(row.get("jurisdiccion") or row.get("cod_jurisdiccion") or "")
                desc = (row.get("desc_jurisdiccion") or row.get("jurisdiccion_desc") or "").upper()
                if jur.strip() == "01" or "LEGISLATIVO" in desc or "CONGRESO" in desc:
                    credito += float(str(row.get("credito_vigente") or row.get("credito") or "0").replace(",", ".") or 0)
                    devengado += float(str(row.get("devengado") or row.get("ejecutado") or "0").replace(",", ".") or 0)
            if credito > 0:
                iap = round(devengado / credito, 4)
                print(f"[OK] IAP={iap} (credito={credito/1e9:.1f}B, devengado={devengado/1e9:.1f}B ARS)")
                return {"ejercicio": anio, "fuente": url, "credito_vigente_m": round(credito/1e6, 2), "devengado_m": round(devengado/1e6, 2), "iap": iap}
        except Exception as e:
            print(f"[WARN] {url[:70]}: {e}")

    # Fallback estatico con datos reales del IAP historico del Congreso
    # Fuente: OPC informes trimestrales 2024 — IAP del Legislativo ~0.951
    print("[WARN] CSV de presupuesto no disponible — usando valor historico de referencia")
    return {
        "ejercicio": anio,
        "fuente": "historico OPC 2024",
        "nota": "IAP estimado en base a ejecucion 2024 (95.1%). Actualizar con datos de opc.gob.ar",
        "credito_vigente_m": None,
        "devengado_m": None,
        "iap": 0.951
    }


# ---------------------------------------------------------------------------
# STEP 5 — Votaciones nominales (IQP por diputado)
# ---------------------------------------------------------------------------
def scrape_votaciones(diputados):
    """
    Fuente: Portal de Datos Abiertos HCDN - dataset votaciones nominales
    El dataset tiene una fila por voto individual: legislador x votacion x resultado.
    Se calcula IQP = votos_emitidos / total_votaciones_convocado.
    """
    print("[STEP 5] Consultando votaciones nominales...")
    anio = str(datetime.now().year)
    anio_prev = str(int(anio) - 1)

    # Opcion 1: API interna de votaciones.hcdn.gob.ar
    # Probar distintas versiones del endpoint
    try:
        periodo = 144 if int(anio) >= 2026 else 143
        api_base = "https://votaciones.hcdn.gob.ar"

        # Probar endpoints conocidos
        endpoints = [
            f"/api/v1/actas/?periodo={periodo}&page_size=50",
            f"/api/actas/?periodo={periodo}",
            f"/votos/?periodo={periodo}",
        ]

        actas = []
        for ep in endpoints:
            try:
                res = requests.get(f"{api_base}{ep}", headers=HEADERS, timeout=20)
                print(f"[INFO] {ep} → {res.status_code}")
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list):
                        actas = data
                    elif isinstance(data, dict):
                        actas = data.get("results") or data.get("data") or data.get("actas") or []
                    if actas:
                        break
            except Exception:
                continue

        conteo = {}
        for acta in actas[:30]:
            acta_id = acta.get("id") or acta.get("acta_id")
            if not acta_id:
                continue
            for ep_votos in [f"/api/v1/actas/{acta_id}/votos/", f"/api/actas/{acta_id}/votos/"]:
                try:
                    res2 = requests.get(f"{api_base}{ep_votos}", headers=HEADERS, timeout=20)
                    if res2.status_code != 200:
                        continue
                    votos_data = res2.json()
                    votos_list = votos_data if isinstance(votos_data, list) else (votos_data.get("results") or [])
                    for v in votos_list:
                        nombre = (v.get("diputado_nombre") or v.get("legislador") or v.get("nombre") or "").upper().strip()
                        voto = (v.get("voto") or "").upper().strip()
                        apellido = nombre.split(",")[0].strip() if "," in nombre else nombre.split()[0].strip()
                        if len(apellido) < 3:
                            continue
                        if apellido not in conteo:
                            conteo[apellido] = {"c": 0, "e": 0}
                        conteo[apellido]["c"] += 1
                        if voto and "AUSENTE" not in voto:
                            conteo[apellido]["e"] += 1
                    break
                except Exception:
                    continue

        if conteo:
            matched = sum(1 for d in diputados
                         if d["nombre"].split(",")[0].strip().upper() in conteo
                         and conteo[d["nombre"].split(",")[0].strip().upper()]["c"] > 0)
            for d in diputados:
                ap = d["nombre"].split(",")[0].strip().upper()
                if ap in conteo and conteo[ap]["c"] > 0:
                    d["iqp"] = round(conteo[ap]["e"] / conteo[ap]["c"], 4)
            if matched > 0:
                print(f"[OK] IQP (API votaciones periodo {periodo}) para {matched}/{len(diputados)} diputados")
                return diputados
            else:
                print(f"[WARN] API votaciones respondio pero sin matches con los diputados actuales")
        else:
            print(f"[WARN] API votaciones.hcdn.gob.ar: ningun endpoint funciono o sin actas para periodo {periodo}")

    except Exception as e:
        print(f"[WARN] API votaciones.hcdn.gob.ar: {e}")

    # El dataset CKAN de votaciones (periodos 129-137) es historico y no tiene datos 2025/2026.
    # El sitio votaciones.hcdn.gob.ar carga sus estadisticas via JavaScript (no parseable con requests).
    # IQP queda en null hasta que la HCDN publique un dataset actualizado o habilite una API publica.
    print("[WARN] IQP no disponible para el periodo actual.")
    print("       Fuente pendiente: dataset votaciones 2025/2026 en datos.hcdn.gob.ar")
    return diputados


# ---------------------------------------------------------------------------
# STEP 6 — TPMP (SIL: fechas ingreso y dictamen) [v1.1]
# ---------------------------------------------------------------------------
def scrape_tpmp(anio: int = None) -> dict:
    """
    Calcula el TPMP usando el scraper SIL.
    Retorna dict con valor y metadatos para incluir en data/diputados.json.
    """
    print("[STEP 6] Calculando TPMP (Tiempo Promedio de Maduración de Proyectos)...")
    anio = anio or datetime.now().year
    try:
        from scrapers.sil import calcular_tpmp, obtener_proyectos_por_diputado
        resultado = calcular_tpmp(anio)
        return resultado
    except ImportError as e:
        print(f"[WARN] scrapers/sil.py no disponible: {e}")
    except Exception as e:
        print(f"[WARN] Error en TPMP: {e}")

    # Fallback
    return {
        "valor": 105.0,
        "unidad": "días",
        "n_proyectos": 0,
        "fuente": "fallback (scrapers/sil.py no disponible)",
        "advertencia": "⚠️ Instalar scrapers/sil.py para datos reales",
    }


def _enriquecer_diputados_con_sil(diputados: list[dict], anio: int = None) -> list[dict]:
    """
    Enriquece la lista de diputados con datos del SIL:
      - sil_presentados:     proyectos presentados (dato SIL, más completo que CKAN)
      - sil_con_dictamen:    proyectos que llegaron a dictamen
      - sil_tasa_dictamen:   % de proyectos con dictamen
    """
    anio = anio or datetime.now().year
    try:
        from scrapers.sil import obtener_proyectos_por_diputado
        df_sil = obtener_proyectos_por_diputado(anio)

        if df_sil.empty:
            return diputados

        # Crear mapa de apellido → datos SIL
        sil_map = df_sil.set_index("apellido").to_dict("index")

        matcheados = 0
        for d in diputados:
            apellido = d.get("nombre", "").split(",")[0].strip().upper()
            if apellido in sil_map:
                d["sil_presentados"] = int(sil_map[apellido].get("presentados", 0))
                d["sil_con_dictamen"] = int(sil_map[apellido].get("con_dictamen", 0))
                d["sil_tasa_dictamen"] = float(sil_map[apellido].get("tasa_dictamen_pct", 0))

                # Si los datos del pipeline (CKAN) son nulos, usar datos SIL
                if not d.get("proyectos_presentados"):
                    d["proyectos_presentados"] = d["sil_presentados"]
                if not d.get("proyectos_aprobados"):
                    d["proyectos_aprobados"] = d["sil_con_dictamen"]
                matcheados += 1

        print(f"[OK] SIL: datos enriquecidos para {matcheados}/{len(diputados)} diputados")

    except Exception as e:
        print(f"[WARN] Error enriqueciendo con SIL: {e}")

    return diputados


# ---------------------------------------------------------------------------
# STEP 7 — ITC (actas de reuniones de comisión) [v1.1]
# ---------------------------------------------------------------------------
def scrape_itc(anio: int = None) -> dict:
    """
    Calcula el ITC usando el scraper de comisiones.
    Retorna dict con valor y metadatos.
    """
    print("[STEP 7] Calculando ITC (Índice de Trabajo en Comisiones)...")
    anio = anio or datetime.now().year
    try:
        from scrapers.comisiones import calcular_itc
        resultado = calcular_itc(anio, max_comisiones=20)
        return resultado
    except ImportError as e:
        print(f"[WARN] scrapers/comisiones.py no disponible: {e}")
    except Exception as e:
        print(f"[WARN] Error en ITC: {e}")

    # Fallback
    return {
        "id": "ITC",
        "valor": 3.5,
        "unidad": "ratio",
        "fuente": "fallback histórico",
        "advertencia": "⚠️ Instalar scrapers/comisiones.py para datos reales",
    }


# ---------------------------------------------------------------------------
# Pipeline completo
# ---------------------------------------------------------------------------
def run_pipeline(steps=None):
    ensure_output_dir()
    data = load_existing()
    anio = datetime.now().year

    all_steps = {"nomina", "asistencia", "proyectos", "presupuesto", "votaciones",
                 "tpmp", "itc"}
    steps = set(steps) if steps else all_steps

    if "nomina" in steps:
        diputados = scrape_nomina()
        if diputados:
            data["diputados"] = diputados
    else:
        diputados = data.get("diputados", [])

    if "asistencia" in steps and diputados:
        diputados = scrape_asistencia(diputados)
        data["diputados"] = diputados

    if "proyectos" in steps and diputados:
        diputados = scrape_proyectos(diputados)
        data["diputados"] = diputados

    if "presupuesto" in steps:
        data["presupuesto"] = scrape_presupuesto()

    if "votaciones" in steps and diputados:
        diputados = scrape_votaciones(diputados)
        data["diputados"] = diputados

    # ── v1.1: TPMP y SIL ─────────────────────────────────────────────────────
    if "tpmp" in steps:
        tpmp_resultado = scrape_tpmp(anio)
        data["tpmp"] = tpmp_resultado

        # Enriquecer diputados con datos SIL
        if diputados:
            diputados = _enriquecer_diputados_con_sil(diputados, anio)
            data["diputados"] = diputados

    # ── v1.1: ITC ────────────────────────────────────────────────────────────
    if "itc" in steps:
        itc_resultado = scrape_itc(anio)
        data["itc"] = itc_resultado

    save(data)
    return data


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline de scraping legislativo")
    parser.add_argument(
        "--step",
        choices=["nomina", "asistencia", "proyectos", "presupuesto", "votaciones",
                 "tpmp", "itc"],
        help="Correr solo un step especifico"
    )
    args = parser.parse_args()
    steps = [args.step] if args.step else None
    t0 = time.time()
    run_pipeline(steps)
    print(f"[DONE] Pipeline completado en {time.time()-t0:.1f}s")
