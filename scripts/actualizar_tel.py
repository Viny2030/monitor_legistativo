"""
scripts/actualizar_tel.py
Tasa de Éxito Legislativo (TEL) — REAL desde datos.hcdn.gob.ar
===============================================================
Fuente: https://datos.hcdn.gob.ar/dataset/proyectos-parlamentarios
CSV columnas confirmadas: proyecto_id, titulo, publicacion_fecha,
                          publicacion_id, camara_origen, exp_diputados,
                          exp_senado, tipo, autor

TEL = proyectos convertidos en ley / proyectos presentados (por autor, período)

Nota: el dataset principal lista todos los proyectos; el de "leyes"
(proyectos convertidos en ley) está en un recurso separado del mismo dataset.
"""

import requests
import pandas as pd
import os
import sys

# ── ENDPOINTS CKAN ────────────────────────────────────────────────────────────
BASE_CKAN = "https://datos.hcdn.gob.ar/api/3/action/package_show"

# Dataset principal de proyectos (confirmado activo)
DATASET_PROYECTOS = "proyectos-parlamentarios"

# URL directa del CSV más reciente (versión 1.6, verificada)
URL_PROYECTOS_CSV = (
    "https://datos.hcdn.gob.ar/dataset/839441fc-1b5c-45b8-82c9-8b0f18ac7c9b"
    "/resource/22b2d52c-7a0e-426b-ac0a-a3326c388ba6"
    "/download/proyectosparlamentarios1.4.csv"
)

# Dataset de proyectos convertidos en ley (recurso separado en HCDN)
DATASET_LEYES = "leyes"  # CKAN id alternativo

HEADERS = {"User-Agent": "MEL-TP Monitor Legislativo (datos abiertos)"}


def obtener_recursos_ckan(dataset_id: str) -> list[tuple[str, str]]:
    """Consulta la API CKAN y devuelve lista de (nombre, url) para CSVs."""
    try:
        r = requests.get(
            BASE_CKAN,
            params={"id": dataset_id},
            headers=HEADERS,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        recursos = data.get("result", {}).get("resources", [])
        return [
            (rec.get("name", ""), rec.get("url", ""))
            for rec in recursos
            if rec.get("url", "").endswith(".csv")
        ]
    except Exception as e:
        print(f"⚠️  CKAN error ({dataset_id}): {e}")
        return []


def descargar_csv(url: str, label: str = "") -> pd.DataFrame | None:
    """Descarga un CSV y devuelve DataFrame. Maneja encodings alternativos."""
    print(f"  ⬇️  {label or url}")
    for enc in ("utf-8", "latin-1", "iso-8859-1"):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            r.raise_for_status()
            from io import StringIO
            df = pd.read_csv(StringIO(r.content.decode(enc, errors="replace")),
                             low_memory=False)
            print(f"     ✅ {len(df):,} filas · columnas: {list(df.columns)}")
            return df
        except Exception as e:
            print(f"     ⚠️  enc={enc}: {e}")
    return None


def normalizar_autor(nombre: str) -> str:
    """Normaliza 'APELLIDO, NOMBRE' → 'APELLIDO, NOMBRE' en mayúsculas."""
    if not isinstance(nombre, str):
        return ""
    return nombre.strip().upper()


def calcular_tel(df_todos: pd.DataFrame,
                 df_leyes: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Calcula TEL por autor.

    Parámetros
    ----------
    df_todos  : DataFrame con todos los proyectos (columna 'autor')
    df_leyes  : DataFrame con proyectos convertidos en ley (columna 'autor')
                Si es None, usa df_todos filtrando tipo == 'LEY' como proxy.

    Retorna
    -------
    DataFrame con columnas: autor, presentados, aprobados, tel
    """
    # Columna autor: puede venir como 'autor' o 'AUTOR'
    col_autor = next(
        (c for c in df_todos.columns if c.lower() == "autor"), None
    )
    if col_autor is None:
        print("❌ Columna 'autor' no encontrada.")
        print(f"   Columnas disponibles: {list(df_todos.columns)}")
        return pd.DataFrame()

    # Solo proyectos originados en Diputados (camara_origen == 'Diputados')
    col_camara = next(
        (c for c in df_todos.columns if "camara" in c.lower()), None
    )
    if col_camara:
        mask_dip = df_todos[col_camara].str.strip().str.lower() == "diputados"
        df_todos = df_todos[mask_dip]

    df_todos["_autor"] = df_todos[col_autor].apply(normalizar_autor)
    df_todos = df_todos[df_todos["_autor"].str.len() > 0]

    presentados = df_todos.groupby("_autor").size().rename("presentados")

    if df_leyes is not None and not df_leyes.empty:
        col_a2 = next(
            (c for c in df_leyes.columns if c.lower() == "autor"), None
        )
        if col_a2:
            df_leyes["_autor"] = df_leyes[col_a2].apply(normalizar_autor)
            aprobados = (
                df_leyes[df_leyes["_autor"].str.len() > 0]
                .groupby("_autor")
                .size()
                .rename("aprobados")
            )
        else:
            aprobados = pd.Series(dtype=int, name="aprobados")
    else:
        # Proxy: proyectos de tipo LEY como indicador de actividad legislativa
        col_tipo = next(
            (c for c in df_todos.columns if c.lower() == "tipo"), None
        )
        if col_tipo:
            mask_ley = df_todos[col_tipo].str.upper().str.strip() == "LEY"
            aprobados = (
                df_todos[mask_ley]
                .groupby("_autor")
                .size()
                .rename("aprobados")
            )
        else:
            aprobados = pd.Series(dtype=int, name="aprobados")

    tel = pd.concat([presentados, aprobados], axis=1).fillna(0)
    tel["aprobados"] = tel["aprobados"].astype(int)
    tel["presentados"] = tel["presentados"].astype(int)

    # TEL = aprobados / presentados, capped a 1.0
    tel["tel"] = (tel["aprobados"] / tel["presentados"].replace(0, 1)).clip(0, 1).round(4)

    return tel.reset_index().rename(columns={"_autor": "autor"})


def main():
    print("=" * 60)
    print("=== MEL-TP: Actualizando TEL desde datos.hcdn.gob.ar ===")
    print("=" * 60)

    # 1. Intentar obtener recursos vía CKAN
    print("\n📡 Consultando CKAN...")
    recursos_proyectos = obtener_recursos_ckan(DATASET_PROYECTOS)
    recursos_leyes = obtener_recursos_ckan(DATASET_LEYES)

    # 2. Descargar CSV de proyectos
    df_proyectos = None
    if recursos_proyectos:
        for nombre, url in recursos_proyectos[:2]:  # intentar primeros 2
            df_proyectos = descargar_csv(url, f"Proyectos: {nombre}")
            if df_proyectos is not None:
                break

    if df_proyectos is None:
        print(f"\n📋 CKAN falló. Usando URL directa conocida...")
        df_proyectos = descargar_csv(URL_PROYECTOS_CSV, "proyectos (URL directa)")

    if df_proyectos is None:
        print("❌ No se pudo obtener el dataset de proyectos.")
        sys.exit(1)

    # 3. Descargar CSV de leyes (opcional)
    df_leyes = None
    if recursos_leyes:
        for nombre, url in recursos_leyes[:1]:
            df_leyes = descargar_csv(url, f"Leyes: {nombre}")
            if df_leyes is not None:
                break

    if df_leyes is None:
        print("  ℹ️  Dataset de leyes no disponible. Usando proxy por tipo='LEY'")

    # 4. Calcular TEL
    print("\n⚙️  Calculando TEL por autor...")
    tel_df = calcular_tel(df_proyectos, df_leyes)

    if tel_df.empty:
        print("❌ No se pudo calcular TEL.")
        sys.exit(1)

    # 5. Guardar
    out = "tel_diputados.csv"
    tel_df.to_csv(out, index=False)
    print(f"\n✅ TEL calculado: {len(tel_df):,} autores → '{out}'")
    print(f"   TEL promedio: {tel_df['tel'].mean():.4f}")
    print(f"   TEL > 0:      {(tel_df['tel'] > 0).sum():,} autores")
    print("\nTop 10 por TEL:")
    print(
        tel_df[tel_df["presentados"] >= 5]
        .sort_values("tel", ascending=False)
        .head(10)
        .to_string(index=False)
    )
    return tel_df


if __name__ == "__main__":
    main()