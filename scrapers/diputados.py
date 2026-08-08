"""
scrapers/diputados.py
Extrae la nómina completa de diputados desde diputados.gov.ar

DIAGNÓSTICO DEL PROBLEMA ANTERIOR:
- La tabla tiene 8 columnas: Foto | Diputado | Distrito | Bloque | Mandato |
  Inicia mandato | Finaliza mandato | Fecha nacimiento
- El scraper viejo buscaba cols[1], cols[2], cols[3] → correcto en índices
  pero la col[0] es la FOTO (imagen), no texto → si no había imagen el
  desplazamiento rompía todo.
- El problema REAL: la web usa JavaScript para filtrar/paginar. El HTML
  estático SÍ contiene todos los diputados, pero el parser fallaba porque
  buscaba soup.find('table') genérico en lugar de la tabla específica.
- SOLUCIÓN: usar el CSV oficial que la misma web ofrece como descarga directa.
"""

import requests
import pandas as pd
import io
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ── Constantes ────────────────────────────────────────────────────────────────
URL_NOMINA     = "https://www.diputados.gov.ar/diputados/index.html"
URL_CSV_HCDN   = "https://www.diputados.gov.ar/diputados/index.csv"   # 404 actualmente — se usa fallback HTML
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
    "Referer": "https://www.diputados.gov.ar/",
}


def obtener_nomina_csv() -> pd.DataFrame:
    """
    MÉTODO 1 (PREFERIDO): Descarga el CSV oficial que la web expone.
    Más robusto que el scraping HTML porque no depende de la estructura visual.
    """
    print("📥 [Método 1] Intentando descarga del CSV oficial...")
    try:
        r = requests.get(URL_CSV_HCDN, headers=HEADERS, timeout=20)
        r.raise_for_status()
        # El CSV de HCDN viene en latin-1 / iso-8859-1
        df = pd.read_csv(
            io.StringIO(r.content.decode("latin-1")),
            sep=",",
            skipinitialspace=True
        )
        df.columns = [c.strip() for c in df.columns]
        print(f"  ✅ CSV descargado: {len(df)} filas, columnas: {list(df.columns)}")
        return df
    except Exception as e:
        print(f"  ⚠️  CSV oficial falló: {e}")
        return pd.DataFrame()


def obtener_nomina_scraping() -> pd.DataFrame:
    """
    MÉTODO 2 (FALLBACK): Parsea el HTML directamente.
    Usa la estructura REAL de la tabla (8 columnas confirmadas):
      0: Foto | 1: Diputado | 2: Distrito | 3: Bloque |
      4: Mandato | 5: Inicia | 6: Finaliza | 7: Fecha nacimiento
    """
    print("🔍 [Método 2] Scraping HTML de la nómina...")
    try:
        r = requests.get(URL_NOMINA, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.content.decode("utf-8", errors="replace"), "html.parser")

        # La tabla tiene thead con los headers conocidos
        tabla = None
        for t in soup.find_all("table"):
            headers_tabla = [th.get_text(strip=True) for th in t.find_all("th")]
            if "Distrito" in headers_tabla or "Bloque" in headers_tabla:
                tabla = t
                break

        if not tabla:
            # Último recurso: primera tabla de la página
            tabla = soup.find("table")

        if not tabla:
            print("  ❌ No se encontró ninguna tabla. La estructura del sitio cambió.")
            return pd.DataFrame()

        datos = []
        filas = tabla.find_all("tr")[1:]  # Saltar encabezado
        print(f"  📋 Filas encontradas: {len(filas)}")

        for fila in filas:
            cols = fila.find_all("td")
            if len(cols) < 4:
                continue

            # Col 0: foto (imagen) — antes se ignoraba por completo (ver
            # diagnostico arriba). La extraemos ahora en vez de descartarla.
            img = cols[0].find("img") if len(cols) > 0 else None
            url_foto = ""
            if img:
                src = (img.get("src") or img.get("data-src") or "").strip()
                if src and not any(p in src.lower() for p in ("sin-foto", "sinfoto", "blank.gif", "default")):
                    url_foto = urljoin(URL_NOMINA, src)

            # Col 1: puede ser link o texto
            col_nombre = cols[1]
            nombre = col_nombre.get_text(strip=True)
            # Extraer URL del perfil si existe
            link = col_nombre.find("a")
            url_perfil = link["href"] if link and link.get("href") else ""

            datos.append({
                "Nombre":           nombre,
                "Distrito":         cols[2].get_text(strip=True) if len(cols) > 2 else "",
                "Bloque":           cols[3].get_text(strip=True) if len(cols) > 3 else "",
                "Mandato":          cols[4].get_text(strip=True) if len(cols) > 4 else "",
                "Inicia_mandato":   cols[5].get_text(strip=True) if len(cols) > 5 else "",
                "Finaliza_mandato": cols[6].get_text(strip=True) if len(cols) > 6 else "",
                "Fecha_nacimiento": cols[7].get_text(strip=True) if len(cols) > 7 else "",
                "URL_perfil":       url_perfil,
                "URL_foto":         url_foto,
            })

        df = pd.DataFrame(datos)
        print(f"  ✅ Scraping HTML: {len(df)} diputados extraídos.")
        return df

    except Exception as e:
        print(f"  ❌ Error en scraping HTML: {e}")
        return pd.DataFrame()


def obtener_nomina(guardar_csv: bool = True, ruta_salida: str = "data/nomina_diputados.csv") -> pd.DataFrame:
    """
    Punto de entrada principal. Intenta Método 1 (CSV oficial),
    si falla usa Método 2 (HTML scraping).
    """
    print("\n" + "="*55)
    print("  EXTRACTOR DE NÓMINA DE DIPUTADOS")
    print("="*55)

    # Intentar CSV oficial primero
    df = obtener_nomina_csv()

    # Si el CSV no funcionó o vino vacío, usar scraping
    if df.empty:
        print("\n🔄 Cambiando a método de scraping HTML...")
        df = obtener_nomina_scraping()

    if df.empty:
        print("\n❌ FALLO TOTAL: no se pudo obtener la nómina por ningún método.")
        print("   Verificar: ¿el sitio está caído? ¿cambió la estructura?")
        return df

    # Limpieza básica
    df = df.dropna(how="all")
    df = df[df.apply(lambda r: r.astype(str).str.strip().ne("").any(), axis=1)]

    print(f"\n📊 RESULTADO FINAL: {len(df)} diputados")
    if "Bloque" in df.columns:
        print("\n📌 Distribución por Bloque:")
        print(df["Bloque"].value_counts().to_string())

    if guardar_csv:
        import os
        os.makedirs("data", exist_ok=True)
        df.to_csv(ruta_salida, index=False, encoding="utf-8-sig")
        print(f"\n💾 Guardado en: {ruta_salida}  ({len(df)} filas)")

    return df


if __name__ == "__main__":
    df = obtener_nomina()