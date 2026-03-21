"""
data_loader.py – Monitor Legislativo Argentina
===============================================
Lee los CSVs reales descargados por obtener_datos.py
y construye el dict que espera calcular_todos() en indicadores/calculos.py.

Indicadores con fuente automática:
  CPR → presupuesto CSV + población hardcodeada (Censo 2022)
  TPS → presupuesto CSV (columnas personal)
  CAF → presupuesto CSV (devengado vs crédito original)
  CUN → presupuesto CSV + leyes del Boletín Oficial

Indicadores sin fuente automática (requieren scraping o carga manual):
  TMM, ITT, IQP → HCDN SIL / actas de comisión  (ver obtener_datos.py Etapa 4)
  CLS, TEF       → clasificación manual / AGN
  CAD, EVD, TCI  → auditoría propia / Google Analytics
  → Se usan valores de FALLBACK configurables en MANUAL_OVERRIDES
"""

from __future__ import annotations
import pandas as pd
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# ─────────────────────────────────────────────────────────────────────────────
# VALORES MANUALES / FALLBACK
# Completá estos con los datos reales cuando los tengas.
# Cada clave coincide con el nombre del parámetro que espera calcular_todos().
# ─────────────────────────────────────────────────────────────────────────────
MANUAL_OVERRIDES: dict = {
    # Dimensión I (se sobreescriben automáticamente si el CSV está disponible)
    "presupuesto_total":      185_000_000_000,   # $185 mil millones ARS (referencia Ley Presupuesto)
    "presupuesto_devengado":  178_000_000_000,   # Actualizar con Presupuesto Abierto
    "presupuesto_solicitado": 185_000_000_000,   # Actualizar con Presupuesto Abierto
    "poblacion_total": 46_654_581,          # INDEC Censo 2022
    "planta_permanente": 3_800,             # Actualizar con RRHH HCDN
    "planta_temporaria": 1_200,             # Actualizar con RRHH HCDN

    # Dimensión II – requieren scraping HCDN SIL (Etapa 4)
    "proyectos": [
        # Formato: {"fecha_ingreso": "YYYY-MM-DD", "fecha_dictamen": "YYYY-MM-DD"}
        {"fecha_ingreso": "2024-03-01", "fecha_dictamen": "2024-05-15"},
        {"fecha_ingreso": "2024-04-10", "fecha_dictamen": "2024-06-20"},
        {"fecha_ingreso": "2024-01-05", "fecha_dictamen": "2024-03-10"},
    ],
    "horas_comision": 1_240,               # Actas de comisión HCDN
    "horas_pleno": 320,                    # Diario de Sesiones
    "votaciones": [
        {"presentes": 210},
        {"presentes": 198},
        {"presentes": 225},
    ],
    "total_escanos_diputados": 257,

    # Dimensión III – clasificación manual / AGN
    "leyes_sancionadas": 84,               # Boletín Oficial
    "leyes_sustantivas": 31,               # Clasificación manual
    "leyes_total": 84,
    "informes_resueltos": 18,              # AGN / Mesa de entradas
    "informes_recibidos": 42,

    # Dimensión IV – auditoría propia / Google Analytics
    "datasets": [
        {"formato": "JSON",  "tiempo": "inmediato"},
        {"formato": "Excel", "tiempo": "semana"},
        {"formato": "PDF",   "tiempo": "mes"},
        {"formato": "API",   "tiempo": "inmediato"},
        {"formato": "PDF",   "tiempo": "semana"},
    ],
    "datos_verificables": 200,
    "datos_erroneos": 14,
    "usuarios_activos": 3_200,
    "sesiones_totales": 48_000,
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de lectura de CSV
# ─────────────────────────────────────────────────────────────────────────────

def _leer_csv(nombre: str) -> pd.DataFrame | None:
    """Lee un CSV de la carpeta data/. Devuelve None si no existe."""
    ruta = DATA_DIR / nombre
    if not ruta.exists():
        return None
    try:
        df = pd.read_csv(ruta, encoding="utf-8-sig", on_bad_lines="skip")
        return df
    except Exception as e:
        print(f"⚠️  No se pudo leer {ruta}: {e}")
        return None


def _buscar_col(df: pd.DataFrame, fragmentos: list[str]) -> str | None:
    """Devuelve el nombre de la primera columna que contenga alguno de los fragmentos."""
    for frag in fragmentos:
        for col in df.columns:
            if frag.lower() in col.lower():
                return col
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Lectores por fuente
# ─────────────────────────────────────────────────────────────────────────────

def _datos_presupuesto(anio: int = 2024) -> dict:
    """
    Extrae del CSV de presupuesto:
      - presupuesto_total       (crédito vigente o devengado Jurisdicción 01)
      - presupuesto_devengado
      - presupuesto_solicitado  (crédito original)
    """
    resultado = {}
    nombre_csv = f"presupuesto_{anio}.csv"
    df = _leer_csv(nombre_csv)

    if df is None:
        print(f"⚠️  {nombre_csv} no encontrado en data/. Usando valores de MANUAL_OVERRIDES.")
        return resultado

    # Columnas posibles según el esquema de datos.gob.ar
    col_devengado  = _buscar_col(df, ["devengado", "ejecutado"])
    col_credito    = _buscar_col(df, ["credito_orig", "credito original", "credito vigente"])
    col_vigente    = _buscar_col(df, ["credito_vige", "vigente"])

    try:
        if col_devengado:
            resultado["presupuesto_devengado"] = pd.to_numeric(
                df[col_devengado], errors="coerce"
            ).sum()
        if col_credito:
            resultado["presupuesto_solicitado"] = pd.to_numeric(
                df[col_credito], errors="coerce"
            ).sum()
        elif col_vigente:
            resultado["presupuesto_solicitado"] = pd.to_numeric(
                df[col_vigente], errors="coerce"
            ).sum()

        # presupuesto_total = devengado si existe, sino crédito vigente
        resultado["presupuesto_total"] = resultado.get(
            "presupuesto_devengado",
            resultado.get("presupuesto_solicitado", 0)
        )

        if resultado.get("presupuesto_total", 0) > 0:
            print(f"✅ Presupuesto leído: ${resultado['presupuesto_total']:,.0f} ARS")
        else:
            print("⚠️  Presupuesto en cero – revisar columnas del CSV.")
            resultado = {}
    except Exception as e:
        print(f"⚠️  Error procesando presupuesto: {e}")
        resultado = {}

    return resultado


def _datos_nomina() -> dict:
    """
    Lee nomina_diputados.csv y verifica columnas esperadas:
    Nombre, Distrito, Bloque
    """
    df = _leer_csv("nomina_diputados.csv")
    if df is None:
        print("⚠️  nomina_diputados.csv no encontrado. Ejecutá obtener_datos.py primero.")
        return {}

    cols_esperadas = ["Nombre", "Distrito", "Bloque"]
    cols_faltantes = [c for c in cols_esperadas if c not in df.columns]

    if cols_faltantes:
        # Intentar renombrar columnas comunes
        mapeo = {}
        for col in df.columns:
            cl = col.lower()
            if "nombre" in cl or "diputado" in cl:
                mapeo[col] = "Nombre"
            elif "distrito" in cl or "provincia" in cl:
                mapeo[col] = "Distrito"
            elif "bloque" in cl or "partido" in cl or "bancada" in cl:
                mapeo[col] = "Bloque"
        df = df.rename(columns=mapeo)
        cols_faltantes = [c for c in cols_esperadas if c not in df.columns]

    if cols_faltantes:
        print(f"⚠️  nomina_diputados.csv le faltan columnas: {cols_faltantes}")
        print(f"   Columnas encontradas: {list(df.columns)}")
    else:
        print(f"✅ Nómina leída: {len(df)} diputados | columnas: {list(df.columns)}")

    return {"_nomina_df": df, "total_escanos_diputados": len(df) or 257}


# ─────────────────────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────────────────────

def _datos_hcdn(anio: int) -> dict:
    """
    Intenta importar y correr scraper_hcdn para obtener datos de TMM/ITT/IQP.
    Si falla, devuelve dict vacío (se usarán MANUAL_OVERRIDES).
    """
    try:
        from scraper_hcdn import obtener_datos_hcdn
        return obtener_datos_hcdn(anio)
    except ImportError:
        print("ℹ️  scraper_hcdn.py no encontrado. Usando MANUAL_OVERRIDES para TMM/ITT/IQP.")
        return {}
    except Exception as e:
        print(f"ℹ️  scraper_hcdn falló: {e}. Usando MANUAL_OVERRIDES para TMM/ITT/IQP.")
        return {}


def construir_datos(anio: int = 2024, usar_scraper_hcdn: bool = False) -> dict:
    """
    Construye y devuelve el dict completo listo para calcular_todos().

    Prioridad:
      1. Datos del CSV real
      2. MANUAL_OVERRIDES (fallback)
    """
    print("\n📊 Construyendo datos para los 12 indicadores...")
    print(f"   Año de referencia: {anio}")
    print(f"   Directorio data/: {DATA_DIR}\n")

    # Base: valores manuales/fallback
    datos = dict(MANUAL_OVERRIDES)

    # Sobreescribir con datos reales del presupuesto
    datos_ppto = _datos_presupuesto(anio)
    datos.update(datos_ppto)

    # Sobreescribir con datos reales de la nómina
    datos_nomina = _datos_nomina()
    datos.update({k: v for k, v in datos_nomina.items() if not k.startswith("_")})

    # Sobreescribir con datos del scraper HCDN (TMM/ITT/IQP) si se pide
    if usar_scraper_hcdn:
        datos_hcdn = _datos_hcdn(anio)
        datos.update(datos_hcdn)

    # Resumen de fuentes utilizadas
    print("\n📋 Resumen de fuentes:")
    fuentes = {
        "CPR":  "CSV presupuesto" if "presupuesto_total"      in datos_ppto  else "MANUAL_OVERRIDES ⚠️",
        "TPS":  "MANUAL_OVERRIDES ⚠️ (RRHH HCDN no automatizado)",
        "CAF":  "CSV presupuesto" if "presupuesto_devengado"   in datos_ppto  else "MANUAL_OVERRIDES ⚠️",
        "TMM":  "MANUAL_OVERRIDES ⚠️ (pendiente scraping SIL – Etapa 4)",
        "ITT":  "MANUAL_OVERRIDES ⚠️ (pendiente actas HCDN – Etapa 4)",
        "IQP":  "MANUAL_OVERRIDES ⚠️ (pendiente votaciones HCDN – Etapa 4)",
        "CUN":  "CSV presupuesto" if "presupuesto_total"      in datos_ppto  else "MANUAL_OVERRIDES ⚠️",
        "CLS":  "MANUAL_OVERRIDES ⚠️ (clasificación manual BO)",
        "TEF":  "MANUAL_OVERRIDES ⚠️ (pendiente datos AGN)",
        "CAD":  "MANUAL_OVERRIDES ⚠️ (auditoría propia)",
        "EVD":  "MANUAL_OVERRIDES ⚠️ (auditoría propia)",
        "TCI":  "MANUAL_OVERRIDES ⚠️ (Google Analytics)",
    }
    for ind, fuente in fuentes.items():
        icono = "✅" if "⚠️" not in fuente else "⏳"
        print(f"   {icono} [{ind}] {fuente}")

    return datos


if __name__ == "__main__":
    datos = construir_datos()
    print(f"\n✅ Dict listo con {len(datos)} claves para calcular_todos()")