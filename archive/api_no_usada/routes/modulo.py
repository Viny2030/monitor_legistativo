"""
api/routes/modulo.py
Endpoint para consultar y actualizar el valor del módulo legislativo.

Integra monitorear_modulo() del pipeline principal.
Si detecta nuevo valor → actualiza VALOR_MODULO en memoria (y sugiere
actualizar personal.py / la variable de entorno VALOR_MODULO).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import re

router = APIRouter()

# Valor en memoria — se actualiza cuando el monitor detecta cambio
_modulo_cache = {"valor": 215_000, "fuente": "manual", "ultima_actualizacion": "2025-01"}


class ModuloUpdate(BaseModel):
    valor: int
    fuente: str = "manual"


@router.get("/")
def get_modulo():
    return _modulo_cache


@router.post("/actualizar")
def actualizar_modulo(body: ModuloUpdate):
    _modulo_cache["valor"] = body.valor
    _modulo_cache["fuente"] = body.fuente
    return {"ok": True, "nuevo_valor": body.valor}


@router.get("/monitorear")
def monitorear_modulo():
    """
    Intenta obtener el valor del módulo desde el sitio de HCDN.
    Si detecta un valor diferente al almacenado, lo actualiza en memoria.
    """
    url = "https://www.hcdn.gob.ar/institucional/modulo/"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        texto = soup.get_text()

        # Buscar patrón numérico tipo $ 215.000 o 215000
        matches = re.findall(r"\$\s*([\d\.]+)", texto)
        if matches:
            valor_str = matches[0].replace(".", "").replace(",", "")
            valor_nuevo = int(valor_str)

            if valor_nuevo != _modulo_cache["valor"]:
                _modulo_cache["valor"] = valor_nuevo
                _modulo_cache["fuente"] = "hcdn_scraper"
                return {
                    "cambio_detectado": True,
                    "nuevo_valor": valor_nuevo,
                    "mensaje": "Actualizar VALOR_MODULO en api/routes/costos.py y personal.py",
                }
            return {"cambio_detectado": False, "valor_actual": _modulo_cache["valor"]}

        return {"cambio_detectado": False, "nota": "No se encontró valor en la página"}

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al consultar HCDN: {e}")