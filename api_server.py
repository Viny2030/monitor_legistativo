"""
api_server.py
=============
API REST minima para monitor_legistativo.
Sirve los datos generados por scraper_pipeline.py como endpoints JSON.
Pensado para deploy en Railway; el HTML del dashboard consume estos endpoints
en lugar de tener los datos hardcodeados.
Endpoints:
  GET /                        → health check + meta
  GET /dashboard               → dashboard principal (index.html)
  GET /api/diputados           → array completo de diputados
  GET /api/diputados/{nombre}  → diputado especifico
  GET /api/bloques             → resumen agregado por bloque
  GET /api/presupuesto         → datos de ejecucion presupuestaria
  GET /api/kpis                → KPIs globales del dashboard
  POST /api/refresh            → dispara el pipeline (protegido por REFRESH_TOKEN)
Uso local:
    pip install fastapi uvicorn
    python api_server.py
    # abre http://localhost:8000/docs

Variables de entorno:
    REFRESH_TOKEN   → token para el endpoint /api/refresh (default: "dev")
    PORT            → puerto (default: 8000)
    DATA_FILE       → ruta al JSON generado (default: data/diputados.json)
"""
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_FILE = os.getenv("DATA_FILE", "data/diputados.json")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN", "dev")
PORT = int(os.getenv("PORT", 8000))

app = FastAPI(
    title="Monitor Legislativo Diputados — API",
    description="Datos actualizados automaticamente del monitoreo legislativo de la HCDN",
    version="1.0.0"
)

# CORS abierto para que el HTML pueda consumir desde cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"]
)

# Servir archivos HTML del dashboard (aiofiles requerido por StaticFiles)
_DASHBOARD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard")
try:
    if os.path.isdir(_DASHBOARD_DIR):
        app.mount("/dashboard", StaticFiles(directory=_DASHBOARD_DIR, html=True), name="dashboard")
        print(f"[INFO] Dashboard montado en /dashboard")
    else:
        print(f"[WARN] dashboard/ no encontrado — /dashboard no disponible")
except Exception as e:
    print(f"[WARN] No se pudo montar /dashboard (aiofiles ausente?): {e}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        raise HTTPException(
            status_code=503,
            detail="Datos no disponibles. Correr scraper_pipeline.py primero."
        )
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _bloque_stats(diputados):
    """Agrega estadisticas por bloque."""
    bloques = defaultdict(lambda: {
        "cantidad": 0,
        "mujeres": 0,
        "asistencia_pct_sum": 0,
        "asistencia_count": 0,
        "proyectos_presentados": 0,
        "proyectos_aprobados": 0,
        "iqp_sum": 0,
        "iqp_count": 0,
        "distritos": set()
    })

    for d in diputados:
        b = d.get("bloque", "Sin bloque") or "Sin bloque"
        bloques[b]["cantidad"] += 1
        if d.get("genero") == "F":
            bloques[b]["mujeres"] += 1
        if d.get("asistencia_pct") is not None:
            bloques[b]["asistencia_pct_sum"] += d["asistencia_pct"]
            bloques[b]["asistencia_count"] += 1
        bloques[b]["proyectos_presentados"] += d.get("proyectos_presentados") or 0
        bloques[b]["proyectos_aprobados"] += d.get("proyectos_aprobados") or 0
        if d.get("iqp") is not None:
            bloques[b]["iqp_sum"] += d["iqp"]
            bloques[b]["iqp_count"] += 1
        if d.get("distrito"):
            bloques[b]["distritos"].add(d["distrito"])

    result = []
    for nombre, s in sorted(bloques.items(), key=lambda x: -x[1]["cantidad"]):
        n = s["cantidad"]
        result.append({
            "bloque": nombre,
            "cantidad": n,
            "mujeres": s["mujeres"],
            "hombres": n - s["mujeres"],
            "pct_mujeres": round(s["mujeres"] / n * 100, 1) if n else 0,
            "asistencia_pct": round(s["asistencia_pct_sum"] / s["asistencia_count"], 1)
            if s["asistencia_count"] else None,
            "nape": round(1 - s["asistencia_pct_sum"] / s["asistencia_count"] / 100, 4)
            if s["asistencia_count"] else None,
            "proyectos_presentados": s["proyectos_presentados"],
            "proyectos_aprobados": s["proyectos_aprobados"],
            "tasa_aprobacion": round(s["proyectos_aprobados"] / s["proyectos_presentados"] * 100, 1)
            if s["proyectos_presentados"] else None,
            "iqp_promedio": round(s["iqp_sum"] / s["iqp_count"], 4)
            if s["iqp_count"] else None,
            "distritos": sorted(s["distritos"])
        })
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return RedirectResponse(url="/dashboard/")


@app.get("/health")
def health():
    try:
        data = load_data()
        meta = data.get("meta", {})
    except HTTPException:
        meta = {}
    return {
        "status": "ok",
        "servicio": "Monitor Legislativo Diputados",
        "ultima_actualizacion": meta.get("ultima_actualizacion"),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/diputados")
def get_diputados(bloque: str = None, distrito: str = None, genero: str = None):
    """
    Retorna array de diputados.
    Filtros opcionales por query param: bloque, distrito, genero (M/F/ND)
    """
    data = load_data()
    diputados = data.get("diputados", [])

    if bloque:
        diputados = [d for d in diputados if (d.get("bloque") or "").lower() == bloque.lower()]
    if distrito:
        diputados = [d for d in diputados if (d.get("distrito") or "").lower() == distrito.lower()]
    if genero:
        diputados = [d for d in diputados if (d.get("genero") or "").upper() == genero.upper()]

    return {
        "total": len(diputados),
        "diputados": diputados,
        "meta": data.get("meta", {})
    }


@app.get("/api/diputados/{nombre_busqueda}")
def get_diputado(nombre_busqueda: str):
    """Busca un diputado por apellido (busqueda parcial, case-insensitive)."""
    data = load_data()
    q = nombre_busqueda.upper()
    resultados = [d for d in data.get("diputados", []) if q in d.get("nombre", "").upper()]

    if not resultados:
        raise HTTPException(status_code=404, detail=f"No se encontro diputado: {nombre_busqueda}")

    return {"resultados": resultados}


@app.get("/api/bloques")
def get_bloques():
    """Estadisticas agregadas por bloque parlamentario."""
    data = load_data()
    bloques = _bloque_stats(data.get("diputados", []))

    return {
        "total_bloques": len(bloques),
        "bloques": bloques,
        "meta": data.get("meta", {})
    }


@app.get("/api/presupuesto")
def get_presupuesto():
    """Datos de ejecucion presupuestaria del Poder Legislativo."""
    data = load_data()
    presupuesto = data.get("presupuesto", {})

    if not presupuesto:
        raise HTTPException(status_code=404, detail="Datos de presupuesto no disponibles todavia")

    return presupuesto


@app.get("/api/kpis")
def get_kpis():
    """
    KPIs globales para el dashboard:
      - NAPE global (% inasistencia promedio)
      - TPMP (tasa proyectos media por diputado)
      - COLS (coeficiente de legisferacion activa)
      - IAP (indice de aprobacion presupuestaria)
      - RLS (ratio legisladores/100k hab)
      - Paridad de genero
    """
    data = load_data()
    diputados = data.get("diputados", [])
    n = len(diputados)

    if n == 0:
        raise HTTPException(status_code=503, detail="Sin datos de diputados")

    # NAPE
    asistencias = [d["asistencia_pct"] for d in diputados if d.get("asistencia_pct") is not None]
    nape = round(1 - sum(asistencias) / len(asistencias) / 100, 4) if asistencias else None

    # TPMP (proyectos presentados promedio)
    proyectos = [d["proyectos_presentados"] for d in diputados if d.get("proyectos_presentados") is not None]
    tpmp = round(sum(proyectos) / len(proyectos), 2) if proyectos else None

    # COLS (% con al menos 1 proyecto aprobado)
    con_aprobado = sum(1 for d in diputados if (d.get("proyectos_aprobados") or 0) > 0)
    cols = round(con_aprobado / n * 100, 1) if n else None

    # IAP
    presupuesto = data.get("presupuesto", {})
    iap = presupuesto.get("iap")

    # Paridad
    mujeres = sum(1 for d in diputados if d.get("genero") == "F")
    pct_mujeres = round(mujeres / n * 100, 1)

    # IQP promedio
    iqps = [d["iqp"] for d in diputados if d.get("iqp") is not None]
    iqp_global = round(sum(iqps) / len(iqps), 4) if iqps else None

    # RLS: Argentina ~46.6M hab, 257 diputados activos
    rls = round(n / 46.6, 2)

    return {
        "total_diputados": n,
        "nape": nape,
        "tpmp": tpmp,
        "cols": cols,
        "iap": iap,
        "iqp_global": iqp_global,
        "rls": rls,
        "paridad": {
            "mujeres": mujeres,
            "hombres": n - mujeres,
            "pct_mujeres": pct_mujeres
        },
        "meta": data.get("meta", {})
    }


# ---------------------------------------------------------------------------
# Endpoints v1.1 — Indicadores SIL y Comisiones
# ---------------------------------------------------------------------------

@app.get("/api/indicadores")
def get_indicadores():
    """[v1.1] Devuelve todos los indicadores calculados."""
    data = load_data()
    diputados = data.get("diputados", [])
    n = len(diputados)
    asistencias = [d["asistencia_pct"] for d in diputados if d.get("asistencia_pct") is not None]
    nape_valor = round(1 - sum(asistencias) / len(asistencias) / 100, 4) if asistencias else None
    cols_n = sum(1 for d in diputados if (d.get("proyectos_aprobados") or 0) > 0)
    tpmp_data = data.get("tpmp", {})
    itc_data = data.get("itc", {})
    presupuesto = data.get("presupuesto", {})
    indicadores = [
        {"id": "NAPE", "nombre": "Nivel de Asistencia y Permanencia Efectiva",
         "valor": nape_valor, "unidad": "ratio (0-1)",
         "fuente": "Direccion Lab. Parlamentaria / votaciones HCDN",
         "diputados_con_dato": len(asistencias), "version": "1.0"},
        {"id": "TPMP", "nombre": "Tiempo Promedio de Maduracion de Proyectos",
         "valor": tpmp_data.get("valor", 105.0), "unidad": "dias",
         "fuente": tpmp_data.get("fuente", "estimacion"),
         "n_proyectos": tpmp_data.get("n_proyectos", 0),
         "mediana_dias": tpmp_data.get("mediana_dias"),
         "advertencia": tpmp_data.get("advertencia"), "version": "1.1"},
        {"id": "ITC", "nombre": "Indice de Trabajo en Comisiones",
         "valor": itc_data.get("valor", 3.5), "unidad": "ratio",
         "fuente": itc_data.get("fuente", "estimacion historica"),
         "horas_comision": itc_data.get("horas_comision"),
         "horas_pleno": itc_data.get("horas_pleno"),
         "n_reuniones": itc_data.get("n_reuniones"),
         "advertencia": itc_data.get("advertencia"), "version": "1.1"},
        {"id": "COLS", "nombre": "Coeficiente de Legislacion Sustantiva",
         "valor": round(cols_n / n * 100, 1) if n else None,
         "unidad": "% diputados con 1+ ley aprobada", "fuente": "CKAN HCDN / SIL", "version": "1.0"},
        {"id": "IAP", "nombre": "Indice de Autonomia Presupuestaria",
         "valor": presupuesto.get("iap"), "unidad": "ratio (0-1)",
         "fuente": presupuesto.get("fuente", "ONP / Presupuesto Abierto"), "version": "1.0"},
    ]
    return {"version_api": "1.1", "total": len(indicadores), "indicadores": indicadores,
            "meta": data.get("meta", {})}


@app.get("/api/indicadores/tpmp")
def get_tpmp():
    """[v1.1] TPMP — Tiempo Promedio de Maduracion de Proyectos."""
    data = load_data()
    tpmp_data = data.get("tpmp")
    if tpmp_data:
        return {"ok": True, "indicador": {"id": "TPMP", **tpmp_data}}
    try:
        from scrapers.sil import calcular_tpmp
        resultado = calcular_tpmp()
        return {"ok": True, "calculado_en_tiempo_real": True, "indicador": {"id": "TPMP", **resultado}}
    except Exception as e:
        return {"ok": False, "indicador": {"id": "TPMP", "valor": 105.0, "unidad": "dias",
                                           "fuente": "estimacion de referencia",
                                           "advertencia": f"SIL no disponible: {str(e)[:100]}"}}


@app.get("/api/indicadores/itc")
def get_itc():
    """[v1.1] ITC — Indice de Trabajo en Comisiones."""
    data = load_data()
    itc_data = data.get("itc")
    if itc_data:
        return {"ok": True, "indicador": itc_data}
    try:
        from scrapers.comisiones import calcular_itc
        resultado = calcular_itc(max_comisiones=15)
        return {"ok": True, "calculado_en_tiempo_real": True, "indicador": resultado}
    except Exception as e:
        return {"ok": False, "indicador": {"id": "ITC", "valor": 3.5, "unidad": "ratio",
                                           "fuente": "estimacion historica",
                                           "advertencia": f"Actas no disponibles: {str(e)[:100]}"}}


@app.get("/api/diputados/{nombre_busqueda}/asistencia")
def get_asistencia_diputado(nombre_busqueda: str):
    """[v1.1] Asistencia individual por diputado."""
    data = load_data()
    q = nombre_busqueda.upper()
    resultados = [d for d in data.get("diputados", []) if q in d.get("nombre", "").upper()]
    if not resultados:
        raise HTTPException(status_code=404, detail=f"Diputado no encontrado: {nombre_busqueda}")
    salida = []
    for d in resultados:
        asistencia_pct = d.get("asistencia_pct")
        iqp = d.get("iqp")
        nape = d.get("nape")
        if nape is None and asistencia_pct is not None:
            nape = round(1 - asistencia_pct / 100, 4)
        salida.append({"nombre": d["nombre"], "distrito": d.get("distrito"),
                       "bloque": d.get("bloque"), "asistencia_pct": asistencia_pct,
                       "nape": nape, "iqp": iqp, "version": "1.1"})
    return {"ok": True, "resultados": len(salida), "diputados": salida, "meta": data.get("meta", {})}


@app.get("/api/diputados/{nombre_busqueda}/proyectos")
def get_proyectos_diputado(nombre_busqueda: str):
    """[v1.1] Proyectos por diputado."""
    data = load_data()
    q = nombre_busqueda.upper()
    resultados = [d for d in data.get("diputados", []) if q in d.get("nombre", "").upper()]
    if not resultados:
        raise HTTPException(status_code=404, detail=f"Diputado no encontrado: {nombre_busqueda}")
    salida = []
    for d in resultados:
        presentados = d.get("proyectos_presentados") or d.get("sil_presentados")
        aprobados = d.get("proyectos_aprobados") or d.get("sil_con_dictamen")
        tasa = round(aprobados / presentados * 100, 1) if (
                    presentados and aprobados is not None and presentados > 0) else None
        salida.append({"nombre": d["nombre"], "distrito": d.get("distrito"),
                       "bloque": d.get("bloque"), "proyectos_presentados": presentados,
                       "proyectos_aprobados": aprobados, "tasa_aprobacion_pct": tasa,
                       "fuente": "CKAN HCDN + SIL", "version": "1.1"})
    return {"ok": True, "resultados": len(salida), "diputados": salida, "meta": data.get("meta", {})}


@app.post("/api/refresh")
def refresh_data(x_refresh_token: str = Header(None)):
    """
    Dispara el pipeline de scraping.
    Requiere header: X-Refresh-Token: <REFRESH_TOKEN>
    """
    if x_refresh_token != REFRESH_TOKEN:
        raise HTTPException(status_code=401, detail="Token invalido")

    try:
        result = subprocess.run(
            [sys.executable, "scraper_pipeline.py"],
            capture_output=True, text=True, timeout=300
        )
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "stdout": result.stdout[-3000:],
            "stderr": result.stderr[-1000:],
            "timestamp": datetime.now().isoformat()
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Pipeline timeout (>5min)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=PORT, reload=False)
