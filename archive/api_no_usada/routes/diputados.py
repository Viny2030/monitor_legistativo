"""
api/routes/diputados.py
Endpoint: lista completa de diputados con datos base
Compatible con CSV extendido (obtener_datos.py real)
"""
from fastapi import APIRouter, Query
import pandas as pd
import os

router = APIRouter()

CSV_PATH = os.path.join(os.getcwd(), "nomina_diputados.csv")


def _load_df() -> pd.DataFrame:
    for path in [CSV_PATH, "nomina_diputados.csv"]:
        if os.path.exists(path):
            return pd.read_csv(path)
    return pd.DataFrame(columns=["Nombre", "Distrito", "Bloque"])


@router.get("/")
def listar_diputados(
    bloque: str    = Query(None, description="Filtrar por bloque"),
    provincia: str = Query(None, description="Filtrar por distrito/provincia"),
    limit: int     = Query(257, le=257),
):
    df = _load_df()
    if bloque:
        df = df[df["Bloque"].str.contains(bloque, case=False, na=False)]
    if provincia:
        df = df[df["Distrito"].str.contains(provincia, case=False, na=False)]
    return {"total": len(df), "diputados": df.head(limit).to_dict(orient="records")}


@router.get("/bloques")
def lista_bloques():
    df = _load_df()
    return {"bloques": sorted(df["Bloque"].dropna().unique().tolist())}


@router.get("/provincias")
def lista_provincias():
    df = _load_df()
    return {"provincias": sorted(df["Distrito"].dropna().unique().tolist())}


@router.get("/{nombre}")
def detalle_diputado(nombre: str):
    df = _load_df()
    match = df[df["Nombre"].str.contains(nombre, case=False, na=False)]
    if match.empty:
        return {"error": "Diputado no encontrado"}
    return match.to_dict(orient="records")
