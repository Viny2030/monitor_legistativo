# api_no_usada — código archivado (2026-06-30)

Este directorio contiene `api/main.py` y `api/routes/*.py`, una **segunda
implementación de API FastAPI** que existía en paralelo a `api_server.py`
(que es la que efectivamente corre en producción, según `Dockerfile` /
`railway.toml`).

## Por qué se archivó

Tras auditar el repo se confirmó que:

- `api_server.py` (raíz del repo) es 100% autónomo y no importa nada de
  `api/`, `data_loader.py` ni `indicadores/calculos.py`. Es el único que
  se despliega (`CMD ["python", "api_server.py"]` en el `Dockerfile`).
- `api/main.py` **nunca se ejecuta** en producción ni en CI.
- `api/routes/*.py` (bloques.py, costos.py, diputados.py, modulo.py,
  ranking.py) definían cada uno un `APIRouter()`, pero **ninguno estaba
  montado** con `app.include_router(...)` — ni siquiera en `api/main.py`.
  Eran endpoints físicamente inalcanzables incluso corriendo localmente.
- Los 76 tests del repo importan exclusivamente de `api_server.py`
  (`from api_server import app`, `from api_server import _bloque_stats`).
  Ninguno depende de este código.
- `api/main.py` tenía además un endpoint `/diputados` que generaba datos
  **falsos** con `random.randint()` (asistencia, productividad,
  comisiones) y los etiquetaba como `"fuente": "csv_real"` — un riesgo
  si alguna vez se llegaba a montar sin revisar.

## Qué hacer con esto

Se conserva acá por las dudas (en vez de borrarlo directo) para poder
revisar si alguna idea de `api/routes/costos.py` (cruce presupuestario)
o `api/routes/ranking.py` (Score de Función Ejecutiva) vale la pena
portar a `api_server.py` más adelante.

Si después de un tiempo nadie lo necesitó, se puede borrar esta carpeta
entera sin riesgo — no la importa nada del sistema en producción.

`data_loader.py` e `indicadores/calculos.py` (raíz del repo) **no** se
archivaron junto con esto porque `scraper_hcdn.py` sí depende de
`data_loader.py` para otra cosa.