# Automatización del Monitor Legislativo — Diputados

Este documento describe los archivos nuevos agregados al repo para automatizar
los datos del dashboard `indicadores_diputados.html`.

**Ningún archivo existente fue modificado.**

---

## Archivos nuevos

| Archivo | Propósito |
|---|---|
| `scraper_pipeline.py` | Pipeline unificado de scraping (5 fuentes) |
| `api_server.py` | API FastAPI para Railway |
| `inject_json_to_html.py` | Helper para uso local file:// |
| `requirements_api.txt` | Dependencias adicionales de la API |
| `Dockerfile` | Imagen Docker para Railway |
| `.github/workflows/update_data.yml` | CI/CD cada 15 días |

---

## Flujo de datos

```
scraper_pipeline.py
       │
       ├── diputados.gov.ar    → nomina + genero
       ├── hcdn.gob.ar/asist.  → asistencia por diputado
       ├── hcdn.gob.ar/proyect → proyectos presentados/aprobados
       ├── presupuestoabierto  → ejecucion presupuestaria (API REST)
       └── votaciones.hcdn.gov → votaciones nominales (IQP)
               │
               ▼
        data/diputados.json
               │
       ┌───────┴───────┐
       │               │
 api_server.py   inject_json_to_html.py
 (Railway)        (local file://)
       │               │
  /api/diputados  indicadores_diputados_local.html
  /api/bloques
  /api/kpis
  /api/presupuesto
```

---

## Uso local

### 1. Correr el pipeline

```powershell
# Pipeline completo
python scraper_pipeline.py

# Solo un step
python scraper_pipeline.py --step nomina
python scraper_pipeline.py --step asistencia
python scraper_pipeline.py --step proyectos
python scraper_pipeline.py --step presupuesto
python scraper_pipeline.py --step votaciones
```

Genera: `data/diputados.json`

### 2. Inyectar datos en el HTML para file://

```powershell
python inject_json_to_html.py
```

Genera: `dashboard/indicadores_diputados_local.html`
Abrir con Chrome directamente (no modifica el original).

### 3. Correr la API localmente

```powershell
pip install -r requirements_api.txt
python api_server.py
# API disponible en http://localhost:8000
# Docs en http://localhost:8000/docs
```

---

## Deploy en Railway

1. Conectar el repo en Railway → detecta el `Dockerfile` automáticamente.
2. Agregar variables de entorno en Railway:
   - `REFRESH_TOKEN` → token secreto para `/api/refresh`
   - `PORT` → Railway lo asigna automáticamente
3. El GitHub Action commitea el JSON cada 15 días → Railway hace redeploy automático.
4. (Opcional) Descomentar el paso "Trigger Railway redeploy" en el workflow
   y agregar `RAILWAY_WEBHOOK_URL` en los secrets del repo.

---

## Endpoints de la API

| Endpoint | Descripción |
|---|---|
| `GET /` | Health check |
| `GET /api/diputados` | Array completo (filtros: bloque, distrito, genero) |
| `GET /api/diputados/{nombre}` | Buscar diputado por apellido |
| `GET /api/bloques` | Estadísticas por bloque |
| `GET /api/presupuesto` | Ejecución presupuestaria |
| `GET /api/kpis` | KPIs globales (NAPE, TPMP, COLS, IAP, IQP, RLS) |
| `POST /api/refresh` | Dispara el pipeline (requiere header X-Refresh-Token) |

---

## GitHub Action

El workflow `.github/workflows/update_data.yml`:
- Se ejecuta automáticamente el **día 1 y 15 de cada mes** a las 6:00 ART.
- Se puede disparar manualmente desde la pestaña **Actions** del repo.
- Al terminar exitosamente, commitea el JSON actualizado con mensaje `[skip ci]`.
- Genera un resumen en la pestaña Actions con el conteo de diputados y el IAP.

Para activarlo: solo hace falta que el archivo exista en `.github/workflows/`.
No requiere configuración adicional de secrets para el funcionamiento básico.