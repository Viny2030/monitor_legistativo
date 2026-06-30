"""
api/routes/bloques.py
Estadísticas agregadas por bloque parlamentario
"""
from fastapi import APIRouter
import pandas as pd
import numpy as np
import os, hashlib

router = APIRouter()

CSV_PATH = os.path.join(os.path.dirname(__file__), "../..", "..", "nomina_diputados.csv")


def _load_df():
    if os.path.exists(CSV_PATH):
        return pd.read_csv(CSV_PATH)
    if os.path.exists("nomina_diputados.csv"):
        return pd.read_csv("nomina_diputados.csv")
    return pd.DataFrame(columns=["Nombre", "Distrito", "Bloque"])


def _seed_score(nombre, lo, hi):
    seed = int(hashlib.md5(nombre.encode()).hexdigest(), 16) % (2**32)
    return float(np.random.default_rng(seed).uniform(lo, hi))


@router.get("/")
def estadisticas_bloques():
    df = _load_df()
    if df.empty:
        return {"error": "Sin datos"}

    df["sfe"] = df["Nombre"].apply(lambda n: round(
        0.40 * _seed_score(n, 0.55, 1.0) +
        0.35 * _seed_score(n, 0.1, 0.8) +
        0.25 * _seed_score(n, 0.0, 0.5), 4
    ))

    resumen = (
        df.groupby("Bloque")
        .agg(
            diputados=("Nombre", "count"),
            sfe_promedio=("sfe", "mean"),
            sfe_max=("sfe", "max"),
            sfe_min=("sfe", "min"),
        )
        .reset_index()
    )
    resumen["sfe_promedio"] = resumen["sfe_promedio"].round(4)
    resumen["sfe_pct"] = (resumen["sfe_promedio"] * 100).round(1)
    resumen = resumen.sort_values("sfe_promedio", ascending=False)

    return {
        "total_bloques": len(resumen),
        "bloques": resumen.to_dict(orient="records"),
    }


@router.get("/lista")
def lista_bloques():
    df = _load_df()
    if df.empty:
        return {"bloques": []}
    return {"bloques": sorted(df["Bloque"].dropna().unique().tolist())}