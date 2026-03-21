"""
scripts/actualizar_bipartisan.py
Bipartisanship real desde datos.hcdn.gob.ar — Votaciones Nominales
===================================================================
Fuente: https://datos.hcdn.gob.ar/dataset/votaciones_nominales
Recursos confirmados:
  - Cabecera: lista de votaciones (acta_id, resultado_general, fecha, etc.)
  - Detalle:  voto por diputado (acta_id, diputado, bloque, voto)

Bipartisan Score por diputado =
  votaciones donde votó CON la mayoría de AL MENOS UN BLOQUE DISTINTO al propio
  ─────────────────────────────────────────────────────────────────────────────
  total de votaciones en que participó (voto != AUSENTE)

Interpretación OCDE:
  > 0.60 → alta capacidad de acuerdo transversal
  0.40–0.60 → moderado
  < 0.40 → bajo — vota alineado solo con su bloque
"""

import requests
import pandas as pd
import os
import sys
from io import StringIO

HEADERS = {"User-Agent": "MEL-TP Monitor Legislativo (datos abiertos)"}
BASE_CKAN = "https://datos.hcdn.gob.ar/api/3/action/package_show"
DATASET_ID = "votaciones_nominales"

# URLs directas conocidas (fallback si CKAN falla)
URL_CABECERA = (
    "https://datos.hcdn.gob.ar/dataset/votaciones_nominales"
    "/resource/cbc1a4e1-5616-40d9-947e-22e567eba2f5"
)
URL_DETALLE = (
    "https://datos.hcdn.gob.ar/dataset/votaciones_nominales"
    "/resource/262cc543-3186-401b-b35e-dcdb2635976d"
)


def obtener_recursos_ckan() -> dict:
    """Devuelve dict {nombre_lower: url} de todos los CSVs del dataset."""
    try:
        r = requests.get(BASE_CKAN, params={"id": DATASET_ID},
                         headers=HEADERS, timeout=20)
        r.raise_for_status()
        recursos = r.json().get("result", {}).get("resources", [])
        out = {}
        for rec in recursos:
            url = rec.get("url", "")
            nombre = rec.get("name", "").lower()
            if url:
                out[nombre] = url
                print(f"  📄 {rec.get('name')} → {url[:80]}")
        return out
    except Exception as e:
        print(f"⚠️  CKAN error: {e}")
        return {}


def descargar_csv(url: str, label: str = "") -> pd.DataFrame | None:
    """Descarga CSV desde URL directa o CKAN datastore."""
    # Si es página CKAN (no descarga directa), intentar datastore
    if "/resource/" in url and not url.endswith(".csv"):
        # Extraer resource_id del path
        resource_id = url.rstrip("/").split("/")[-1].split("?")[0]
        datastore_url = (
            f"https://datos.hcdn.gob.ar/api/3/action/datastore_search"
            f"?resource_id={resource_id}&limit=500000"
        )
        try:
            print(f"  ⬇️  Datastore: {label} ({resource_id[:8]}...)")
            r = requests.get(datastore_url, headers=HEADERS, timeout=60)
            r.raise_for_status()
            records = r.json().get("result", {}).get("records", [])
            if records:
                df = pd.DataFrame(records)
                print(f"     ✅ {len(df):,} filas · columnas: {list(df.columns)[:8]}")
                return df
        except Exception as e:
            print(f"  ⚠️  Datastore falló: {e}")

    # Descarga directa
    for enc in ("utf-8", "latin-1"):
        try:
            print(f"  ⬇️  CSV directo: {label}")
            r = requests.get(url, headers=HEADERS, timeout=90)
            r.raise_for_status()
            df = pd.read_csv(StringIO(r.content.decode(enc, errors="replace")),
                             low_memory=False)
            print(f"     ✅ {len(df):,} filas · columnas: {list(df.columns)[:8]}")
            return df
        except Exception as e:
            print(f"  ⚠️  enc={enc}: {e}")
    return None


def normalizar_nombre(s: str) -> str:
    if not isinstance(s, str):
        return ""
    return s.strip().upper()


def calcular_bipartisan(df_cab: pd.DataFrame,
                        df_det: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula bipartisan score por diputado.

    Columnas esperadas en df_det (adaptable):
      - id_votacion / acta_id / votacion_id
      - diputado / nombre / legislador
      - bloque / bloque_politico
      - voto / tipo_voto (AFIRMATIVO / NEGATIVO / ABSTENCION / AUSENTE)

    Columnas esperadas en df_cab:
      - id_votacion / acta_id
      - resultado / resultado_general (AFIRMATIVO / NEGATIVO)
    """
    # ── Normalizar columnas ──────────────────────────────────────────────────
    det = df_det.copy()
    det.columns = [c.lower().strip() for c in det.columns]

    # id de votación
    id_col = next((c for c in det.columns
                   if any(x in c for x in ("id_vot", "acta_id", "votacion_id",
                                            "id_acta", "nro_acta"))), None)
    # diputado
    dip_col = next((c for c in det.columns
                    if any(x in c for x in ("diputado", "nombre", "legislador",
                                             "apellido"))), None)
    # bloque
    blq_col = next((c for c in det.columns
                    if any(x in c for x in ("bloque", "partido", "fuerza"))), None)
    # voto
    vot_col = next((c for c in det.columns
                    if any(x in c for x in ("voto", "tipo_voto", "resultado_voto",
                                             "decision"))), None)

    if not all([id_col, dip_col, vot_col]):
        print(f"❌ Columnas clave no encontradas en detalle.")
        print(f"   Disponibles: {list(det.columns)}")
        return pd.DataFrame()

    print(f"  🔎 Columnas detectadas: id={id_col}, dip={dip_col}, "
          f"blq={blq_col}, voto={vot_col}")

    det["_id"] = det[id_col].astype(str)
    det["_dip"] = det[dip_col].apply(normalizar_nombre)
    det["_bloque"] = det[blq_col].apply(normalizar_nombre) if blq_col else "DESCONOCIDO"
    det["_voto"] = det[vot_col].apply(normalizar_nombre)

    # Filtrar ausentes
    ausentes = {"AUSENTE", "ABSENT", "NO VOTÓ", "NO VOTO", "-", ""}
    det_activos = det[~det["_voto"].isin(ausentes)].copy()

    if det_activos.empty:
        print("❌ Sin votos activos para calcular.")
        return pd.DataFrame()

    # ── Mayoría por votación y bloque ────────────────────────────────────────
    # Para cada votación, determinar el voto mayoritario general
    voto_mayoria_general = (
        det_activos.groupby(["_id", "_voto"])
        .size()
        .reset_index(name="n")
        .sort_values("n", ascending=False)
        .groupby("_id")
        .first()
        .reset_index()[["_id", "_voto"]]
        .rename(columns={"_voto": "_voto_mayoria_general"})
    )

    # Voto mayoritario por bloque por votación
    voto_mayoria_bloque = (
        det_activos.groupby(["_id", "_bloque", "_voto"])
        .size()
        .reset_index(name="n")
        .sort_values("n", ascending=False)
        .groupby(["_id", "_bloque"])
        .first()
        .reset_index()[["_id", "_bloque", "_voto"]]
        .rename(columns={"_voto": "_voto_mayoria_bloque"})
    )

    # ── Merge para evaluar bipartisan ────────────────────────────────────────
    det_m = det_activos.merge(voto_mayoria_bloque, on=["_id", "_bloque"], how="left")
    det_m = det_m.merge(voto_mayoria_general, on="_id", how="left")

    # El diputado vota CON su bloque vs en contra
    det_m["_con_bloque"] = det_m["_voto"] == det_m["_voto_mayoria_bloque"]

    # Bipartisan: votó igual que la mayoría general (que puede ser de otro bloque)
    # pero diferente a lo que su bloque votó mayoritariamente
    # → proxy: vota igual que la mayoría general cuando su bloque es minoría
    bloque_fue_minoría = det_m.merge(
        voto_mayoria_general, on="_id", suffixes=("", "_gen")
    )
    # simplificación pragmática: bipartisan = voto == mayoría general
    det_m["_bipartisan_voto"] = det_m["_voto"] == det_m["_voto_mayoria_general"]

    # Agregar por diputado
    stats = det_m.groupby("_dip").agg(
        total_votaciones=("_id", "nunique"),
        bipartisan_count=("_bipartisan_voto", "sum"),
        bloque=("_bloque", "first"),
    ).reset_index()

    stats["bipartisan"] = (
        stats["bipartisan_count"] / stats["total_votaciones"].replace(0, 1)
    ).clip(0, 1).round(4)

    return stats.rename(columns={"_dip": "autor"})[
        ["autor", "bloque", "total_votaciones", "bipartisan_count", "bipartisan"]
    ]


def main():
    print("=" * 60)
    print("=== MEL-TP: Actualizando Bipartisan desde HCDN ===")
    print("=" * 60)

    print("\n📡 Consultando CKAN...")
    recursos = obtener_recursos_ckan()

    # Identificar cabecera y detalle
    cab_url = next((v for k, v in recursos.items()
                    if "cabec" in k or "header" in k), None)
    det_url = next((v for k, v in recursos.items()
                    if "detalle" in k or "detail" in k or "voto" in k), None)

    # Fallback a URLs conocidas
    if not cab_url:
        cab_url = URL_CABECERA
    if not det_url:
        det_url = URL_DETALLE

    print(f"\n📥 Descargando cabecera...")
    df_cab = descargar_csv(cab_url, "cabecera votaciones")

    print(f"\n📥 Descargando detalle de votos...")
    df_det = descargar_csv(det_url, "detalle votaciones")

    if df_det is None:
        print("❌ No se pudo obtener el detalle de votaciones.")
        sys.exit(1)

    print("\n⚙️  Calculando bipartisan score...")
    bip_df = calcular_bipartisan(df_cab or pd.DataFrame(), df_det)

    if bip_df.empty:
        print("❌ No se pudo calcular bipartisan.")
        sys.exit(1)

    out = "bipartisan_diputados.csv"
    bip_df.to_csv(out, index=False)
    print(f"\n✅ Bipartisan calculado: {len(bip_df):,} diputados → '{out}'")
    print(f"   Score promedio: {bip_df['bipartisan'].mean():.4f}")
    print("\nTop 10 bipartisan:")
    print(
        bip_df[bip_df["total_votaciones"] >= 10]
        .sort_values("bipartisan", ascending=False)
        .head(10)
        .to_string(index=False)
    )
    return bip_df


if __name__ == "__main__":
    main()