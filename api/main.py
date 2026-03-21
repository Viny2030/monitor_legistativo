"""
api/main.py – Monitor Legislativo Argentina
============================================
FastAPI: endpoints para servir los 12 indicadores en JSON.

Instalación:
    pip install fastapi uvicorn

Correr:
    uvicorn api.main:app --reload --port 8000

Endpoints:
    GET /                    → info del monitor
    GET /indicadores         → los 12 indicadores calculados (JSON)
    GET /indicadores/{id}    → un indicador por ID (ej: /indicadores/CPR)
    GET /salud               → health check
"""

from __future__ import annotations
import sys
from pathlib import Path

# Permite importar desde el root del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from data_loader import construir_datos
from indicadores.calculos import calcular_todos

app = FastAPI(
    title="Monitor Legislativo Argentina",
    description="API de 12 indicadores de eficiencia y transparencia del Congreso Nacional",
    version="1.0.0",
)

# CORS abierto para que el dashboard HTML pueda consumirlo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _calcular(usar_scraper: bool = False) -> list[dict]:
    """Ejecuta el pipeline completo: datos → cálculos."""
    datos = construir_datos(usar_scraper_hcdn=usar_scraper)
    return calcular_todos(datos)


@app.get("/")
def raiz():
    return {
        "proyecto": "Monitor de Eficiencia Legislativa – República Argentina",
        "version": "1.0.0",
        "dimensiones": 4,
        "indicadores": 12,
        "endpoints": {
            "todos_los_indicadores": "/indicadores",
            "indicador_por_id":      "/indicadores/{id}",
            "salud":                 "/salud",
            "docs":                  "/docs",
        },
    }


@app.get("/salud")
def salud():
    return {"status": "ok"}


@app.get("/indicadores")
def get_indicadores(scraper: bool = False):
    """
    Devuelve los 12 indicadores calculados con datos reales (o fallback).

    Parámetros:
      scraper=true  → activa scraping en tiempo real de HCDN (más lento, más actual)
      scraper=false → usa CSVs descargados + MANUAL_OVERRIDES (default, rápido)
    """
    try:
        resultados = _calcular(usar_scraper=scraper)
        return JSONResponse(content={
            "ok": True,
            "total": len(resultados),
            "indicadores": resultados,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/indicadores/{indicador_id}")
def get_indicador(indicador_id: str, scraper: bool = False):
    """
    Devuelve un indicador específico por su ID (CPR, TPS, CAF, etc.).
    IDs válidos: CPR, TPS, CAF, TMM, ITT, IQP, CUN, CLS, TEF, CAD, EVD, TCI
    """
    indicador_id = indicador_id.upper()
    ids_validos = {"CPR", "TPS", "CAF", "TMM", "ITT", "IQP",
                   "CUN", "CLS", "TEF", "CAD", "EVD", "TCI"}

    if indicador_id not in ids_validos:
        raise HTTPException(
            status_code=404,
            detail=f"ID '{indicador_id}' no encontrado. IDs válidos: {sorted(ids_validos)}"
        )

    try:
        resultados = _calcular(usar_scraper=scraper)
        for r in resultados:
            if r["id"] == indicador_id:
                return JSONResponse(content={"ok": True, "indicador": r})
        raise HTTPException(status_code=404, detail=f"No se calculó el indicador {indicador_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)"""
api/main.py – Monitor Legislativo Argentina
============================================
FastAPI: endpoints para servir los 12 indicadores en JSON.

Instalación:
    pip install fastapi uvicorn

Correr:
    uvicorn api.main:app --reload --port 8000

Endpoints:
    GET /                    → info del monitor
    GET /indicadores         → los 12 indicadores calculados (JSON)
    GET /indicadores/{id}    → un indicador por ID (ej: /indicadores/CPR)
    GET /salud               → health check
"""

from __future__ import annotations
import sys
from pathlib import Path

# Permite importar desde el root del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from data_loader import construir_datos
from indicadores.calculos import calcular_todos

app = FastAPI(
    title="Monitor Legislativo Argentina",
    description="API de 12 indicadores de eficiencia y transparencia del Congreso Nacional",
    version="1.0.0",
)

# CORS abierto para que el dashboard HTML pueda consumirlo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _calcular(usar_scraper: bool = False) -> list[dict]:
    """Ejecuta el pipeline completo: datos → cálculos."""
    datos = construir_datos(usar_scraper_hcdn=usar_scraper)
    return calcular_todos(datos)


@app.get("/")
def raiz():
    return {
        "proyecto": "Monitor de Eficiencia Legislativa – República Argentina",
        "version": "1.0.0",
        "dimensiones": 4,
        "indicadores": 12,
        "endpoints": {
            "todos_los_indicadores": "/indicadores",
            "indicador_por_id":      "/indicadores/{id}",
            "salud":                 "/salud",
            "docs":                  "/docs",
        },
    }


@app.get("/salud")
def salud():
    return {"status": "ok"}


@app.get("/indicadores")
def get_indicadores(scraper: bool = False):
    """
    Devuelve los 12 indicadores calculados con datos reales (o fallback).

    Parámetros:
      scraper=true  → activa scraping en tiempo real de HCDN (más lento, más actual)
      scraper=false → usa CSVs descargados + MANUAL_OVERRIDES (default, rápido)
    """
    try:
        resultados = _calcular(usar_scraper=scraper)
        return JSONResponse(content={
            "ok": True,
            "total": len(resultados),
            "indicadores": resultados,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/indicadores/{indicador_id}")
def get_indicador(indicador_id: str, scraper: bool = False):
    """
    Devuelve un indicador específico por su ID (CPR, TPS, CAF, etc.).
    IDs válidos: CPR, TPS, CAF, TMM, ITT, IQP, CUN, CLS, TEF, CAD, EVD, TCI
    """
    indicador_id = indicador_id.upper()
    ids_validos = {"CPR", "TPS", "CAF", "TMM", "ITT", "IQP",
                   "CUN", "CLS", "TEF", "CAD", "EVD", "TCI"}

    if indicador_id not in ids_validos:
        raise HTTPException(
            status_code=404,
            detail=f"ID '{indicador_id}' no encontrado. IDs válidos: {sorted(ids_validos)}"
        )

    try:
        resultados = _calcular(usar_scraper=scraper)
        for r in resultados:
            if r["id"] == indicador_id:
                return JSONResponse(content={"ok": True, "indicador": r})
        raise HTTPException(status_code=404, detail=f"No se calculó el indicador {indicador_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)