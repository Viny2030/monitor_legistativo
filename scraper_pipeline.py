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
import unicodedata
from datetime import datetime
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup

# Los dominios .gob.ar vienen fallando con SSLCertVerificationError ("unable
# to get local issuer certificate") tanto en Windows como en runners de CI
# (mismo workaround aplicado en obtener_datos.py / scripts/cruzar_presupuesto.py).
# No es un problema de nuestro codigo, es la cadena de certificados del
# servidor publico: desactivamos la verificacion estricta para no perder el
# dato por esto (aceptable aca: solo se lee HTML/CSV/JSON publico, no se
# manda nada sensible).
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "diputados.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MonitorLegislativo/1.0)"}
TIMEOUT = 60  # el SIL es lento

# Nombres femeninos frecuentes en Argentina para deteccion de genero
# (fallback heuristico; el campo genero del scraper tiene prioridad)
# NOTA (2026-06): lista ampliada tras detectar 59+ diputadas mal clasificadas
# como "M" (ver auditoria de datos). Se agrega tambien una regla de sufijo
# "-a" como red de contencion, con excepciones masculinas conocidas, en vez
# de defaultear todo nombre desconocido a "M".
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
    "adelaida", "griselda", "alejandrina", "rebeca", "eugenia", "marta",
    # --- ampliacion 2026-06 ---
    "hilda", "barbara", "fernanda", "eliana", "celia", "julieta", "mariela",
    "daiana", "alida", "frida", "maira", "virginia", "antonela", "luisa",
    "maura", "moira", "lilia", "johanna", "marianela", "varinia", "luciana",
    "valentina", "gisela", "blanca", "isabel", "carmen", "raquel", "dolores",
    "ximena", "yolanda", "viviana", "miriam", "perla", "noemi", "edith",
    "delia", "felisa", "haydee", "zulema", "iris", "lidia", "leonor",
    "magdalena", "antonia", "matilde", "angela", "constanza", "guadalupe",
    "rocio", "milagros", "candela", "abril", "luna", "luz", "dalma",
    "macarena", "araceli", "yael", "tamara", "vanina", "estefania", "daniela",
    "camila", "carla", "diana", "elena", "emilia", "eva", "flavia",
    "gimena", "ivana", "judith", "karen", "marisa", "marina", "miryam",
    "olivia", "ornela", "renata", "sofia", "sol", "wanda", "yanina",
    # --- ampliacion 2026-06 (segunda pasada, nombres con variantes/raros) ---
    "myriam", "giselle", "caren", "kelly", "yamile", "lourdes", "nancy",
    "rosario", "belen", "rocio", "veronica",
}

# Nombres masculinos que terminan en "-a" (excepciones a la regla de sufijo)
_NOMBRES_M_EXCEPCION_A = {
    "luca", "matias", "tobias", "elias", "isaias", "jonas", "nicolas",
    "andres", "tomas", "lucas", "ezequiel",  # por si el split deja sufijos raros
}


def _detect_gender(nombre):
    """Heuristica de genero por primer nombre. Devuelve 'F', 'M' o 'ND'.

    Orden de prioridad:
      1. Lista curada de nombres femeninos -> F
      2. Lista de excepciones masculinas terminadas en "-a" -> M
      3. Termina en "-a" (regla general en espanol) -> F
      4. Default -> M
    """
    parts = nombre.lower().split()
    if not parts:
        return "ND"
    # apellido primero: "GARCIA, Maria" → tomar despues de la coma
    if "," in nombre:
        after_comma = nombre.split(",", 1)[1].strip().lower().split()
        primer = after_comma[0] if after_comma else parts[0]
    else:
        primer = parts[0]
    primer = re.sub(r"[^a-záéíóúñ]", "", primer)
    primer_sin_tilde = (
        unicodedata.normalize("NFKD", primer)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    if primer_sin_tilde in _NOMBRES_F:
        return "F"
    if primer_sin_tilde in _NOMBRES_M_EXCEPCION_A:
        return "M"
    if primer_sin_tilde.endswith("a"):
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
def _extraer_foto_url(col_foto, base_url):
    """
    Extrae la URL de la foto desde la primera columna de la tabla de nomina.
    La imagen puede venir en src (carga normal) o en data-src/data-original
    (lazy-loading, comun en el sitio de diputados.gov.ar). Devuelve None si
    no hay imagen o si es un placeholder generico (sin-foto.jpg, blank.gif).
    """
    if col_foto is None:
        return None
    img = col_foto.find("img")
    if not img:
        return None
    src = (
        img.get("src")
        or img.get("data-src")
        or img.get("data-original")
        or ""
    ).strip()
    if not src:
        return None
    # Descartar placeholders conocidos de "sin foto"
    src_lower = src.lower()
    if any(p in src_lower for p in ("sin-foto", "sinfoto", "no-photo", "blank.gif", "default")):
        return None
    return urljoin(base_url, src)


def scrape_nomina():
    """
    Fuente: https://www.diputados.gov.ar/diputados/
    Campos obtenidos: nombre, distrito, bloque, mandato_hasta, genero, foto_url
    """
    print("[STEP 1] Scraping nomina de diputados...")
    url = "https://www.diputados.gov.ar/diputados/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        tabla = soup.find("table")
        if not tabla:
            print("[WARN] No se encontro tabla en diputados.gov.ar")
            return []

        diputados = []
        con_foto = 0
        filas = tabla.find_all("tr")[1:]
        for fila in filas:
            cols = fila.find_all("td")
            if len(cols) < 4:
                continue
            # Col 0 = foto (imagen), col 1 = nombre — ver diagnostico en
            # scrapers/diputados.py. Ya filtramos arriba len(cols) >= 4, asi
            # que cols[0] siempre existe en este punto.
            foto_url = _extraer_foto_url(cols[0], url)
            nombre = cols[1].get_text(strip=True)
            distrito = cols[2].get_text(strip=True)
            bloque = cols[3].get_text(strip=True)
            # Columna de mandato puede variar; intentar col 4 si existe
            mandato_hasta = cols[4].get_text(strip=True) if len(cols) > 4 else ""
            if foto_url:
                con_foto += 1
            diputados.append({
                "nombre": nombre,
                "distrito": distrito,
                "bloque": bloque,
                "mandato_hasta": mandato_hasta,
                "genero": _detect_gender(nombre),  # mejorar con datos oficiales
                "foto_url": foto_url,
                "asistencia_pct": None,
                "proyectos_presentados": None,
                "proyectos_aprobados": None,
                "iqp": None
            })
        print(f"[OK] {len(diputados)} diputados encontrados ({con_foto} con foto)")
        return diputados
    except Exception as e:
        print(f"[ERROR] scrape_nomina: {e}")
        return []


# ---------------------------------------------------------------------------
# STEP 2 — Asistencia por diputado
# ---------------------------------------------------------------------------
ASISTENCIA_INDICE_URL = "https://www2.hcdn.gob.ar/secparl/dclp/asistencia.html"
# Respaldo si no se puede leer el índice: período 2026 y período 2025.
ASISTENCIA_PDF_RESPALDO = [
    "https://www3.hcdn.gob.ar/dependencias/dclp/asistencia/periodo144/ESTADISTICAS.pdf",
    "https://www3.hcdn.gob.ar/dependencias/dclp/asistencia/periodo%20143/ESTADISTICAS.pdf",
]
# Metadatos de la última corrida de asistencia (los copia run_pipeline a data["meta"])
ASISTENCIA_META = {}


def _norm_txt(txt: str) -> str:
    """Mayúsculas, sin tildes y con espacios simples (para comparar nombres)."""
    txt = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", txt).upper().strip()


def _urls_pdf_asistencia() -> list:
    """URLs del PDF ESTADISTICAS, del período más reciente al más viejo.
    Se leen del índice de la Dirección de Labor Parlamentaria; si no responde,
    se usan las de respaldo."""
    urls = []
    try:
        res = requests.get(ASISTENCIA_INDICE_URL, headers=HEADERS, timeout=TIMEOUT, verify=False)
        res.raise_for_status()
        candidatos = []
        for href in re.findall(r'href="([^"]+)"', res.text):
            if not href.upper().endswith("/ESTADISTICAS.PDF"):
                continue
            m = re.search(r"periodo(?:%20|\s)?(\d+)", href, re.I)
            if m:
                candidatos.append((int(m.group(1)), urljoin(ASISTENCIA_INDICE_URL, href)))
        candidatos.sort(reverse=True)
        urls = [u for _, u in candidatos]
    except Exception as e:
        print(f"[WARN] No se pudo leer el índice de asistencia ({e}) — uso URLs de respaldo")
    return urls + [u for u in ASISTENCIA_PDF_RESPALDO if u not in urls]


def _parsear_estadisticas_asistencia(texto: str) -> list:
    """Filas del PDF ESTADISTICAS de la HCDN.

    El PDF NO trae porcentajes: cada fila es
        BLOQUE  Apellido, Nombre  P  A  L  M.O.
    (Presente, Ausente, Licencia, Misión Oficial). Antes se tomaba la última
    columna (M.O., casi siempre 0) como si fuera el % de asistencia, y por
    eso todos los diputados quedaban con asistencia 0 %.
    Devuelve [{"texto": "BLOQUE Apellido, Nombre", "p":.., "a":.., "l":.., "mo":..}]
    """
    filas = []
    for linea in (texto or "").split("\n"):
        m = re.match(r"^(?P<txt>.*\S)\s+(?P<p>\d+)\s+(?P<a>\d+)\s+(?P<l>\d+)\s+(?P<mo>\d+)\s*$", linea.strip())
        if m and "," in m.group("txt"):
            filas.append({"texto": m.group("txt"), "p": int(m.group("p")), "a": int(m.group("a")),
                          "l": int(m.group("l")), "mo": int(m.group("mo"))})
    return filas


def _buscar_fila_diputado(nombre: str, filas: list):
    """Busca la fila de un diputado ("Apellido, Nombre") por apellido + primer
    nombre. Si el apellido es único en el PDF alcanza con el apellido."""
    if "," not in nombre:
        return None
    apellido, nombres = [x.strip() for x in nombre.split(",", 1)]
    ap = _norm_txt(apellido)
    primer = _norm_txt(nombres).split(" ")[0] if nombres.strip() else ""
    patron = re.compile(r"(?:^|\s)" + re.escape(ap) + r"\s*,\s*(?P<resto>.*)$")
    candidatos = []
    for f in filas:
        m = patron.search(_norm_txt(f["texto"]))
        if m:
            candidatos.append((f, m.group("resto")))
    if not candidatos:
        return None
    if len(candidatos) == 1:
        return candidatos[0][0]
    for f, resto in candidatos:
        if primer and resto.startswith(primer):
            return f
    return None  # apellido repetido y no se pudo desambiguar: mejor sin dato que dato ajeno


def scrape_asistencia(diputados, previos=None):
    """
    Fuente: PDF "ESTADISTICAS" de la Dirección de Coordinación de Labor
    Parlamentaria (HCDN), del período legislativo más reciente publicado.

    asistencia_pct = presentes / (presentes + ausentes + licencias + misiones) × 100,
    el mismo criterio que usa la HCDN en su reporte PORCENTAJE.pdf.

    2026-10-09: reescrito. Antes (1) tomaba la columna M.O. como porcentaje
    (todos daban 0 %) y (2) estaba fijo en el período 143 (2025), anterior a
    la renovación de diciembre. Si no se puede descargar ningún PDF, se
    conservan los valores de la corrida anterior (`previos`) en vez de
    dejar a todos sin dato.
    """
    global ASISTENCIA_META
    print("[STEP 2] Asistencia (PDF ESTADISTICAS de la HCDN, período más reciente)...")
    try:
        import pdfplumber
    except ImportError:
        print("[WARN] pdfplumber no instalado. Instalar con: pip install pdfplumber")
        return diputados

    import io
    filas, fuente, encabezado = [], None, ""
    for url in _urls_pdf_asistencia():
        try:
            res = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
            if res.status_code != 200 or not res.content.startswith(b"%PDF"):
                continue
            with pdfplumber.open(io.BytesIO(res.content)) as pdf:
                textos = [p.extract_text() or "" for p in pdf.pages]
            filas = _parsear_estadisticas_asistencia("\n".join(textos))
            if len(filas) >= 100:  # un PDF válido trae ~257 filas
                fuente = url
                encabezado = " ".join(textos[0].split("\n")[1:3]) if textos else ""
                break
            print(f"[WARN] {url}: sólo {len(filas)} filas legibles, pruebo el siguiente")
        except Exception as e:
            print(f"[WARN] {url}: {e}")

    if not fuente:
        print("[ERROR] No se pudo obtener ningún PDF de asistencia.")
        conservados = 0
        for d in diputados:
            prev = (previos or {}).get(d.get("nombre"))
            if prev and prev.get("asistencia_pct") is not None and prev.get("asistencia_detalle"):
                d["asistencia_pct"] = prev["asistencia_pct"]
                d["asistencia_detalle"] = prev["asistencia_detalle"]
                d["nape"] = prev.get("nape")
                conservados += 1
        ASISTENCIA_META = {"fuente_asistencia": "sin actualizar hoy (se conservan los valores anteriores)",
                           "fuente_asistencia_actualizados": f"{conservados}/{len(diputados)}"}
        return diputados

    matched = 0
    for d in diputados:
        f = _buscar_fila_diputado(d.get("nombre", ""), filas)
        if not f:
            continue
        total = f["p"] + f["a"] + f["l"] + f["mo"]
        if total == 0:
            continue
        d["asistencia_pct"] = round(f["p"] / total * 100, 1)
        d["asistencia_detalle"] = {"presentes": f["p"], "ausentes": f["a"], "licencias": f["l"],
                                   "mision_oficial": f["mo"], "sesiones": total}
        d["nape"] = round(1 - d["asistencia_pct"] / 100, 4)
        matched += 1

    ASISTENCIA_META = {
        "fuente_asistencia": fuente,
        "periodo_asistencia": encabezado,
        "fuente_asistencia_actualizados": f"{matched}/{len(diputados)}",
    }
    print(f"[OK] Asistencia: {len(filas)} filas en el PDF, {matched}/{len(diputados)} diputados matcheados ({fuente})")
    return diputados


# ---------------------------------------------------------------------------
# STEP 3 — Proyectos (SIL / hcdn.gob.ar/proyectos)
# ---------------------------------------------------------------------------
PROYECTOS_META = {}


def _clave_autor(nombre: str):
    """("APELLIDO", "PRIMERNOMBRE") normalizados desde "Apellido, Nombre"."""
    if "," not in (nombre or ""):
        return _norm_txt(nombre), ""
    ap, nom = nombre.split(",", 1)
    nom = _norm_txt(nom)
    return _norm_txt(ap), (nom.split(" ")[0] if nom else "")


def scrape_proyectos(diputados, previos=None):
    """
    Fuente: API CKAN de datos.hcdn.gob.ar (resource 22b2d52c...), proyectos
    con expediente del año actual y del anterior.

    2026-10-09: corregido.
      · TIPO es el TIPO de proyecto (LEY / RESOLUCION / DECLARACION), no su
        estado. Antes se contaba como "aprobado" todo proyecto de ley
        presentado. Ahora ese conteo va a `proyectos_ley` (y se mantiene en
        `proyectos_aprobados` sólo por compatibilidad de la API; el dashboard
        lo rotula "Proyectos de ley").
      · Cada página se reintenta 3 veces. Si la API igual falla, se conservan
        los valores de la corrida anterior (`previos`) — antes se caía al SIL,
        que cuenta distinto, y los totales oscilaban 4.000 ↔ 8.400 por día.
      · Match por apellido + primer nombre (antes sólo apellido: dos "Ávila"
        recibían los mismos números).
      · Paginación con orden fijo (sort=_id) y sin duplicados: sin `sort` la
        API devuelve las páginas en orden variable y al paginar se salteaban o
        repetían registros (ej.: Zago, Oscar quedaba con 0 teniendo 2 en 2025).
    """
    global PROYECTOS_META
    print("[STEP 3] Consultando API CKAN de proyectos parlamentarios...")
    anio = str(datetime.now().year)
    anio_prev = str(int(anio) - 1)

    RESOURCE_ID = "22b2d52c-7a0e-426b-ac0a-a3326c388ba6"
    API_URL = "https://datos.hcdn.gob.ar/api/3/action/datastore_search"

    conteo = {}   # (APELLIDO, PRIMERNOMBRE) -> {"presentados", "ley"}
    offset, limit, total_procesados = 0, 1000, 0
    vistos = set()  # _id ya contados

    try:
        while True:
            data = None
            for intento in range(3):
                try:
                    res = requests.get(API_URL,
                                       params={"resource_id": RESOURCE_ID, "limit": limit, "offset": offset,
                                               "sort": "_id asc"},
                                       headers=HEADERS, timeout=60, verify=False)
                    res.raise_for_status()
                    data = res.json()
                    break
                except Exception as e:
                    print(f"[WARN] CKAN offset {offset}, intento {intento + 1}/3: {e}")
                    time.sleep(10 * (intento + 1))
            if data is None:
                raise RuntimeError(f"la API de proyectos no respondió (offset {offset})")

            records = data.get("result", {}).get("records", [])
            if not records:
                break
            for row in records:
                if row.get("_id") in vistos:
                    continue
                vistos.add(row.get("_id"))
                expediente = str(row.get("EXP_DIPUTADOS") or "")
                if anio not in expediente and anio_prev not in expediente:
                    continue
                ap, nom = _clave_autor(row.get("AUTOR") or "")
                if len(ap) < 3:
                    continue
                total_procesados += 1
                c = conteo.setdefault((ap, nom), {"presentados": 0, "ley": 0})
                c["presentados"] += 1
                if (row.get("TIPO") or "").strip().upper() == "LEY":
                    c["ley"] += 1

            offset += limit
            if offset >= data.get("result", {}).get("total", 0):
                break
    except Exception as e:
        print(f"[ERROR] scrape_proyectos: {e}")
        conservados = 0
        for d in diputados:
            prev = (previos or {}).get(d.get("nombre"))
            if prev and prev.get("proyectos_fuente") == "CKAN":
                for k in ("proyectos_presentados", "proyectos_aprobados", "proyectos_ley", "proyectos_fuente"):
                    d[k] = prev.get(k)
                conservados += 1
        PROYECTOS_META = {"fuente_proyectos": "sin actualizar hoy (se conservan los valores anteriores)",
                          "proyectos_actualizados": f"{conservados}/{len(diputados)}"}
        return diputados

    por_apellido = {}
    for (ap, nom), c in conteo.items():
        por_apellido.setdefault(ap, []).append((nom, c))

    matched = 0
    for d in diputados:
        ap, nom = _clave_autor(d.get("nombre", ""))
        opciones = por_apellido.get(ap, [])
        c = next((c for n, c in opciones if n == nom), None)
        if c is None and len(opciones) == 1 and sum(1 for x in diputados if _clave_autor(x.get("nombre", ""))[0] == ap) == 1:
            c = opciones[0][1]   # apellido único en la Cámara: el nombre puede venir abreviado
        if c is None:
            c = {"presentados": 0, "ley": 0}   # la API respondió y no tiene proyectos suyos
        else:
            matched += 1
        d["proyectos_presentados"] = c["presentados"]
        d["proyectos_ley"] = c["ley"]
        d["proyectos_aprobados"] = c["ley"]   # compat: mismo valor que proyectos_ley (ver docstring)
        d["proyectos_fuente"] = "CKAN"

    PROYECTOS_META = {"fuente_proyectos": "datos.hcdn.gob.ar (CKAN)",
                      "proyectos_periodo": f"expedientes {anio_prev}-{anio}",
                      "proyectos_actualizados": f"{matched}/{len(diputados)}"}
    print(f"[INFO] {total_procesados} proyectos ({anio_prev}-{anio}), {len(conteo)} autores")
    print(f"[OK] Proyectos matcheados para {matched}/{len(diputados)} diputados")
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
            res = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
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
                res = requests.get(f"{api_base}{ep}", headers=HEADERS, timeout=20, verify=False)
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
                    res2 = requests.get(f"{api_base}{ep_votos}", headers=HEADERS, timeout=20, verify=False)
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
                # 2026-10-09: sólo si CKAN no dio dato (None); antes `not` también
                # pisaba los 0 reales y mezclaba fuentes que cuentan distinto.
                if d.get("proyectos_presentados") is None:
                    d["proyectos_presentados"] = d["sil_presentados"]
                    d["proyectos_fuente"] = "SIL"
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
    # Valores de la corrida anterior, por nombre: si una fuente falla hoy se
    # conservan en vez de dejar a todos sin dato (ver scrape_asistencia/proyectos).
    previos = {d.get("nombre"): d for d in data.get("diputados", [])}
    data.setdefault("meta", {})

    if "nomina" in steps:
        diputados = scrape_nomina()
        if diputados:
            data["diputados"] = diputados
    else:
        diputados = data.get("diputados", [])

    if "asistencia" in steps and diputados:
        diputados = scrape_asistencia(diputados, previos)
        data["diputados"] = diputados
        data["meta"].update(ASISTENCIA_META)

    if "proyectos" in steps and diputados:
        diputados = scrape_proyectos(diputados, previos)
        data["diputados"] = diputados
        data["meta"].update(PROYECTOS_META)

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