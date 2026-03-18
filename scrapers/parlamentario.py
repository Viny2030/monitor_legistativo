"""
scrapers/parlamentario.py
Extrae noticias relevantes de Parlamentario.com usando su API de WordPress.

Útil para:
  - Monitorear actualizaciones del valor del módulo (paritarias)
  - Seguir novedades sobre dietas de legisladores
  - Detectar cambios normativos que afecten el centro de costos
  - Noticias sobre asistencia, votaciones y actividad legislativa

API WordPress estándar: https://www.parlamentario.com/wp-json/wp/v2/posts
"""

import requests
import pandas as pd
import os
import re
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

BASE_API = "https://www.parlamentario.com/wp-json/wp/v2/posts"
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Búsquedas relevantes para el proyecto MEL-TP
BUSQUEDAS_CLAVE = {
    "modulo_paritaria":   "modulo paritaria",
    "dietas_diputados":   "dieta diputados",
    "dietas_senadores":   "dieta senadores módulo",
    "asistencia":         "asistencia diputados sesión",
    "transparencia":      "transparencia presupuesto cámara",
}

# Palabras clave para detectar menciones de valor del módulo en el texto
REGEX_MODULO = re.compile(
    r'\$\s*([\d\.]+(?:,\d+)?)\s*(?:el\s+)?(?:valor\s+(?:del?\s+)?)?módulo',
    re.IGNORECASE
)


def buscar_articulos(
    query: str,
    cantidad: int = 10,
    desde_fecha: str = None,
) -> list:
    """
    Busca artículos en Parlamentario.com via WordPress API.

    Parámetros:
        query:       Términos de búsqueda
        cantidad:    Máximo de resultados (max 100)
        desde_fecha: Filtrar desde esta fecha (formato: '2025-01-01')

    Retorna:
        Lista de dicts con titulo, fecha, link, resumen
    """
    params = {
        "search":   query,
        "per_page": min(cantidad, 100),
        "orderby":  "date",
        "order":    "desc",
    }
    if desde_fecha:
        params["after"] = f"{desde_fecha}T00:00:00"

    try:
        r = requests.get(BASE_API, headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        posts = r.json()

        resultados = []
        for p in posts:
            # Limpiar HTML del resumen
            resumen_html = p.get("excerpt", {}).get("rendered", "")
            resumen = re.sub(r'<[^>]+>', '', resumen_html).strip()

            resultados.append({
                "Titulo":    p.get("title", {}).get("rendered", ""),
                "Fecha":     p.get("date", "")[:10],  # Solo YYYY-MM-DD
                "URL":       p.get("link", ""),
                "Resumen":   resumen[:300],
                "Query":     query,
            })

        return resultados

    except Exception as e:
        print(f"  ❌ Error buscando '{query}': {e}")
        return []


def extraer_valor_modulo(url: str) -> dict:
    """
    Dado el link de un artículo, intenta extraer el valor del módulo mencionado.
    Retorna dict con valor encontrado y contexto.
    """
    try:
        # Obtener el contenido del artículo via API
        # Primero necesitamos el ID del post
        slug = url.rstrip('/').split('/')[-1]
        r = requests.get(
            BASE_API,
            headers=HEADERS,
            params={"slug": slug},
            timeout=15
        )
        r.raise_for_status()
        posts = r.json()

        if not posts:
            return {}

        contenido_html = posts[0].get("content", {}).get("rendered", "")
        texto = re.sub(r'<[^>]+>', ' ', contenido_html)

        # Buscar menciones del valor del módulo
        matches = REGEX_MODULO.findall(texto)

        if matches:
            # Tomar el primer valor encontrado
            valor_str = matches[0].replace('.', '').replace(',', '.')
            try:
                valor = float(valor_str)
                return {
                    "valor_modulo": valor,
                    "menciones":    len(matches),
                    "todos_valores": matches,
                }
            except ValueError:
                pass

        return {}

    except Exception as e:
        return {}


def monitorear_modulo(cantidad: int = 5) -> dict:
    """
    Busca los artículos más recientes sobre el valor del módulo
    e intenta extraer el valor numérico más actualizado.

    Retorna dict con:
        valor_modulo: float (el más reciente encontrado)
        fecha:        str
        fuente:       str (URL del artículo)
    """
    print("\n🔍 Buscando valor del módulo en Parlamentario.com...")

    articulos = buscar_articulos("modulo paritaria", cantidad=cantidad)

    for art in articulos:
        print(f"  📰 {art['Fecha']} — {art['Titulo'][:70]}")
        resultado = extraer_valor_modulo(art["URL"])

        if resultado and resultado.get("valor_modulo"):
            valor = resultado["valor_modulo"]
            if 1000 < valor < 100000:  # rango razonable para el módulo
                print(f"  ✅ Valor del módulo encontrado: ${valor:,.2f}")
                return {
                    "valor_modulo": valor,
                    "fecha":        art["Fecha"],
                    "fuente":       art["URL"],
                    "titulo":       art["Titulo"],
                }

    print("  ⚠️  No se encontró valor del módulo en el texto de los artículos")
    return {}


def descargar_noticias_relevantes(
    guardar: bool = True,
    desde_fecha: str = None,
) -> pd.DataFrame:
    """
    Descarga noticias relevantes para el proyecto MEL-TP
    usando todas las búsquedas clave definidas.

    Retorna DataFrame con todas las noticias encontradas.
    """
    print("\n" + "="*55)
    print("  DESCARGA DE NOTICIAS — PARLAMENTARIO.COM")
    print("="*55)

    if desde_fecha is None:
        # Por defecto, últimos 90 días
        from datetime import timedelta
        desde_fecha = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    print(f"  📅 Desde: {desde_fecha}")

    todos = []
    for nombre, query in BUSQUEDAS_CLAVE.items():
        print(f"\n  🔎 Buscando: '{query}'...")
        arts = buscar_articulos(query, cantidad=5, desde_fecha=desde_fecha)
        print(f"     → {len(arts)} artículos encontrados")
        todos.extend(arts)

    if not todos:
        print("  ❌ Sin resultados")
        return pd.DataFrame()

    df = pd.DataFrame(todos)
    df = df.drop_duplicates(subset=["URL"])
    df = df.sort_values("Fecha", ascending=False).reset_index(drop=True)

    print(f"\n  📊 Total único: {len(df)} artículos")

    if guardar:
        ruta = os.path.join(DATA_DIR, "noticias_parlamentario.csv")
        df.to_csv(ruta, index=False, encoding="utf-8-sig")
        print(f"  💾 Guardado: {ruta}")

    return df


if __name__ == "__main__":
    # Monitorear valor del módulo
    modulo = monitorear_modulo(cantidad=5)
    if modulo:
        print(f"\n  📌 VALOR DEL MÓDULO ACTUALIZADO:")
        print(f"     ${modulo['valor_modulo']:,.2f} ({modulo['fecha']})")
        print(f"     Fuente: {modulo['fuente']}")

    print()
    # Descargar noticias relevantes
    df = descargar_noticias_relevantes()
    if not df.empty:
        print(f"\n  📰 Últimas noticias:")
        print(df[["Fecha", "Titulo", "Query"]].head(10).to_string(index=False))