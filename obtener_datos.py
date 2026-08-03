"""
obtener_datos.py – Monitor Legislativo Argentina
=================================================
Script legacy de nómina/DDJJ/presupuesto. Corre en el workflow diario como
paso "best-effort" (continue-on-error): scraper_pipeline.py es el pipeline
principal que alimenta data/diputados.json; este script solo complementa
nomina_diputados.csv para el código legacy que todavía lo lee.

Reescrito para que las funciones coincidan con tests/test_obtener_datos.py
(antes el módulo solo tenía extraer_diputados(), y los tests esperaban
obtener_nomina_diputados, _scraping_alternativo_diputados, intentar_ddjj,
cargar_ddjj_manual, obtener_presupuesto_congreso — importaban funciones que
no existían, así que la suite fallaba entera con ImportError).

Nota de honestidad: las URLs de DDJJ y del "intento CSV rápido" de nómina no
están confirmadas contra el sitio real (no tengo forma de verificarlas en
esta sesión) — están marcadas explícitamente abajo. Si no responden o no
devuelven lo esperado, cada función degrada con gracia (fallback a scraping
HTML o a DataFrame/dict vacío) en vez de romper el pipeline.
"""

import io
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup

# Mismo workaround que scripts/cruzar_presupuesto.py: los .gob.ar vienen
# fallando con SSLCertVerificationError ("unable to get local issuer
# certificate") tanto en Windows como en runners de GitHub Actions (visto en
# el log de monitor_diario.yml del 2026-08-03, corriendo Ubuntu). No es un
# problema de nuestro código, es la cadena de certificados del servidor
# público — desactivamos la verificación estricta para no perder el dato por
# esto, a costa de no validar el cert (aceptable acá: no se manda nada
# sensible, solo se lee HTML/CSV público).
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
SSL_VERIFY = False

DATA_DIR = Path(__file__).parent / "data"

URL_NOMINA_HTML = "https://www.diputados.gov.ar/diputados/"
# Intento rápido de CSV directo — no confirmado contra el sitio real. Si no
# existe o no responde con CSV válido, obtener_nomina_diputados() cae solo
# al scraping HTML de _scraping_alternativo_diputados().
URL_NOMINA_CSV = "https://www.diputados.gov.ar/diputados/nomina.csv"

# DDJJ (declaraciones juradas patrimoniales) — URL de referencia, requiere
# confirmar contra la fuente oficial vigente (Oficina Anticorrupción / HCDN)
# antes de depender de ella en producción.
URL_DDJJ = "https://www.argentina.gob.ar/anticorrupcion/declaraciones-juradas"

# Mismo endpoint de ejecución presupuestaria que usa scripts/cruzar_presupuesto.py
URL_PRESUPUESTO_CSV = (
    "https://infra.datos.gob.ar/catalog/sspm/dataset/193/distribution/"
    "193.1/download/ejecucion-presupuestaria-anual.csv"
)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; monitor-legislativo/1.0)"}
TIMEOUT = 30


# ---------------------------------------------------------------------------
# Nómina de diputados
# ---------------------------------------------------------------------------
def obtener_nomina_diputados() -> pd.DataFrame:
    """
    Devuelve la nómina de diputados como DataFrame (columnas Nombre,
    Distrito, Bloque) y la guarda en DATA_DIR/nomina_diputados.csv.

    Intenta primero un GET directo esperando CSV; si falla la request o el
    contenido no es un CSV parseable, cae a _scraping_alternativo_diputados()
    (parseo de la tabla HTML de diputados.gov.ar).
    """
    df = None
    try:
        res = requests.get(URL_NOMINA_CSV, headers=HEADERS, timeout=TIMEOUT, verify=SSL_VERIFY)
        res.raise_for_status()
        df = pd.read_csv(io.StringIO(res.text))
        if df.empty or "Nombre" not in df.columns:
            df = None
    except Exception:
        df = None

    if df is None:
        df = _scraping_alternativo_diputados()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not df.empty:
        df.to_csv(DATA_DIR / "nomina_diputados.csv", index=False, encoding="utf-8")
        print(f"✅ {len(df)} diputados guardados en '{DATA_DIR / 'nomina_diputados.csv'}'")
    else:
        print("⚠️  No se pudo obtener nómina de diputados (ni CSV ni scraping HTML).")

    return df


def _scraping_alternativo_diputados() -> pd.DataFrame:
    """
    Fallback: parsea la tabla HTML de diputados.gov.ar directamente.
    Devuelve DataFrame vacío (nunca None) si no hay tabla, la tabla está
    vacía, o falla la request — para que el llamador pueda seguir sin
    romperse.
    """
    print(f"--- 🔍 Scraping HTML nómina diputados | {date.today()} ---")
    try:
        res = requests.get(URL_NOMINA_HTML, headers=HEADERS, timeout=TIMEOUT, verify=SSL_VERIFY)
        res.raise_for_status()
    except Exception as e:
        print(f"❌ Error de red en scraping alternativo: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(res.text, "html.parser")
    tabla = soup.find("table")
    if not tabla:
        print("❌ No se encontró tabla en la página. La estructura del sitio puede haber cambiado.")
        return pd.DataFrame()

    datos = []
    for fila in tabla.find_all("tr")[1:]:
        cols = fila.find_all("td")
        if len(cols) > 3:
            datos.append({
                "Nombre": cols[1].get_text(strip=True),
                "Distrito": cols[2].get_text(strip=True),
                "Bloque": cols[3].get_text(strip=True),
            })

    if not datos:
        print("❌ La tabla estaba vacía.")
        return pd.DataFrame()

    return pd.DataFrame(datos)


# ---------------------------------------------------------------------------
# DDJJ (declaraciones juradas patrimoniales)
# ---------------------------------------------------------------------------
def intentar_ddjj() -> dict:
    """
    Intenta alcanzar la fuente de DDJJ. Nunca lanza excepción: siempre
    devuelve un dict con al menos {"status": ...}. status es "ok" si HTTP
    200, "sin_respuesta" ante cualquier error de red (incluye un mensaje de
    ayuda sobre DNS si el error parece ser de resolución de nombre).
    """
    try:
        res = requests.get(URL_DDJJ, headers=HEADERS, timeout=TIMEOUT, verify=SSL_VERIFY)
        return {
            "status": "ok" if res.status_code == 200 else "error_http",
            "codigo_http": res.status_code,
            "url": URL_DDJJ,
        }
    except Exception as e:
        mensaje = str(e)
        if "getaddrinfo" in mensaje.lower() or "name or service not known" in mensaje.lower():
            print("⚠️  No se pudo resolver el DNS del host de DDJJ. Verificá tu conexión "
                  "o probá forzando un DNS público (8.8.8.8) si el problema persiste.")
        else:
            print(f"⚠️  No se pudo alcanzar la fuente de DDJJ: {mensaje}")
        return {"status": "sin_respuesta", "error": mensaje, "url": URL_DDJJ}


def cargar_ddjj_manual(ruta: str = None) -> pd.DataFrame:
    """
    Carga un CSV de DDJJ cargado a mano (fallback cuando intentar_ddjj() no
    puede scrapear la fuente oficial). Si no se pasa ruta, busca
    DATA_DIR/ddjj_diputados.csv; si no existe, devuelve DataFrame vacío.
    """
    path = Path(ruta) if ruta else (DATA_DIR / "ddjj_diputados.csv")
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception as e:
        print(f"⚠️  No se pudo leer {path}: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Presupuesto del Congreso
# ---------------------------------------------------------------------------
def obtener_presupuesto_congreso(anio: int = None) -> pd.DataFrame:
    """
    Descarga la ejecución presupuestaria (mismo dataset que
    scripts/cruzar_presupuesto.py) y filtra Jurisdicción 01 (Poder
    Legislativo). Si falla, imprime instrucciones para cargar el dato a mano
    desde datos.gob.ar y devuelve un DataFrame vacío en vez de romper el
    pipeline.
    """
    anio = anio or date.today().year
    try:
        res = requests.get(URL_PRESUPUESTO_CSV, headers=HEADERS, timeout=TIMEOUT, verify=SSL_VERIFY)
        res.raise_for_status()
        df = pd.read_csv(io.StringIO(res.content.decode("latin-1", errors="replace")),
                          low_memory=False)
        col_jur = next((c for c in df.columns if "jurisdic" in c.lower()), None)
        if col_jur:
            df = df[df[col_jur].astype(str).str.startswith("1")]
        return df
    except Exception as e:
        print(f"⚠️  No se pudo obtener el presupuesto automáticamente ({e}).")
        print("    Cargalo manualmente: descargá el CSV de ejecución presupuestaria desde "
              "datos.gob.ar y guardalo en data/presupuesto_congreso.csv.")
        return pd.DataFrame()


if __name__ == "__main__":
    exit_code = 0
    nomina = obtener_nomina_diputados()
    if nomina.empty:
        exit_code = 1

    ddjj_status = intentar_ddjj()
    if ddjj_status["status"] != "ok":
        print("ℹ️  DDJJ no disponible en vivo — usando cargar_ddjj_manual() como fallback.")
        cargar_ddjj_manual()

    obtener_presupuesto_congreso()

    sys.exit(exit_code)
