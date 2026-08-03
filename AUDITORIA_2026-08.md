# Auditoría Monitor Legislativo — agosto 2026

Repo: `monitor_legistativo` (Cámara de Diputados Argentina). Revisión completa +
cambios aplicados directamente donde fue seguro, más una lista de acciones
manuales pendientes (no tuve acceso a shell/git en esta sesión — ver nota al final).

## 1. Resumen ejecutivo

El proyecto es real y funcional: scrapers de HCDN/SIL, indicadores de eficiencia
legislativa, API FastAPI, dashboards HTML y CI/CD en GitHub Actions. El código
central (`api_server.py`, `scrapers/`, `core/`, `indicadores/`, `dashboard/`)
está en buen estado. El problema principal es acumulación de código legacy sin
limpiar: dos entornos virtuales, scripts duplicados en la raíz, un bug real en
un script de presupuesto, y un archivo (`index.html` en la raíz) que no
pertenece a este proyecto.

No encontré datos falsos ocultos en el dashboard en vivo. Sí encontré valores
de referencia/estimados — algunos correctamente marcados con `advertencia` en
la API, y uno (`data_loader.py`) con placeholders sin marcar, pero ese archivo
no está conectado al sistema en producción (ver sección 3).

## 2. Cambios aplicados ya en esta sesión

| Archivo | Cambio |
|---|---|
| `scripts/cruzar_presupuesto.py` | Eliminada una línea muerta (`PCT_DIPUTADOS = 0.45  # ← esta línea NO existe todavía, hay que agregarla`) — era un comentario-instrucción que quedó ejecutándose como código, sin uso real en el resto de la función. |
| `pipeline.py` (raíz) | Era una copia desactualizada de `scripts/cruzar_presupuesto.py` con un bug real: `main()` hacía `tc, tc_info = obtener_tipo_cambio()` pero esa función devuelve un solo `float`, no una tupla → `python pipeline.py` tiraba `TypeError` siempre. No estaba importado desde ningún otro lugar del repo. Lo convertí en un shim que delega en la versión real y mantenida, para que si alguien lo sigue corriendo por costumbre, funcione en vez de romper. |
| `agentic_ai.py` | Agregadas `detectar_anomalias()` y `resumen_diario()` — agente autónomo de detección de anomalías (ver sección 5). |
| `api_server.py` | Nuevos endpoints `GET /api/ia/anomalias` y `GET /api/ia/resumen`. |
| `scripts/agente_monitor.py` (nuevo) | Script standalone para correr el agente de forma autónoma (cron/CI), compara contra la corrida anterior y guarda `data/alertas_agente.json`. |
| `.github/workflows/monitor_diario.yml` | Agregado el paso del agente después del scraping diario, con alerta por email automática si detecta severidad alta. |

## 3. Datos no reales / estimaciones — detalle

Encontré tres focos distintos, con distinto nivel de riesgo real:

**a) `/api/indicadores` (TPMP, ITC) — riesgo bajo.** Cuando no hay dato en vivo
usan un valor de referencia (`105.0` días, `3.5`) con un campo `advertencia`
explícito que dice que es una estimación. El frontend puede (y debería) mostrar
esa advertencia. Esto es honesto, no lo tocaría — a lo sumo, verificar que el
dashboard efectivamente pinta la advertencia y no solo el número.

**b) `data_loader.py` (raíz) — placeholders sin marcar, pero código muerto.**
Tiene un diccionario `MANUAL_OVERRIDES` con números fijos (`presupuesto_total:
185_000_000_000`, `planta_permanente: 3_800`, etc.) con el comentario
"Completá estos con los datos reales cuando los tengas". A diferencia del caso
(a), estos no se marcan como estimación en ningún lado. La buena noticia:
confirmé por grep que **nada en el sistema en producción importa
`data_loader.py`** (ni `api_server.py` ni `agentic_ai.py` ni los `scrapers/`)
— es un script huérfano de una versión anterior del proyecto (mismo patrón que
`api_diputados.py`, que tampoco se importa desde ningún lado). No está
mintiéndole a nadie hoy, pero conviene archivarlo junto con `archive/api_no_usada/`
para que no quede la duda, o borrarlo si ya no aporta como referencia.

**c) `tests/conftest.py` — datos ficticios, y está bien que lo sean.** Los
fixtures usan diputados inventados (`GARCIA JUAN`, `LOPEZ MARIA`, etc.) para no
depender de red en los tests. Es la práctica correcta, no es un hallazgo.

**Conclusión:** el dashboard que ve el público (`dashboard/*.html` vía
`data/diputados.json`) usa datos reales scrapeados, con las estimaciones
parciales correctamente señalizadas. El riesgo de "datos sintéticos ocultos"
está en código legacy desconectado, no en el pipeline activo.

## 4. Limpieza pendiente — acciones manuales

No tengo acceso a shell en esta sesión (el sandbox reportó "Not enough disk
space to set up the workspace" — es de mi entorno, no del repo) así que no
pude borrar ni mover archivos directamente. Esto es lo que recomiendo correr
localmente:

```powershell
# 1. Dos entornos virtuales duplicados. venv/ tiene requests/pandas/bs4 pero
#    NO fastapi/pydantic/anthropic. .venv/ tiene fastapi/pydantic/requests/
#    pandas/bs4/lxml pero NO anthropic. Ninguno de los dos alcanza para correr
#    todo el proyecto solo. Recomiendo quedarte con .venv (es el más completo
#    y reciente) y borrar venv/:
Remove-Item -Recurse -Force venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements_api.txt   # completa lo que falta (anthropic, aiofiles)

# 2. railway.yml quedó duplicado con railway.toml (el commit "renombrar
#    railway.yml a railway.toml" no borró el .yml viejo):
Remove-Item railway.yml

# 3. Dos configs de pytest — pytest.ini es el que usa CI (tests_diarios.yml no
#    referencia pytest_diputados.ini en ningún lado):
Remove-Item pytest_diputados.ini

# 4. index.html en la raíz no es de este proyecto — es un formulario de
#    pedidos de "Viny 2030" (otro proyecto tuyo). No lo sirve api_server.py
#    (que solo monta /dashboard), pero confunde a cualquiera que abra el repo:
Remove-Item index.html
# (o moverlo al repo que corresponda si lo necesitás)

# 5. frontend/index.html es un dashboard prototipo anterior (branding
#    "MEL-TP", Chart.js) superado por dashboard/index.html. No está montado
#    por la API. Si no lo necesitás como referencia:
Remove-Item -Recurse frontend

# 6. __pycache__ versionados (no deberían estar en git aunque .gitignore ya
#    los ignore hacia adelante — hay que sacarlos del índice una vez):
git rm -r --cached '**/__pycache__' 2>$null
git commit -m "chore: limpiar __pycache__ del índice, venv duplicado, archivos sueltos"
```

**Candidatos a revisar (no los toqué, decisión tuya):**
- `data_loader.py`, `api_diputados.py` (raíz) — huérfanos, no importados por nada activo. Candidatos a mover a `archive/` junto con `archive/api_no_usada/`.
- `obtener_datos.py` — el propio workflow dice que "viene fallando desde hace meses" (`diputados.gov.ar` cambió o bloquea el request). Vale la pena investigar aparte o directamente sacarlo del workflow si `scraper_pipeline.py` ya cubre esa nómina.

## 5. Dependencias

`requirements.txt`/`requirements_api.txt` están pineados varias versiones
detrás de lo que ya tenés instalado y (asumo) probado en `.venv`:

| Paquete | Pineado en requirements | Instalado en .venv |
|---|---|---|
| fastapi | 0.111.0 | 0.138.2 |
| uvicorn | 0.29.0 | 0.49.0 |
| pydantic | 2.7.1 | 2.13.4 |
| pandas | 2.2.2 | 3.0.2 (**mayor**, con breaking changes) |
| requests | 2.31.0 | 2.33.1 |
| beautifulsoup4 | 4.12.3 | 4.15.0 |
| lxml | 5.2.1 | 6.1.1 |

No actualicé estas versiones en los archivos porque no puedo correr
`pip install` ni la suite de tests en esta sesión para verificar que nada se
rompa — en particular `pandas` 2→3 es un salto mayor con cambios de API real.
Recomiendo, cuando tengas shell a mano: activar `.venv`, correr
`pip install -r requirements.txt -r requirements_api.txt --upgrade`, correr
`pytest -v`, y si pasa todo, actualizar los pines a lo que quedó instalado.
Puedo hacerlo yo en una próxima sesión si el sandbox tiene shell disponible.

## 6. Agentic AI — qué se construyó

Ya existía `agentic_ai.py` conectado a `/api/ia/explicar` (explicación
narrativa bajo demanda vía Claude, ya expuesto en varios dashboards con el
botón "Explicar con IA"). Elegiste extenderlo a un **agente más autónomo**, así
que agregué una capa nueva que no depende de que alguien pregunte:

- **`detectar_anomalias(data, data_anterior=None)`** — reglas estadísticas
  simples, sin costo, sin necesitar `ANTHROPIC_API_KEY`: ausentismo crítico
  (`asistencia_pct` < 50%), IQP muy bajo (< 0.30), outliers estadísticos por
  IQR, datos desactualizados (> 10 días sin refresh), indicadores marcados
  como estimación, y — si se le pasa la corrida anterior — caídas fuertes de
  asistencia promedio global o cambios bruscos en la cantidad de diputados
  (señal de scraper roto o composición real cambiada).
- **`resumen_diario(data, data_anterior=None)`** — corre lo anterior y, si hay
  `ANTHROPIC_API_KEY`, le pide a Claude que redacte un resumen ejecutivo en
  lenguaje natural de los hallazgos, priorizando severidad alta/media.
- **`scripts/agente_monitor.py`** — script que se corre solo: lee
  `data/diputados.json`, lo compara contra `data/.snapshot_anterior.json` (la
  corrida de ayer), corre el análisis, guarda `data/alertas_agente.json`, y
  devuelve exit code 1 si hay algo de severidad alta.
- **`.github/workflows/monitor_diario.yml`** — corre el agente automáticamente
  todos los días después del scraping, y si hay severidad alta, manda un email
  de alerta (reutiliza los secrets `MAIL_USER`/`MAIL_PASS` que ya usa
  `tests_diarios.yml`). Esto es lo que lo hace "agéntico" y no solo un
  endpoint más: decide solo si hay algo para avisar, sin que nadie lo tenga
  que revisar a mano.
- **`GET /api/ia/anomalias`** y **`GET /api/ia/resumen`** en `api_server.py`
  — el mismo análisis, disponible on-demand para mostrarlo en el dashboard
  cuando quieras.

**Para activar el resumen narrativo** hace falta el secret `ANTHROPIC_API_KEY`
en GitHub (Settings → Secrets → Actions) y en Railway. Sin ese secret, el
agente sigue detectando y reportando anomalías igual — solo pierde la
redacción en prosa.

**Pendiente de tu lado (no lo hice porque no pude correr nada):** probar
`python scripts/agente_monitor.py` localmente con el `data/diputados.json`
real para confirmar que el análisis tiene sentido con los datos actuales
antes de dejar que el workflow lo corra en producción.

## 7. Limitación técnica de esta sesión

El sandbox de shell de esta sesión reportó falta de espacio en disco y no
pude ejecutar `python`, `pytest`, `pip` ni `git` — todo lo de arriba lo hice
leyendo/editando archivos directamente. Los cambios de código nuevos
(`agentic_ai.py`, `scripts/agente_monitor.py`, endpoints en `api_server.py`)
no están corridos ni testeados por mí en esta sesión. Antes de mergear a
`main`/deployar a Railway, correlos localmente:

```powershell
pytest -v
python scripts/agente_monitor.py
```
