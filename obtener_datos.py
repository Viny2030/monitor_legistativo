"""
obtener_datos.py  –  Monitor Legislativo Argentina
====================================================
Extrae datos de fuentes oficiales del Congreso Argentino.

PROBLEMA DETECTADO – DDJJ:
  https://ddjj.diputados.gov.ar/ bloquea requests programáticos
  (devuelve HTTP 000 / sin respuesta al no detectar navegador real).
  Ver función `intentar_ddjj()` con la estrategia recomendada.

Fuentes que SÍ funcionan con requests:
  - API abierta Diputados (datos.hcdn.gob.ar)
  - Boletín Oficial (infoleg)
  - datos.gob.ar (datos abiertos Ejecutivo)
"""

import requests
import pandas as pd
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}

TIMEOUT = 20


# ─────────────────────────────────────────────────────────────────────────────
# 1. NÓMINA DE DIPUTADOS (API oficial HCDN)
# ─────────────────────────────────────────────────────────────────────────────

def obtener_nomina_diputados() -> pd.DataFrame:
    """
    Fuente primaria: CSV directo de datos.hcdn.gob.ar (portal datos abiertos HCDN)
    Fuente secundaria: scraping de hcdn.gob.ar/diputados/
    """
    # Intentar CSV directo del portal de datos abiertos
    urls_csv = [
        "https://datos.hcdn.gob.ar/dataset/diputados/resource/nomina-diputados/download",
        "https://datos.hcdn.gob.ar/dataset/diputados-actuales/resource/diputados/download/diputados.csv",
    ]
    print("🔍 Obteniendo nómina de diputados desde datos.hcdn.gob.ar ...")
    for url in urls_csv:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            from io import StringIO
            df = pd.read_csv(StringIO(resp.text))
            salida = DATA_DIR / "nomina_diputados.csv"
            df.to_csv(salida, index=False, encoding="utf-8-sig")
            print(f"✅ {len(df)} diputados guardados en {salida}")
            return df
        except Exception:
            continue

    print("⚠️  CSV directo no disponible. Intentando scraping ...")
    return _scraping_alternativo_diputados()


def _scraping_alternativo_diputados() -> pd.DataFrame:
    """Scraping de la página de nómina de hcdn.gob.ar."""
    from bs4 import BeautifulSoup

    urls = [
        "https://www.hcdn.gob.ar/diputados/",
        "https://www.hcdn.gob.ar/diputados/listado.html",
    ]
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            tabla = soup.find("table")
            datos = []
            if tabla:
                # Detectar encabezados reales para mapear columnas correctamente
                encabezados = [th.get_text(strip=True).lower()
                               for th in tabla.find_all("tr")[0].find_all(["th", "td"])]
                for fila in tabla.find_all("tr")[1:]:
                    cols = [td.get_text(strip=True) for td in fila.find_all("td")]
                    if len(cols) < 2:
                        continue
                    # La tabla de HCDN tiene: col0=foto/vacía, col1=nombre, col2=distrito, col3=bloque
                    # Detectamos cuál columna tiene el nombre buscando texto con coma (apellido, nombre)
                    nombre = ""
                    distrito = ""
                    bloque = ""
                    for i, val in enumerate(cols):
                        if "," in val and len(val) > 5:
                            nombre = val
                            distrito = cols[i+1] if i+1 < len(cols) else ""
                            bloque   = cols[i+2] if i+2 < len(cols) else ""
                            break
                    if nombre:
                        datos.append({"Nombre": nombre, "Distrito": distrito, "Bloque": bloque})

            if datos:
                df = pd.DataFrame(datos)
                salida = DATA_DIR / "nomina_diputados.csv"
                df.to_csv(salida, index=False, encoding="utf-8-sig")
                print(f"✅ Scraping: {len(df)} diputados en {salida}")
                return df
        except Exception as e:
            print(f"   ↳ {url} falló: {e}")
            continue

    print("❌ No se pudo obtener la nómina de ninguna fuente.")
    print("   → Descargá manualmente desde https://www.hcdn.gob.ar/diputados/")
    print("     y guardalo en data/nomina_diputados.csv")
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 2. DDJJ – DECLARACIONES JURADAS DE DIPUTADOS
#    PROBLEMA: el portal bloquea bots. Estrategia documentada abajo.
# ─────────────────────────────────────────────────────────────────────────────

def intentar_ddjj() -> dict:
    """
    Intenta acceder a https://ddjj.diputados.gov.ar/

    DIAGNÓSTICO:
      El portal de DDJJ bloquea requests programáticos (Cloudflare / JS challenge).
      Además, en algunas redes corporativas o de ISP el DNS no resuelve el dominio.

    Error "NameResolutionError / getaddrinfo failed":
      El dominio no resuelve en tu red. Verificá:
        1. Que tenés internet (ping google.com)
        2. Probá cambiar el DNS a 8.8.8.8 (Google) o 1.1.1.1 (Cloudflare)
        3. Abrí https://ddjj.diputados.gov.ar/ en el navegador para confirmar acceso

    ESTRATEGIAS:
      A) Playwright con navegador real → ddjj_con_playwright()
      B) Descarga manual del CSV → cargar_ddjj_manual()
      C) datos.gob.ar si el dataset está disponible
    """
    url = "https://ddjj.diputados.gov.ar/"
    print("🔍 Verificando acceso a DDJJ ...")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            print("✅ Portal DDJJ accesible")
            return {"status": "ok", "codigo_http": 200}
        else:
            print(f"⚠️  Portal DDJJ respondió HTTP {resp.status_code} (bloqueado por anti-bot)")
            return {"status": "bloqueado", "codigo_http": resp.status_code}
    except Exception as e:
        msg = str(e)
        if "getaddrinfo" in msg or "NameResolution" in msg:
            print("❌ DNS no resuelve 'ddjj.diputados.gov.ar'")
            print("   → Verificá tu conexión o cambiá el DNS a 8.8.8.8")
            print("   → Confirmá acceso manual en el navegador")
        else:
            print(f"❌ DDJJ inaccesible: {e}")
        print("   → SOLUCIÓN: usar ddjj_con_playwright() o descarga manual")
        return {"status": "sin_respuesta", "error": msg}


def ddjj_con_playwright():
    """
    Descarga DDJJ usando Playwright (navegador headless real).

    INSTALACIÓN:
        pip install playwright
        playwright install chromium

    USO:
        from obtener_datos import ddjj_con_playwright
        df = ddjj_con_playwright()
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Playwright no instalado. Ejecuta:")
        print("   pip install playwright && playwright install chromium")
        return pd.DataFrame()

    print("🌐 Abriendo navegador real para DDJJ ...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://ddjj.diputados.gov.ar/", wait_until="networkidle")
        # Buscar link de descarga CSV/Excel
        page.wait_for_timeout(3000)
        content = page.content()
        browser.close()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, "html.parser")
    # Intentar encontrar tabla
    tabla = soup.find("table")
    if tabla:
        df = pd.read_html(str(tabla))[0]
        salida = DATA_DIR / "ddjj_diputados.csv"
        df.to_csv(salida, index=False, encoding="utf-8-sig")
        print(f"✅ DDJJ guardado: {len(df)} registros en {salida}")
        return df
    else:
        print("⚠️  No se encontró tabla en el portal DDJJ")
        return pd.DataFrame()


def cargar_ddjj_manual(ruta_csv: str = None) -> pd.DataFrame:
    """
    Carga DDJJ desde archivo descargado manualmente.
    Si no se indica ruta, busca en data/ddjj_diputados.csv
    """
    ruta = Path(ruta_csv) if ruta_csv else DATA_DIR / "ddjj_diputados.csv"
    if ruta.exists():
        df = pd.read_csv(ruta, encoding="utf-8-sig")
        print(f"✅ DDJJ cargado desde {ruta}: {len(df)} registros")
        return df
    else:
        print(f"⚠️  No se encontró {ruta}")
        print("   Descarga el CSV manualmente desde https://ddjj.diputados.gov.ar/")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 3. PRESUPUESTO (datos.gob.ar – Ejecución Presupuestaria)
# ─────────────────────────────────────────────────────────────────────────────

def obtener_presupuesto_congreso(anio: int = None) -> pd.DataFrame:
    """
    Fuente: datos.gob.ar – Presupuesto APN (ZIP con CSV)
    Filtra Jurisdicción 01 (Poder Legislativo Nacional).
    """
    import zipfile, io
    anio = anio or date.today().year
    # El presupuesto 2025/2026 usa la prórroga 2023; usamos 2024 como referencia real
    anio_datos = min(anio, 2024)
    url_zip = (
        f"https://www.datos.gob.ar/dataset/sspre-presupuesto-administracion-publica-nacional-{anio_datos}"
        f"/resource/distribucion-anual-acumulada-creditos-{anio_datos}/download/"
        f"creditos{anio_datos}.zip"
    )
    # URL alternativa directa conocida para 2024
    urls = [
        url_zip,
        f"https://www.datos.gob.ar/dataset/sspre-presupuesto-administracion-publica-nacional-{anio_datos}/resource/download/creditos{anio_datos}.zip",
        # Fallback: ejecución resumida
        f"https://presupuestociudadano.economia.gob.ar/api/datos/ejecucion?jurisdiccion=01&anio={anio_datos}&formato=csv",
    ]
    print(f"🔍 Obteniendo presupuesto Jurisdicción 01 – {anio_datos} (referencia) ...")
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            # Si es ZIP, descomprimir
            content_type = resp.headers.get("content-type", "")
            if "zip" in content_type or url.endswith(".zip"):
                z = zipfile.ZipFile(io.BytesIO(resp.content))
                csv_name = next((n for n in z.namelist() if n.endswith(".csv")), None)
                if not csv_name:
                    continue
                df = pd.read_csv(z.open(csv_name), encoding="latin-1", on_bad_lines="skip")
            else:
                from io import StringIO
                df = pd.read_csv(StringIO(resp.text), encoding="utf-8", on_bad_lines="skip")

            # Filtrar jurisdicción 01
            for col in df.columns:
                col_lower = col.lower()
                if "jurisdic" in col_lower:
                    df = df[df[col].astype(str).str.startswith("1") |
                            df[col].astype(str).str.startswith("01")]
                    break

            salida = DATA_DIR / f"presupuesto_{anio_datos}.csv"
            df.to_csv(salida, index=False, encoding="utf-8-sig")
            print(f"✅ Presupuesto {anio_datos}: {len(df)} registros en {salida}")
            return df
        except Exception as e:
            print(f"   ↳ falló ({e})")
            continue

    print(f"⚠️  No se pudo descargar el presupuesto automáticamente.")
    print("   → Descargalo manualmente desde:")
    print("     https://www.datos.gob.ar/dataset/sspre-presupuesto-administracion-publica-nacional-2024")
    print(f"     Buscá 'Distribución resumida' → descomprimí el ZIP → guardá el CSV en data/presupuesto_{anio_datos}.csv")
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# Runner principal
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("   MONITOR LEGISLATIVO – Extracción de Datos")
    print("=" * 60)

    print("\n[1/3] Nómina de Diputados")
    obtener_nomina_diputados()

    print("\n[2/3] DDJJ – Declaraciones Juradas")
    resultado_ddjj = intentar_ddjj()
    if resultado_ddjj["status"] != "ok":
        print(f"   Status: {resultado_ddjj['status']}")
        print("   ⚠️  Ver instrucciones arriba para resolverlo.")

    print("\n[3/3] Presupuesto Jurisdicción 01")
    obtener_presupuesto_congreso()

    print("\n✅ Proceso de extracción finalizado.")
    print(f"   Archivos disponibles en: {DATA_DIR}")