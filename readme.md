# 🏛️ Monitor Legislativo — Cámara de Diputados Argentina

**Versión 1.0 · Marzo 2026**

Monitor de eficiencia legislativa y transparencia presupuestaria de la Honorable Cámara de Diputados de la Nación Argentina. Analiza la composición y el desempeño de los 257 diputados en ejercicio a partir de registros oficiales de la HCDN, el SIL y la OPC.

---

## 📊 Dashboard

| Archivo | Descripción |
|---------|-------------|
| `dashboard/indicadores_diputados.html` | Nómina completa, composición por bloque y distrito, 12 indicadores en 4 dimensiones |
| `dashboard/indicadores2_diputados.html` | Composición por bloque, distrito y rankings |
| `dashboard/indicadores_bloques.html` | Indicadores calculados automáticamente por bloque parlamentario |
| `dashboard/nomina_detalle_diputados.html` | Cards individuales por diputado con indicadores activos |
| `dashboard/metodologia_diputados.html` | Marco conceptual, fórmulas, glosario y bibliografía |
| `dashboard/manual_usuario.html` | Guía de uso del monitor |

---

## 📐 Indicadores — estado v1.0

### ✅ Activos (datos reales 2025)

| Código | Nombre | Valor 2025 | Fuente |
|--------|--------|-----------|--------|
| NEP | Número Efectivo de Partidos | calculado en tiempo real | HCDN |
| IF | Índice de Fragmentación (Rae) | calculado en tiempo real | HCDN |
| IRB | Tasa de Renovación Bienal | calculado en tiempo real | HCDN |
| IRG | Índice de Representación Geográfica | calculado por distrito | HCDN |
| CRC | Costo de Representación por Ciudadano | $4.818 / hab. | TP N°136/2025 |
| RPS | Ratio de Profesionalización del Staff | 57,5% | HCDN Transparencia |
| NAPE | Nivel de Asistencia y Permanencia Efectiva | 27% asistencia perfecta | Direc. Lab. Parlamentaria |
| COLS | Costo Operativo por Ley Sancionada | $17.421 MM / ley | Directorio Legislativo 2025 |
| RLS | Ratio de Legislación Sustantiva | 72,7% | Directorio Legislativo 2025 |
| IAD | Índice de Accesibilidad Documental | 3/5 | Reglamento HCDN Art. 49 |
| TVD | Tasa de Veracidad de Datos | ~97% | Auditoría interna v1.0 |

### ⚠️ Estimación parcial

| Código | Nombre | Estado |
|--------|--------|--------|
| IAP | Índice de Autonomía Presupuestaria | ~0,95 — ejecución exacta pendiente |
| TPMP | Tiempo Promedio de Maduración de Proyectos | rango 30–180 días — requiere SIL |
| ITC | Índice de Trabajo en Comisiones | ~3,5× — requiere actas comisión |
| ECO | Efectividad del Control | <5% histórico — requiere OPC |

### 🔜 Planificado v2.0

| Código | Nombre | Estado |
|--------|--------|--------|
| IPCV | Índice de Participación Ciudadana Virtual | módulo ciudadano Q3 2026 |

---

## 🗂️ Estructura del repositorio

```
monitor_legistativo/
├── dashboard/                  # Frontend estático (HTML servido por api_server.py)
│   ├── index.html
│   ├── indicadores_diputados.html
│   ├── indicadores2_diputados.html
│   ├── indicadores_bloques_diputados.html
│   ├── nomina_detalle_diputados.html
│   ├── nomina_detalle_legisladores.html
│   ├── comparativa_diputados.html
│   ├── metodologia_diputados.html
│   └── manual_usuario.html
├── data/                       # JSON/CSV generados por el pipeline (data/diputados.json es el que consume la API)
├── scrapers/                   # Scrapers por fuente (diputados, asistencia, votaciones, comisiones, SIL, parlamentario)
├── scripts/                    # Jobs puntuales (tipo de cambio, teléfonos, bipartisanship, presupuesto)
├── core/                       # Cálculos de costo de personal y eficiencia
├── indicadores/                # Fórmulas de los indicadores (NEP, NAPE, IQP, etc.)
├── archive/                    # Código archivado, no usado en producción
├── tests/                      # Suite de pytest (ver sección Tests)
├── api_server.py               # API FastAPI que sirve el dashboard y /api/*
├── scraper_pipeline.py         # Pipeline principal — genera data/diputados.json (nómina, foto, asistencia, proyectos, presupuesto, votaciones)
├── actualizar_diputados.py     # Actualiza diputados.json con datos locales de indicadores_votacion.csv
├── obtener_datos.py            # Script legacy best-effort (nómina/DDJJ), complementa nomina_diputados.csv
├── scraper_hcdn.py             # Scraper de votaciones y comisiones
├── agentic_ai.py                # Integración de explicación con IA (/api/ia/explicar)
├── inject_json_to_html.py      # Inyecta el JSON en el HTML para uso local sin servidor
├── Dockerfile / railway.toml   # Deploy en Railway (build Docker + FastAPI/uvicorn)
├── requirements.txt
└── README.md
```

---

## ⚙️ Instalación y uso

```bash
# Clonar el repositorio
git clone https://github.com/Viny2030/monitor_legistativo.git
cd monitor_legistativo

# Instalar dependencias
pip install -r requirements.txt

# Correr el pipeline completo (nómina, foto, asistencia, proyectos, presupuesto, votaciones)
python scraper_pipeline.py
# o un solo paso:
python scraper_pipeline.py --step nomina

# Levantar la API + dashboard localmente
python api_server.py
# abre http://localhost:8000/dashboard
```

---

## 🧪 Tests

El proyecto incluye una suite de tests automatizados que cubre los módulos principales sin hacer llamadas reales a internet.

```bash
# Correr todos los tests
python -m pytest -v
```

| Archivo | Módulo testeado |
|---------|----------------|
| `tests/test_api.py` | `api_server.py` |
| `tests/test_bloque_stats.py` | Cálculo de estadísticas por bloque |
| `tests/test_kpis.py` | KPIs globales del dashboard |
| `tests/test_live.py` | Endpoints en vivo de la API |
| `tests/test_scraper_hcdn.py` | `scraper_hcdn.py` |

**119 tests · 100% passing** (agosto 2026, ver `requirements.txt`)

Los tests usan mocks para simular respuestas HTTP — son reproducibles en cualquier entorno y no requieren conexión a internet.

---

## 🔄 Actualización de datos

El dashboard consume `data/diputados.json` en tiempo real vía `GET /api/diputados` (servido por `api_server.py`) — los HTML ya no tienen datos hardcodeados. Para actualizar:

1. Ejecutar `python scraper_pipeline.py` (local) para regenerar `data/diputados.json`, o disparar `POST /api/refresh` (protegido por `REFRESH_TOKEN`) en el deploy de Railway
2. Los indicadores de composición (NEP, IF, IRB, IRG) se recalculan automáticamente en el navegador al recargar la página, a partir de los nuevos datos

### Frecuencia recomendada
- **Nómina de diputados**: tras cada renovación bienal (diciembre de años impares)
- **Indicadores presupuestarios** (CRC, COLS): anual, con el nuevo presupuesto aprobado
- **Indicadores de actividad** (NAPE, RLS): al cierre del período ordinario (noviembre)

---

## 📚 Fuentes de datos

| Fuente | URL | Datos |
|--------|-----|-------|
| HCDN — Nómina | [diputados.gov.ar](https://www.diputados.gov.ar/diputados/) | Nómina, bloque, distrito, mandato |
| HCDN — Transparencia | [hcdn.gob.ar](https://www.hcdn.gob.ar/institucional/transparencia/) | Presupuesto, empleados, asistencia |
| HCDN — Sesiones | [diputados.gov.ar/sesiones](https://www.diputados.gov.ar/sesiones/) | Sesiones, votaciones, taquigráficas |
| OPC | [opc.gob.ar](https://opc.gob.ar) | Ejecución presupuestaria |
| Directorio Legislativo | [directoriolegislativo.org](https://directoriolegislativo.org) | Estadísticas legislativas |
| AGN | [agn.gov.ar](https://www.agn.gov.ar) | Informes de auditoría |
| INDEC | [indec.gob.ar](https://www.indec.gob.ar) | Proyecciones de población |

---

## 📖 Marco teórico

- Laakso, M. y Taagepera, R. (1979). *Effective Number of Parties*. Comparative Political Studies.
- Rae, D. W. (1967). *The Political Consequences of Electoral Laws*. Yale University Press.
- IPU — Inter-Parliamentary Union (2022). *Parline Database on National Parliaments*.
- OCDE (2021). *Recommendation of the Council on Open Government*.
- CPA-Zentralstelle (2019). *Benchmarking and Self-Assessment for Parliaments*.

---

## ⚠️ Aviso legal

Esta herramienta es de carácter experimental y académico. Los datos provienen de fuentes públicas oficiales del Estado argentino. Los resultados son indicadores algorítmicos — no implican juicio de valor, acusación ni determinación de responsabilidad sobre ninguna empresa, organismo o persona.

---

## 👤 Autor

**Ph.D. Vicente Humberto Monteverde**
Doctor en Ciencias Económicas · Investigador en economía política y fenómenos de corrupción.
Autor de la teoría de Transferencia Regresiva de Ingresos y desarrollador del algoritmo XAI aplicado al análisis de contrataciones públicas.
Publicaciones en *Journal of Financial Crime* (Emerald Publishing).

✉️ vhmonte@retina.ar · viny01958@gmail.com

---

*Monitor Legislativo v1.0 · Marzo 2026 · [github.com/Viny2030/monitor_legistativo](https://github.com/Viny2030/monitor_legistativo)*