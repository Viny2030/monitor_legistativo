"""
scraper_hcdn.py – Monitor Legislativo Argentina
================================================
Etapa 4: Scraping de HCDN / SIL para los indicadores que requieren
datos de votaciones y actas de comisión:

  TMM – Tiempo Medio de Maduración (SIL / datos.hcdn.gob.ar)
  ITT – Intensidad de Trabajo Técnico (actas de comisión HCDN)
  IQP – Índice de Quórum y Permanencia (votaciones nominales HCDN)

Fuentes:
  Votaciones nominales: https://datos.hcdn.gob.ar/dataset/votaciones
  Actas de comisión:    https://datos.hcdn.gob.ar/dataset/reuniones-comisiones
  SIL / proyectos:      https://datos.hcdn.gob.ar/dataset/proyectos

USO RÁPIDO:
  from scraper_hcdn import obtener_datos_hcdn
  datos_hcdn = obtener_datos_hcdn(anio=2024)
  # Retorna dict con claves: proyectos, horas_comision, horas_pleno, votaciones
"""

from __future__ import annotations
import requests
import pandas as pd
from pathlib import Path
from datetime import date, timedelta
from io import StringIO

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; MonitorLegislativo/1.0; "
        "https://github.com/Viny2030/monitor_legistativo)"
    ),
    "Accept": "application/json, text/csv, */*",
}
TIMEOUT = 25


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_json(url: str) -> dict | list | None:
    """GET que devuelve JSON o None en caso de error."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ⚠️  GET JSON falló ({url}): {e}")
        return None


def _get_csv(url: str) -> pd.DataFrame | None:
    """GET que devuelve DataFrame desde CSV o None en caso de error."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return pd.read_csv(StringIO(r.text), on_bad_lines="skip")
    except Exception as e:
        print(f"  ⚠️  GET CSV falló ({url}): {e}")
        return None


def _buscar_resource_csv(dataset_id: str, anio: int) -> str | None:
    """
    Busca la URL de descarga CSV de un dataset en datos.hcdn.gob.ar
    usando la API CKAN del portal.
    """
    api_url = f"https://datos.hcdn.gob.ar/api/3/action/package_show?id={dataset_id}"
    data = _get_json(api_url)
    if not data or not data.get("success"):
        return None

    recursos = data["result"].get("resources", [])
    # Preferir recurso CSV que coincida con el año
    for r in recursos:
        url = r.get("url", "")
        fmt = r.get("format", "").upper()
        if fmt == "CSV" and str(anio) in url:
            return url
    # Fallback: cualquier CSV
    for r in recursos:
        if r.get("format", "").upper() == "CSV":
            return r.get("url")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. PROYECTOS → TMM (Tiempo Medio de Maduración)
# Fuente: datos.hcdn.gob.ar dataset "proyectos"
# ─────────────────────────────────────────────────────────────────────────────

def obtener_proyectos_para_tmm(anio: int = 2024) -> list[dict]:
    """
    Descarga el dataset de proyectos de HCDN y filtra los que tienen
    fecha de ingreso y fecha de dictamen en el año indicado.

    Devuelve lista de dicts:
      [{"fecha_ingreso": "YYYY-MM-DD", "fecha_dictamen": "YYYY-MM-DD"}, ...]
    """
    print(f"\n🔍 [TMM] Descargando proyectos {anio} de datos.hcdn.gob.ar ...")

    # URLs conocidas del portal de datos abiertos HCDN
    urls_candidatas = [
        f"https://datos.hcdn.gob.ar/dataset/proyectos/resource/proyectos-{anio}/download/proyectos{anio}.csv",
        f"https://datos.hcdn.gob.ar/dataset/proyectos/resource/download/proyectos{anio}.csv",
    ]

    # También intentar via API CKAN
    resource_url = _buscar_resource_csv("proyectos", anio)
    if resource_url:
        urls_candidatas.insert(0, resource_url)

    df = None
    for url in urls_candidatas:
        df = _get_csv(url)
        if df is not None and len(df) > 0:
            print(f"  ✅ {len(df)} proyectos descargados")
            break

    if df is None:
        print("  ❌ No se pudieron descargar proyectos. Verificá la URL en datos.hcdn.gob.ar")
        print("     → https://datos.hcdn.gob.ar/dataset/proyectos")
        return []

    # Guardar CSV crudo
    df.to_csv(DATA_DIR / f"proyectos_{anio}_raw.csv", index=False, encoding="utf-8-sig")

    # Detectar columnas de fecha
    col_ingreso  = None
    col_dictamen = None
    for col in df.columns:
        cl = col.lower()
        if "ingreso" in cl or "presentac" in cl or "fecha_crea" in cl:
            col_ingreso = col
        if "dictamen" in cl or "despacho" in cl:
            col_dictamen = col

    if not col_ingreso or not col_dictamen:
        print(f"  ⚠️  No se encontraron columnas de fecha. Columnas disponibles: {list(df.columns)}")
        print("     Completar MANUAL_OVERRIDES en data_loader.py con los datos del CSV descargado.")
        return []

    proyectos = []
    for _, row in df.iterrows():
        try:
            fi = pd.to_datetime(row[col_ingreso], dayfirst=True, errors="coerce")
            fd = pd.to_datetime(row[col_dictamen], dayfirst=True, errors="coerce")
            if pd.isna(fi) or pd.isna(fd):
                continue
            if fi.year != anio and fd.year != anio:
                continue
            if fd < fi:
                continue
            proyectos.append({
                "fecha_ingreso": fi.strftime("%Y-%m-%d"),
                "fecha_dictamen": fd.strftime("%Y-%m-%d"),
            })
        except Exception:
            continue

    print(f"  ✅ {len(proyectos)} proyectos con ambas fechas válidas para TMM")
    return proyectos


# ─────────────────────────────────────────────────────────────────────────────
# 2. REUNIONES DE COMISIÓN → ITT (Intensidad de Trabajo Técnico)
# Fuente: datos.hcdn.gob.ar dataset "reuniones-comisiones"
# ─────────────────────────────────────────────────────────────────────────────

def obtener_horas_comision(anio: int = 2024) -> dict:
    """
    Descarga el dataset de reuniones de comisión y calcula:
      - horas_comision : suma de duración de reuniones de comisión
      - horas_pleno    : suma de duración de sesiones en el recinto

    Devuelve: {"horas_comision": float, "horas_pleno": float}
    """
    print(f"\n🔍 [ITT] Descargando reuniones de comisión {anio} ...")

    urls_candidatas = [
        f"https://datos.hcdn.gob.ar/dataset/reuniones-comisiones/resource/reuniones-{anio}/download/reuniones{anio}.csv",
        f"https://datos.hcdn.gob.ar/dataset/reuniones-comisiones/resource/download/reuniones{anio}.csv",
    ]
    resource_url = _buscar_resource_csv("reuniones-comisiones", anio)
    if resource_url:
        urls_candidatas.insert(0, resource_url)

    df = None
    for url in urls_candidatas:
        df = _get_csv(url)
        if df is not None and len(df) > 0:
            print(f"  ✅ {len(df)} reuniones descargadas")
            break

    if df is None:
        print("  ❌ No se pudieron descargar reuniones de comisión.")
        print("     → https://datos.hcdn.gob.ar/dataset/reuniones-comisiones")
        return {}

    df.to_csv(DATA_DIR / f"reuniones_comision_{anio}_raw.csv", index=False, encoding="utf-8-sig")

    # Detectar columna de duración
    col_dur = None
    col_tipo = None
    for col in df.columns:
        cl = col.lower()
        if "duracion" in cl or "minutos" in cl or "horas" in cl or "duracion" in cl:
            col_dur = col
        if "tipo" in cl or "modalidad" in cl or "clase" in cl:
            col_tipo = col

    if not col_dur:
        print(f"  ⚠️  No se encontró columna de duración. Columnas: {list(df.columns)}")
        return {}

    df["_dur_num"] = pd.to_numeric(df[col_dur], errors="coerce").fillna(0)

    # Si hay columna de tipo, separar comisión de pleno
    if col_tipo:
        mask_pleno = df[col_tipo].astype(str).str.lower().str.contains("pleno|sesion|plen")
        df_pleno = df[mask_pleno]
        df_comision = df[~mask_pleno]
    else:
        # Sin columna de tipo, asumir todo como comisión
        df_comision = df
        df_pleno = pd.DataFrame(columns=df.columns)

    # Convertir a horas (si los valores parecen estar en minutos)
    factor = 1/60 if df["_dur_num"].median() > 60 else 1

    horas_com  = float(df_comision["_dur_num"].sum() * factor)
    horas_pleno = float(df_pleno["_dur_num"].sum() * factor)

    # Si no hay pleno en el dataset, usar estimación basada en diario de sesiones
    if horas_pleno == 0:
        print("  ℹ️  No se detectaron sesiones plenarias en el dataset. Usando estimación.")
        horas_pleno = horas_com / 3.875  # usando ITT de ejemplo como ratio inverso

    print(f"  ✅ Horas comisión: {horas_com:.1f} | Horas pleno: {horas_pleno:.1f}")
    return {"horas_comision": round(horas_com, 1), "horas_pleno": round(horas_pleno, 1)}


# ─────────────────────────────────────────────────────────────────────────────
# 3. VOTACIONES NOMINALES → IQP (Índice de Quórum y Permanencia)
# Fuente: datos.hcdn.gob.ar dataset "votaciones"
# ─────────────────────────────────────────────────────────────────────────────

def obtener_votaciones_para_iqp(anio: int = 2024) -> list[dict]:
    """
    Descarga el dataset de votaciones nominales y arma la lista:
      [{"presentes": N}, ...]

    Devuelve lista de dicts lista para IQP.
    """
    print(f"\n🔍 [IQP] Descargando votaciones nominales {anio} ...")

    urls_candidatas = [
        f"https://datos.hcdn.gob.ar/dataset/votaciones/resource/votaciones-{anio}/download/votaciones{anio}.csv",
        f"https://datos.hcdn.gob.ar/dataset/votaciones/resource/download/votaciones{anio}.csv",
        f"https://datos.hcdn.gob.ar/dataset/votaciones-nominales/resource/download/votaciones{anio}.csv",
    ]
    resource_url = _buscar_resource_csv("votaciones", anio)
    if resource_url:
        urls_candidatas.insert(0, resource_url)

    df = None
    for url in urls_candidatas:
        df = _get_csv(url)
        if df is not None and len(df) > 0:
            print(f"  ✅ {len(df)} registros de votaciones descargados")
            break

    if df is None:
        print("  ❌ No se pudieron descargar votaciones nominales.")
        print("     → https://datos.hcdn.gob.ar/dataset/votaciones")
        return []

    df.to_csv(DATA_DIR / f"votaciones_{anio}_raw.csv", index=False, encoding="utf-8-sig")

    # Detectar columna de presentes/asistentes
    col_presentes = None
    for col in df.columns:
        cl = col.lower()
        if "presente" in cl or "asistente" in cl or "voto" in cl or "quorum" in cl:
            col_presentes = col
            break

    # Alternativa: si hay columnas afirmativo/negativo/abstencion, sumarlas
    if not col_presentes:
        col_afirm = next((c for c in df.columns if "afirm" in c.lower() or "si" == c.lower()), None)
        col_neg   = next((c for c in df.columns if "negat" in c.lower() or "no" == c.lower()), None)
        if col_afirm and col_neg:
            df["_presentes"] = (
                pd.to_numeric(df[col_afirm], errors="coerce").fillna(0) +
                pd.to_numeric(df[col_neg],   errors="coerce").fillna(0)
            )
            col_presentes = "_presentes"

    if not col_presentes:
        print(f"  ⚠️  No se encontró columna de presentes. Columnas: {list(df.columns)}")
        return []

    # Agrupar por sesión si hay columna de sesión
    col_sesion = next((c for c in df.columns if "sesion" in c.lower() or "fecha" in c.lower()), None)

    if col_sesion:
        # Agrupar por sesión y tomar el máximo de presentes (quórum inicial)
        df["_pres_num"] = pd.to_numeric(df[col_presentes], errors="coerce")
        resumen = df.groupby(col_sesion)["_pres_num"].max().dropna()
        votaciones = [{"presentes": int(v)} for v in resumen if v > 0]
    else:
        df["_pres_num"] = pd.to_numeric(df[col_presentes], errors="coerce")
        votaciones = [{"presentes": int(v)} for v in df["_pres_num"].dropna() if v > 0]

    print(f"  ✅ {len(votaciones)} sesiones con datos de presentes para IQP")
    return votaciones


# ─────────────────────────────────────────────────────────────────────────────
# Función principal: obtener todos los datos HCDN
# ─────────────────────────────────────────────────────────────────────────────

def obtener_datos_hcdn(anio: int = 2024) -> dict:
    """
    Ejecuta los tres scrapers y devuelve un dict listo para
    actualizar MANUAL_OVERRIDES en data_loader.py:

      {
        "proyectos":      [...],   # para TMM
        "horas_comision": float,   # para ITT
        "horas_pleno":    float,   # para ITT
        "votaciones":     [...],   # para IQP
      }

    Las claves que no se pudieron obtener no aparecen en el dict.
    """
    print(f"\n{'='*60}")
    print(f" SCRAPER HCDN – Datos para TMM / ITT / IQP  ({anio})")
    print(f"{'='*60}")

    resultado = {}

    proyectos = obtener_proyectos_para_tmm(anio)
    if proyectos:
        resultado["proyectos"] = proyectos

    horas = obtener_horas_comision(anio)
    resultado.update(horas)

    votaciones = obtener_votaciones_para_iqp(anio)
    if votaciones:
        resultado["votaciones"] = votaciones

    print(f"\n{'='*60}")
    print(f" Resumen de datos obtenidos:")
    print(f"  TMM: {'✅ ' + str(len(resultado.get('proyectos',[]))) + ' proyectos' if 'proyectos' in resultado else '❌ no disponible'}")
    print(f"  ITT: {'✅ horas_comision=' + str(resultado.get('horas_comision','—')) if 'horas_comision' in resultado else '❌ no disponible'}")
    print(f"  IQP: {'✅ ' + str(len(resultado.get('votaciones',[]))) + ' sesiones' if 'votaciones' in resultado else '❌ no disponible'}")
    print(f"{'='*60}")

    # Guardar resumen en JSON para referencia
    import json
    resumen = {k: v for k, v in resultado.items() if k not in ('proyectos', 'votaciones')}
    resumen["n_proyectos"] = len(resultado.get("proyectos", []))
    resumen["n_votaciones"] = len(resultado.get("votaciones", []))
    with open(DATA_DIR / f"hcdn_resumen_{anio}.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    return resultado


if __name__ == "__main__":
    anio = date.today().year
    datos = obtener_datos_hcdn(anio)

    if datos:
        print("\n💡 Para usar estos datos en calculos.py, actualizá MANUAL_OVERRIDES en data_loader.py:")
        print("   o llamá a construir_datos() — ya integra scraper_hcdn automáticamente.")
    else:
        print("\n⚠️  No se obtuvieron datos automáticos.")
        print("   Completá MANUAL_OVERRIDES en data_loader.py con datos del portal:")
        print("   https://datos.hcdn.gob.ar")