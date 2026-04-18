"""
scrapers/comisiones.py
======================
Scraper de reuniones de comisiones permanentes — HCDN Argentina.

Datos obtenidos:
  - Reuniones por comisión en el período (fecha, hora, duración estimada)
  - Sesiones plenarias del año (para calcular denominador ITC)

Calcula:
  ITC = horas_comision / horas_pleno

Fuentes:
  - HCDN comisiones: https://www.hcdn.gob.ar/comisiones/permanentes/
  - HCDN sesiones:   https://www.hcdn.gob.ar/sesiones/sesiones/sesionesAnteriores.html
  - Fallback:        valores de referencia documentados (ITC histórico ~3.5×)

Genera:
  data/comisiones_reuniones.csv   — reuniones por comisión
  data/itc_resultado.json         — ITC calculado + metadatos

Uso:
    python -m scrapers.comisiones
    from scrapers.comisiones import calcular_itc
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
TIMEOUT = 20
PAUSA = 0.4  # segundos entre requests

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE, "data")
os.makedirs(DATA_DIR, exist_ok=True)

HCDN_BASE = "https://www.hcdn.gob.ar"

# Duración promedio estimada por reunión de comisión (horas)
# Fuente: metodología MEL-TP, consistente con datos históricos HCDN
DURACION_PROMEDIO_REUNION_HS = 2.5

# Duración promedio estimada por sesión plenaria (horas)
DURACION_PROMEDIO_SESION_HS = 4.0

# ITC de referencia cuando no se puede calcular (dato histórico documentado)
ITC_REFERENCIA = 3.5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_fecha(s: str) -> Optional[date]:
    if not s:
        return None
    s = s.strip()
    for fmt in ["%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # Buscar patrón dentro del texto
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", s)
    if m:
        d, mo, y = m.groups()
        y = int(y)
        if y < 100:
            y += 2000
        try:
            return date(y, int(mo), int(d))
        except ValueError:
            pass
    return None


def _extract_hour_from_text(text: str) -> Optional[float]:
    """Extrae la hora de inicio de un texto (ej: '10:30 hs' → 10.5)."""
    m = re.search(r"(\d{1,2}):(\d{2})\s*(?:hs|h\.)?", text)
    if m:
        return int(m.group(1)) + int(m.group(2)) / 60
    return None


# ---------------------------------------------------------------------------
# Obtener lista de comisiones permanentes
# ---------------------------------------------------------------------------
def _obtener_comisiones_permanentes() -> list[dict]:
    """
    Scrape la página de comisiones permanentes del HCDN.
    Retorna lista de {nombre, codigo, url}

    URL: https://www.hcdn.gob.ar/comisiones/permanentes/
    """
    url = f"{HCDN_BASE}/comisiones/permanentes/"
    print(f"  [ITC] Obteniendo lista de comisiones: {url}")

    comisiones = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Buscar links a comisiones (patrón: /comisiones/permanentes/cXX/)
        links = soup.find_all("a", href=re.compile(r"/comisiones/permanentes/[a-z]+", re.I))
        seen = set()

        for link in links:
            href = link.get("href", "")
            nombre = link.get_text(strip=True)
            if not nombre or len(nombre) < 3:
                continue

            # Normalizar URL
            if href.startswith("/"):
                href = HCDN_BASE + href
            elif not href.startswith("http"):
                href = f"{HCDN_BASE}/comisiones/permanentes/{href}"

            # Extraer código de la URL
            m = re.search(r"/permanentes/([a-z]+)/?", href.lower())
            codigo = m.group(1) if m else ""

            key = f"{codigo}:{nombre[:30]}"
            if key not in seen and codigo:
                seen.add(key)
                comisiones.append({
                    "nombre": nombre,
                    "codigo": codigo,
                    "url": href,
                })

        print(f"  [ITC] {len(comisiones)} comisiones encontradas")

    except Exception as e:
        print(f"  [ITC] Error al obtener comisiones: {e}")

    # Si no se encontró nada, usar lista de comisiones permanentes conocidas
    if len(comisiones) < 5:
        print("  [ITC] Usando lista de comisiones hardcodeada como fallback")
        comisiones = _comisiones_conocidas()

    return comisiones


def _comisiones_conocidas() -> list[dict]:
    """
    Lista de comisiones permanentes de la HCDN (actualizada a 2025).
    Fuente: Reglamento HCDN, Art. 61.
    """
    codigos = [
        ("Asuntos Constitucionales", "cac"),
        ("Legislación General", "clg"),
        ("Presupuesto y Hacienda", "cph"),
        ("Educación", "ced"),
        ("Trabajo y Previsión Social", "ctp"),
        ("Obras Públicas", "cop"),
        ("Economía", "cec"),
        ("Industria", "cind"),
        ("Comercio", "ccom"),
        ("Agricultura y Ganadería", "cag"),
        ("Energía y Combustibles", "ceyc"),
        ("Minería", "cmin"),
        ("Comunicaciones e Informática", "cci"),
        ("Transporte", "ctr"),
        ("Acción Social y Salud Pública", "cas"),
        ("Justicia", "cjus"),
        ("Interior", "cint"),
        ("Relaciones Exteriores y Culto", "crec"),
        ("Defensa Nacional", "cde"),
        ("Seguridad Interior", "csi"),
        ("Ciencia, Tecnología e Innovación Productiva", "cctip"),
        ("Cultura", "ccul"),
        ("Derechos Humanos y Garantías", "cdhyg"),
        ("Familia, Mujer, Niñez y Adolescencia", "cfmna"),
        ("Legislación Penal", "clp"),
        ("Recursos Naturales y Conservación", "crnca"),
        ("Turismo", "ctur"),
        ("Vivienda y Ordenamiento Urbano", "cvou"),
        ("Discapacidad", "cdisc"),
        ("Finanzas", "cfin"),
        ("Pequeñas y Medianas Empresas", "cpyme"),
    ]
    return [
        {
            "nombre": nombre,
            "codigo": codigo,
            "url": f"{HCDN_BASE}/comisiones/permanentes/{codigo}/",
        }
        for nombre, codigo in codigos
    ]


# ---------------------------------------------------------------------------
# Obtener reuniones de una comisión
# ---------------------------------------------------------------------------
def _obtener_reuniones_comision(
    codigo: str,
    nombre: str,
    anio: int,
    max_paginas: int = 3,
) -> list[dict]:
    """
    Obtiene las reuniones de una comisión para el año dado.

    URLs probadas:
      - /comisiones/permanentes/{codigo}/reuniones.html
      - /comisiones/permanentes/{codigo}/
    """
    reuniones = []

    urls_a_probar = [
        f"{HCDN_BASE}/comisiones/permanentes/{codigo}/reuniones.html",
        f"{HCDN_BASE}/comisiones/permanentes/{codigo}/",
    ]

    for url_base in urls_a_probar:
        try:
            for pagina in range(1, max_paginas + 1):
                url = url_base if pagina == 1 else f"{url_base}?pagina={pagina}"

                r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
                if r.status_code == 404:
                    break
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")

                # Buscar listado de reuniones (tabla o lista)
                items_encontrados = 0

                # Buscar en tablas
                for tabla in soup.find_all("table"):
                    for fila in tabla.find_all("tr")[1:]:
                        cols = fila.find_all("td")
                        if len(cols) < 2:
                            continue
                        texto_fila = " ".join(c.get_text(strip=True) for c in cols)

                        # Detectar fecha en la fila
                        fecha = None
                        for col in cols:
                            t = col.get_text(strip=True)
                            f = _parse_fecha(t)
                            if f and f.year == anio:
                                fecha = f
                                break

                        if fecha:
                            hora = _extract_hour_from_text(texto_fila)
                            reuniones.append({
                                "comision": nombre,
                                "codigo": codigo,
                                "fecha": str(fecha),
                                "hora_inicio": hora,
                                "duracion_hs": DURACION_PROMEDIO_REUNION_HS,
                                "texto": texto_fila[:150],
                            })
                            items_encontrados += 1

                # Buscar en listas (li) con fechas
                for li in soup.find_all("li"):
                    t = li.get_text(strip=True)
                    f = _parse_fecha(t[:15])  # la fecha suele estar al inicio
                    if f and f.year == anio:
                        hora = _extract_hour_from_text(t)
                        reuniones.append({
                            "comision": nombre,
                            "codigo": codigo,
                            "fecha": str(f),
                            "hora_inicio": hora,
                            "duracion_hs": DURACION_PROMEDIO_REUNION_HS,
                            "texto": t[:150],
                        })
                        items_encontrados += 1

                # Buscar en párrafos con fechas (diseño tipo news)
                for p in soup.find_all(["p", "div", "span"]):
                    t = p.get_text(strip=True)
                    if len(t) < 10 or len(t) > 300:
                        continue
                    # Buscar patrón: "Reunión del dd/mm/yyyy"
                    m = re.search(r"reuni[oó]n.*?(\d{2}/\d{2}/\d{4})", t, re.I)
                    if m:
                        f = _parse_fecha(m.group(1))
                        if f and f.year == anio:
                            reuniones.append({
                                "comision": nombre,
                                "codigo": codigo,
                                "fecha": str(f),
                                "hora_inicio": _extract_hour_from_text(t),
                                "duracion_hs": DURACION_PROMEDIO_REUNION_HS,
                                "texto": t[:150],
                            })
                            items_encontrados += 1

                if pagina > 1 and items_encontrados == 0:
                    break

                time.sleep(PAUSA)

            if reuniones:
                break  # si encontramos reuniones, no probar la siguiente URL

        except Exception as e:
            # No imprimir error por cada comisión para no spamear el log
            pass

    return reuniones


# ---------------------------------------------------------------------------
# Obtener sesiones plenarias
# ---------------------------------------------------------------------------
def _obtener_sesiones_plenarias(anio: int) -> int:
    """
    Obtiene el número de sesiones plenarias realizadas en el año dado.

    URL: https://www.hcdn.gob.ar/sesiones/sesiones/sesionesAnteriores.html

    Retorna:
        int: número de sesiones (fallback: 20 sesiones anuales típicas)
    """
    print(f"  [ITC] Obteniendo sesiones plenarias {anio}...")
    url = f"{HCDN_BASE}/sesiones/sesiones/sesionesAnteriores.html"

    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Contar menciones del año en la página
        texto = soup.get_text()
        sesiones_anio = 0

        # Buscar patrones de fecha del año
        patron = re.compile(rf"\d{{2}}/\d{{2}}/{anio}")
        matches = patron.findall(texto)
        sesiones_anio = len(set(matches))  # únicos

        # También buscar en tabla si existe
        tabla = soup.find("table")
        if tabla:
            sesiones_en_tabla = 0
            for fila in tabla.find_all("tr"):
                texto_fila = fila.get_text()
                if str(anio) in texto_fila:
                    sesiones_en_tabla += 1
            if sesiones_en_tabla > sesiones_anio:
                sesiones_anio = sesiones_en_tabla

        # Filtrar si está en un rango razonable
        if 5 <= sesiones_anio <= 60:
            print(f"  [ITC] {sesiones_anio} sesiones plenarias en {anio}")
            return sesiones_anio
        else:
            print(f"  [ITC] Conteo sospechoso ({sesiones_anio}), usando fallback")

    except Exception as e:
        print(f"  [ITC] Error al obtener sesiones: {e}")

    # Fallback: promedio histórico HCDN
    fallback_sesiones = 20 if anio >= 2020 else 25
    print(f"  [ITC] Usando fallback: {fallback_sesiones} sesiones para {anio}")
    return fallback_sesiones


# ---------------------------------------------------------------------------
# Función principal: calcular_itc
# ---------------------------------------------------------------------------
def calcular_itc(anio: int = None, max_comisiones: int = 20) -> dict:
    """
    Calcula el ITC (Índice de Trabajo en Comisiones).

    ITC = horas_comision / horas_pleno

    Donde:
      horas_comision = Σ reuniones × duración_promedio
      horas_pleno    = sesiones_plenarias × duración_promedio

    Parámetros:
        anio:             Año a calcular (default: año actual)
        max_comisiones:   Cuántas comisiones scrapear (limitar para no sobrecargar HCDN)

    Retorna:
        dict con: valor, horas_comision, horas_pleno, n_reuniones, n_sesiones, fuente
    """
    anio = anio or datetime.now().year
    print(f"\n{'='*55}")
    print(f"  ITC — Índice de Trabajo en Comisiones")
    print(f"  Año: {anio} | Comisiones a evaluar: {max_comisiones}")
    print(f"{'='*55}")

    todas_reuniones = []
    comisiones_con_datos = 0
    fuente = "ninguna"

    # ── Obtener lista de comisiones ───────────────────────────────────────────
    try:
        comisiones = _obtener_comisiones_permanentes()
        print(f"\n  [ITC] Procesando {min(max_comisiones, len(comisiones))} comisiones...")

        for com in comisiones[:max_comisiones]:
            reuniones = _obtener_reuniones_comision(
                com["codigo"], com["nombre"], anio
            )
            if reuniones:
                todas_reuniones.extend(reuniones)
                comisiones_con_datos += 1
                print(f"    ✓ {com['nombre'][:40]}: {len(reuniones)} reuniones")

        fuente = "HTML HCDN (comisiones permanentes)"

    except Exception as e:
        print(f"  [ITC] Error en scraping de comisiones: {e}")

    # ── Obtener sesiones plenarias ────────────────────────────────────────────
    n_sesiones = _obtener_sesiones_plenarias(anio)

    # ── Calcular horas ────────────────────────────────────────────────────────
    n_reuniones = len(todas_reuniones)
    horas_comision = n_reuniones * DURACION_PROMEDIO_REUNION_HS
    horas_pleno = n_sesiones * DURACION_PROMEDIO_SESION_HS

    # ── Calcular ITC ─────────────────────────────────────────────────────────
    if horas_pleno > 0 and n_reuniones >= 10:
        itc_valor = round(horas_comision / horas_pleno, 3)
        nota = (
            f"ITC calculado sobre {n_reuniones} reuniones en "
            f"{comisiones_con_datos} comisiones vs {n_sesiones} sesiones plenarias"
        )
    else:
        print(f"\n  [ITC] Datos insuficientes ({n_reuniones} reuniones). "
              f"Usando valor de referencia histórico.")
        itc_valor = ITC_REFERENCIA
        fuente = "estimación histórica MEL-TP"
        nota = (
            f"Valor de referencia (ITC histórico ~3.5×). "
            f"Solo se obtuvieron {n_reuniones} reuniones en {anio}."
        )

    # ── Guardar reuniones ─────────────────────────────────────────────────────
    df_reuniones = pd.DataFrame(todas_reuniones) if todas_reuniones else pd.DataFrame()
    if not df_reuniones.empty:
        ruta_csv = os.path.join(DATA_DIR, "comisiones_reuniones.csv")
        df_reuniones.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
        print(f"  💾 {ruta_csv} ({len(df_reuniones)} reuniones)")

        # Resumen por comisión
        resumen_com = (
            df_reuniones.groupby("comision")["duracion_hs"]
            .agg(["count", "sum"])
            .rename(columns={"count": "reuniones", "sum": "horas"})
            .sort_values("reuniones", ascending=False)
        )
        print(f"\n  📊 Top comisiones más activas:")
        print(resumen_com.head(8).to_string())

    # ── Construir resultado ───────────────────────────────────────────────────
    resultado = {
        "id": "ITC",
        "nombre": "Índice de Trabajo en Comisiones",
        "valor": itc_valor,
        "unidad": "ratio",
        "formula": "ITC = Σhoras_comision / Σhoras_pleno",
        "horas_comision": round(horas_comision, 1),
        "horas_pleno": round(horas_pleno, 1),
        "n_reuniones": n_reuniones,
        "n_sesiones": n_sesiones,
        "comisiones_con_datos": comisiones_con_datos,
        "duracion_promedio_reunion_hs": DURACION_PROMEDIO_REUNION_HS,
        "duracion_promedio_sesion_hs": DURACION_PROMEDIO_SESION_HS,
        "anio": anio,
        "fuente": fuente,
        "nota": nota,
        "timestamp": datetime.now().isoformat(),
        "interpretacion": (
            f"ITC={itc_valor:.2f}× → "
            + ("el trabajo técnico en comisiones supera al debate plenario." if itc_valor >= 1
               else "el debate plenario supera al trabajo en comisiones.")
        ),
    }

    if itc_valor == ITC_REFERENCIA:
        resultado["advertencia"] = "⚠️ Valor de referencia. Conectar actas HCDN para dato real."

    print(f"\n  📊 ITC = {itc_valor}× ({fuente})")
    print(f"     Reuniones: {n_reuniones} ({horas_comision:.0f}hs) | "
          f"Sesiones: {n_sesiones} ({horas_pleno:.0f}hs)")

    # ── Guardar JSON ──────────────────────────────────────────────────────────
    ruta_json = os.path.join(DATA_DIR, "itc_resultado.json")
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"  💾 {ruta_json}")

    return resultado


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    anio = datetime.now().year
    print("=" * 60)
    print(f"  SCRAPER COMISIONES — Monitor Legislativo v1.1")
    print(f"  Año: {anio}")
    print("=" * 60)

    resultado = calcular_itc(anio, max_comisiones=20)
    print(f"\n✅ ITC: {resultado['valor']}×")
    print(f"   Fuente: {resultado['fuente']}")