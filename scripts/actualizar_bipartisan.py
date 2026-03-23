"""
scripts/actualizar_bipartisan.py - CORREGIDO
"""

import requests
import pandas as pd
import os
import sys
from io import StringIO
import json

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
    """Descarga data desde URL directa o CKAN datastore."""
    # 1. Intentar via Datastore API si parece un recurso CKAN
    if "/resource/" in url and not url.endswith(".csv"):
        resource_id = url.rstrip("/").split("/")[-1].split("?")[0]
        datastore_url = (
            f"https://datos.hcdn.gob.ar/api/3/action/datastore_search"
            f"?resource_id={resource_id}&limit=500000"
        )
        try:
            print(f"  ⬇️  Datastore: {label} ({resource_id[:8]}...)")
            r = requests.get(datastore_url, headers=HEADERS, timeout=60)
            if r.status_code == 200:
                records = r.json().get("result", {}).get("records", [])
                if records:
                    df = pd.DataFrame(records)
                    print(f"     ✅ {len(df):,} filas (Datastore)")
                    return df
        except Exception as e:
            print(f"  ⚠️  Datastore falló: {e}")

    # 2. Descarga directa (con detección de formato JSON/CSV)
    for enc in ("utf-8", "latin-1"):
        try:
            print(f"  ⬇️  Descarga directa: {label} (intento {enc})")
            r = requests.get(url, headers=HEADERS, timeout=90)
            r.raise_for_status()
            content = r.content.decode(enc, errors="replace").strip()
            
            # Si el contenido empieza con '{', es un JSON, no un CSV
            if content.startswith("{") or content.startswith("["):
                try:
                    # Muchos datos de HCDN vienen como { "1": {...}, "2": {...} }
                    data_json = json.loads(content)
                    if isinstance(data_json, dict) and "1" in data_json:
                        df = pd.DataFrame.from_dict(data_json, orient="index")
                    else:
                        df = pd.read_json(StringIO(content))
                    print(f"     ✅ {len(df):,} filas (JSON detectado)")
                    return df
                except:
                    pass

            # Si no es JSON, intentar como CSV
            df = pd.read_csv(StringIO(content), low_memory=False)
            if len(df.columns) < 2: # Probable error de lectura
                continue
                
            print(f"     ✅ {len(df):,} filas (CSV detectado)")
            return df
        except Exception as e:
            print(f"  ⚠️  Error con {enc}: {e}")
    return None


def normalizar_nombre(s: str) -> str:
    if not isinstance(s, str):
        return ""
    return s.strip().upper()


def calcular_bipartisan(df_cab: pd.DataFrame,
                        df_det: pd.DataFrame) -> pd.DataFrame:
    """Calcula bipartisan score por diputado."""
    if df_det is None or df_det.empty:
        return pd.DataFrame()

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
        return pd.DataFrame()

    print(f"  🔎 Columnas detectadas: id={id_col}, dip={dip_col}, blq={blq_col}, voto={vot_col}")

    det["_id"] = det[id_col].astype(str)
    det["_dip"] = det[dip_col].apply(normalizar_nombre)
    det["_bloque"] = det[blq_col].apply(normalizar_nombre) if blq_col else "DESCONOCIDO"
    det["_voto"] = det[vot_col].apply(normalizar_nombre)

    # Filtrar ausentes
    ausentes = {"AUSENTE", "ABSENT", "NO VOTÓ", "NO VOTO", "-", "", "nan", "NONE"}
    det_activos = det[~det["_voto"].isin(ausentes)].copy()

    if det_activos.empty:
        print("❌ Sin votos activos para calcular.")
        return pd.DataFrame()

    # Voto mayoritario general por votación
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

    # Voto mayoritario por bloque
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

    det_m = det_activos.merge(voto_mayoria_bloque, on=["_id", "_bloque"], how="left")
    det_m = det_m.merge(voto_mayoria_general, on="_id", how="left")

    # Proxy de bipartisan: votó igual que la mayoría general
    det_m["_bipartisan_voto"] = det_m["_voto"] == det_m["_voto_mayoria_general"]

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

    recursos = obtener_recursos_ckan()

    cab_url = next((v for k, v in recursos.items() if "cabec" in k), URL_CABECERA)
    det_url = next((v for k, v in recursos.items() if "detalle" in k or "voto" in k), URL_DETALLE)

    print(f"\n📥 Descargando cabecera...")
    df_cab = descargar_csv(cab_url, "cabecera votaciones")

    print(f"\n📥 Descargando detalle de votos...")
    df_det = descargar_csv(det_url, "detalle votaciones")

    if df_det is None or df_det.empty:
        print("❌ No se pudo obtener el detalle de votaciones.")
        sys.exit(1)

    print("\n⚙️  Calculando bipartisan score...")
    # FIX: Se reemplaza el 'or' ambiguo por una validación explícita
    df_cab_clean = df_cab if df_cab is not None else pd.DataFrame()
    bip_df = calcular_bipartisan(df_cab_clean, df_det)

    if bip_df.empty:
        print("❌ No se pudo calcular bipartisan.")
        sys.exit(1)

    out = "bipartisan_diputados.csv"
    bip_df.to_csv(out, index=False)
    print(f"\n✅ Bipartisan calculado: {len(bip_df):,} diputados → '{out}'")
    
    if "bipartisan" in bip_df.columns:
        print(f"   Score promedio: {bip_df['bipartisan'].mean():.4f}")
    
    return bip_df


if __name__ == "__main__":
    main()
