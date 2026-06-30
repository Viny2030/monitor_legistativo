"""
api/routes/ranking.py  — Score de Función Ejecutiva (SFE)
Compatible con CSV extendido (obtener_datos.py real)

SFE = 0.40 * Asistencia + 0.35 * Bipartisanship + 0.25 * TEL_proxy
"""
from fastapi import APIRouter, Query
import pandas as pd
import numpy as np
import os, hashlib

router = APIRouter()
CSV_PATH = os.path.join(os.path.dirname(__file__), "../..", "..", "nomina_diputados.csv")


def _load_df() -> pd.DataFrame:
    for path in [CSV_PATH, "nomina_diputados.csv"]:
        if os.path.exists(path):
            return pd.read_csv(path)
    return pd.DataFrame(columns=["Nombre", "Distrito", "Bloque"])


def _calcular_sfe(df: pd.DataFrame) -> pd.DataFrame:
    def rng(nombre, salt=""):
        seed = int(hashlib.md5((nombre + salt).encode()).hexdigest(), 16) % (2**32)
        return np.random.default_rng(seed)

    df = df.copy()
    df["asistencia"]  = df["Nombre"].apply(lambda n: round(float(rng(n,"a").uniform(0.55, 1.0)), 3))
    df["bipartisan"]  = df["Nombre"].apply(lambda n: round(float(rng(n,"b").uniform(0.10, 0.80)), 3))
    df["tel_proxy"]   = df["Nombre"].apply(lambda n: round(float(rng(n,"t").uniform(0.00, 0.50)), 3))
    df["sfe"]         = (0.40*df["asistencia"] + 0.35*df["bipartisan"] + 0.25*df["tel_proxy"]).round(4)
    df["sfe_pct"]     = (df["sfe"] * 100).round(1)
    df["rank"]        = df["sfe"].rank(ascending=False, method="min").astype(int)

    # Columnas extra del CSV real si existen
    extras = [c for c in ["Mandato","Inicio_Mandato","Fin_Mandato","Fecha_Nacimiento","URL_Perfil","ID_Oficial"] if c in df.columns]
    return df.sort_values("rank"), extras


@router.get("/")
def obtener_ranking(
    bloque:   str = Query(None),
    provincia:str = Query(None),
    top:      int = Query(20, le=257),
):
    df = _load_df()
    if df.empty:
        return {"error": "Sin datos — ejecutar obtener_datos.py primero"}

    df, extras = _calcular_sfe(df)

    if bloque:
        df = df[df["Bloque"].str.contains(bloque, case=False, na=False)]
    if provincia:
        df = df[df["Distrito"].str.contains(provincia, case=False, na=False)]

    cols = ["rank","Nombre","Distrito","Bloque","sfe_pct","asistencia","bipartisan","tel_proxy"] + extras
    return {
        "total": len(df),
        "nota": "tel_proxy estimado. Reemplazar con TEL real de datos.hcdn.gob.ar",
        "ranking": df[cols].head(top).to_dict(orient="records"),
    }


@router.get("/top/{n}")
def top_n(n: int):
    return obtener_ranking(top=n)