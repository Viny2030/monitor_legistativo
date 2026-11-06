"""
actualizar_nomina_html.py
=========================
Varias páginas del dashboard (Nómina, Indicadores, Por Bloque y la nómina
de legisladores) no consultan la API: dibujan con un array DIPUTADOS
escrito dentro del HTML. Ese array y la leyenda "datos al ..." del
encabezado quedaron congelados el 27/03/2026 mientras data/diputados.json
se actualiza todos los días.

Este script reescribe, en cada página, el array DIPUTADOS y la fecha del
encabezado con lo que hay en data/diputados.json. Lo corre el workflow
diario después del pipeline.

  * Mantiene los campos que ya usa cada página (nombre, distrito, bloque,
    mandato y, donde existen, asistencia y genero).
  * Si el JSON parece incompleto (menos de MIN_DIPUTADOS o sin bloque o
    distrito), no toca nada: mejor una nómina vieja con su fecha real que
    una nómina rota.
  * En las páginas que ya leen la API (nomina_detalle_diputados.html) solo
    actualiza la fecha.

Uso:
    python scripts/actualizar_nomina_html.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(RAIZ, "data", "diputados.json")
DASHBOARD = os.path.join(RAIZ, "dashboard")
PAGINAS = [
    "indicadores_diputados.html",
    "indicadores2_diputados.html",
    "indicadores_bloques_diputados.html",
    "nomina_detalle_legisladores.html",
    "nomina_detalle_diputados.html",
]
MIN_DIPUTADOS = 200
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

_RE_ARRAY = re.compile(r"(const DIPUTADOS = \[\r?\n)(.*?)(\r?\n\];)", re.S)
_RE_FECHA = re.compile(r"datos al \d{1,2} de [a-záéíóú]+ de \d{4}")
_RE_CAMPO = re.compile(r"(\w+):")


def fecha_larga(iso: str) -> str:
    d = datetime.fromisoformat(iso[:19])
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _js(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def fila_js(d: dict, campos: list[str]) -> str:
    partes = []
    for c in campos:
        if c == "nombre":
            v = d.get("nombre")
        elif c == "distrito":
            v = d.get("distrito")
        elif c == "bloque":
            v = d.get("bloque")
        elif c == "mandato":
            v = d.get("mandato_hasta") or d.get("mandato")
        elif c == "genero":
            v = d.get("genero")
        elif c == "asistencia":
            v = d.get("asistencia_pct")
            v = round(float(v), 1) if v is not None else None
        else:
            v = d.get(c)
        if v is None or v == "":
            continue  # la página ya trata el campo ausente como "sin dato"
        partes.append(f"{c}:{_js(v)}")
    return "  {" + ",".join(partes) + "}"


def actualizar_pagina(html: str, diputados: list[dict], fecha: str) -> tuple[str, bool]:
    """Devuelve (html nuevo, si se reescribió el array)."""
    nuevo, reescrito = html, False
    m = _RE_ARRAY.search(html)
    if m:
        primera = next((l for l in m.group(2).splitlines() if "nombre" in l), "")
        campos = list(dict.fromkeys(_RE_CAMPO.findall(primera)))
        if "nombre" in campos and "bloque" in campos:
            nl = "\r\n" if "\r\n" in m.group(1) else "\n"
            cuerpo = ("," + nl).join(fila_js(d, campos) for d in diputados)
            nuevo = html[:m.start(2)] + cuerpo + html[m.end(2):]
            reescrito = True
    nuevo = _RE_FECHA.sub(f"datos al {fecha}", nuevo)
    return nuevo, reescrito


def main() -> int:
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)
    diputados = data.get("diputados", [])
    iso = (data.get("meta") or {}).get("ultima_actualizacion")
    completos = [d for d in diputados if d.get("nombre") and d.get("bloque") and d.get("distrito")]
    if len(completos) < MIN_DIPUTADOS or len(completos) != len(diputados) or not iso:
        print(f"⚠️ data/diputados.json incompleto ({len(completos)}/{len(diputados)} con nombre, "
              f"bloque y distrito; fecha={iso!r}): no se modifica el HTML")
        return 0
    fecha = fecha_larga(iso)
    for pagina in PAGINAS:
        ruta = os.path.join(DASHBOARD, pagina)
        if not os.path.exists(ruta):
            continue
        with open(ruta, encoding="utf-8", newline="") as f:
            html = f.read()
        nuevo, reescrito = actualizar_pagina(html, diputados, fecha)
        if nuevo != html:
            with open(ruta, "w", encoding="utf-8", newline="") as f:
                f.write(nuevo)
        print(f"{pagina}: {'nómina y fecha' if reescrito else 'fecha'} → {fecha}"
              + ("" if nuevo != html else " (sin cambios)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
