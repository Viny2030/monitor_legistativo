"""
personal.py
Obtiene el valor del módulo salarial del Congreso automáticamente.

Cascada de fuentes:
  1. datos.hcdn.gob.ar  → CSV oficial de remuneraciones (dieta legislador)
  2. data/escala_salarial.csv → escala local → calcula desde sueldo piso
  3. Boletín Oficial   → scraping última resolución de módulo
  4. Fallback fijo     → último valor conocido ($2,730)

El valor resuelto queda en VALOR_MODULO para que pipeline.py lo importe.
"""

import re
import os
import io
import logging

log = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

# Escalafón 14 (sueldo piso): básico 96.6 + adicional 41.4 = 138 módulos
_MODULOS_ESCALAFON_PISO = 138.0

# Fallback: último valor conocido (Marzo 2026)
_VALOR_FALLBACK = 2_730

# URL CSV oficial HCDN — dieta y gastos de representación
_URL_HCDN = (
    "https://datos.hcdn.gob.ar/dataset/"
    "07518f0f-43f0-41f5-a462-53ed8a1bebb6/resource/"
    "0c91eb20-f694-4064-a65b-b8bfe3673c7e/download/remuneraciones1.8.csv"
)

# URL Boletín Oficial — búsqueda de resoluciones de módulo
_URL_BOLETIN = (
    "https://www.boletinoficial.gob.ar/busquedaAvanzada/index"
    "?busqueda=modulo+congreso+nacional&categoria=1"
)


# ── Fuente 1: datos.hcdn.gob.ar ───────────────────────────────────────────────

def _desde_hcdn() -> float | None:
    """
    Descarga el CSV oficial de remuneraciones y calcula el módulo
    a partir de la dieta del legislador.

    La dieta equivale a ~845 módulos (escalafón 1: 591.5 + 253.5).
    """
    try:
        import requests
        import pandas as pd

        r = requests.get(_URL_HCDN, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()

        for enc in ("utf-8", "latin-1"):
            try:
                df = pd.read_csv(io.StringIO(r.content.decode(enc)))
                break
            except Exception:
                continue
        else:
            return None

        col_dieta = next(
            (c for c in df.columns if "dieta" in c.lower()),
            None
        )
        if col_dieta is None:
            return None

        dieta = pd.to_numeric(df[col_dieta], errors="coerce").dropna()
        if dieta.empty:
            return None

        valor_dieta = dieta.iloc[0]
        # Escalafón 1 (máximo) = 845 módulos
        modulo = round(valor_dieta / 845)
        log.info(f"[HCDN] dieta={valor_dieta:,.0f} → módulo={modulo:,}")
        return float(modulo)

    except Exception as e:
        log.warning(f"[HCDN] falló: {e}")
        return None


# ── Fuente 2: escala salarial local ───────────────────────────────────────────

def _desde_escala_local() -> float | None:
    """
    Lee data/escala_salarial.csv y calcula el módulo desde el escalafón piso
    (categoría 14, 138 módulos).
    """
    try:
        import pandas as pd

        ruta = os.path.join("data", "escala_salarial.csv")
        if not os.path.exists(ruta):
            return None

        df = pd.read_csv(ruta)

        col_cat = next(
            (c for c in df.columns if "categ" in c.lower() or "escal" in c.lower()),
            None
        )
        col_sueldo = next(
            (c for c in df.columns if "sueldo" in c.lower() or "total" in c.lower()
             or "monto" in c.lower()),
            None
        )
        if col_cat is None or col_sueldo is None:
            return None

        df[col_sueldo] = pd.to_numeric(df[col_sueldo], errors="coerce")
        df = df.dropna(subset=[col_sueldo])

        fila_piso = df.loc[df[col_sueldo].idxmin()]
        sueldo_piso = fila_piso[col_sueldo]

        modulo = round(sueldo_piso / _MODULOS_ESCALAFON_PISO)
        log.info(f"[Escala local] sueldo_piso={sueldo_piso:,.0f} → módulo={modulo:,}")
        return float(modulo)

    except Exception as e:
        log.warning(f"[Escala local] falló: {e}")
        return None


# ── Fuente 3: Boletín Oficial ─────────────────────────────────────────────────

def _desde_boletin_oficial() -> float | None:
    """
    Busca en el Boletín Oficial la última resolución que fije el valor
    del módulo del Congreso y extrae el número.
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        r = requests.get(_URL_BOLETIN, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        texto = soup.get_text(" ", strip=True)

        patrones = [
            r"m[oó]dulo[^$\d]{0,30}\$\s*([\d.,]+)",
            r"valor\s+del\s+m[oó]dulo[^$\d]{0,20}([\d.,]+)",
            r"\$\s*([\d.,]+)\s*(?:por\s+)?m[oó]dulo",
        ]

        for patron in patrones:
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                raw = match.group(1).replace(".", "").replace(",", "")
                valor = float(raw)
                if 1_000 < valor < 500_000:
                    log.info(f"[Boletín Oficial] módulo={valor:,}")
                    return valor

        return None

    except Exception as e:
        log.warning(f"[Boletín Oficial] falló: {e}")
        return None


# ── Resolver con cascada ──────────────────────────────────────────────────────

def obtener_valor_modulo() -> float:
    """
    Intenta cada fuente en orden y devuelve el primer valor válido.
    Si todas fallan, devuelve el fallback fijo.
    """
    fuentes = [
        ("datos.hcdn.gob.ar", _desde_hcdn),
        ("escala local",       _desde_escala_local),
        ("Boletín Oficial",    _desde_boletin_oficial),
    ]

    for nombre, fn in fuentes:
        valor = fn()
        if valor and valor > 0:
            print(f"  💰 Módulo obtenido desde {nombre}: ${valor:,.0f}")
            return valor

    print(f"  ⚠️  Todas las fuentes fallaron — usando fallback: ${_VALOR_FALLBACK:,}")
    return float(_VALOR_FALLBACK)


# ── Valor exportado ───────────────────────────────────────────────────────────

VALOR_MODULO = obtener_valor_modulo()