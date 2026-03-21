# 🏛️ Monitor de Eficiencia Legislativa – República Argentina

Herramienta de análisis y visualización del desempeño del Congreso Nacional,
basada en **12 indicadores cuantitativos** distribuidos en 4 dimensiones.

---

## 📁 Estructura del proyecto

```
monitor_legistativo/
│
├── data_loader.py          # ← NUEVO: conecta CSVs reales a calculos.py
├── scraper_hcdn.py         # ← NUEVO: scraping de votaciones/comisión (TMM/ITT/IQP)
├── obtener_datos.py        # Extracción: nómina diputados, presupuesto
├── scraper_diputados.py    # Scraping básico de nómina
│
├── indicadores/
│   └── calculos.py         # 12 indicadores con fórmulas y validaciones
│
├── api/
│   ├── __init__.py
│   └── main.py             # ← NUEVO: FastAPI – endpoint /indicadores (JSON)
│
├── dashboard/
│   └── index.html          # ← NUEVO: Dashboard dinámico (fetch al endpoint)
│
├── data/                   # CSVs generados automáticamente
├── requirements.txt
└── README.md
```

---

## 🚀 Setup rápido (5 pasos)

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Descargar datos reales

```bash
python obtener_datos.py
```

Esto genera:
- `data/nomina_diputados.csv` (257 diputados vía scraping HCDN)
- `data/presupuesto_2024.csv` (Jurisdicción 01 vía datos.gob.ar)

### 3. (Opcional) Datos de votaciones y comisión para TMM/ITT/IQP

```bash
python scraper_hcdn.py
```

Si los datos de HCDN no están disponibles automáticamente,
editá `MANUAL_OVERRIDES` en `data_loader.py` con los valores reales.

### 4. Levantar el servidor API

```bash
uvicorn api.main:app --reload --port 8000
```

Endpoints disponibles:
- `http://localhost:8000/indicadores` — los 12 indicadores en JSON
- `http://localhost:8000/indicadores/CPR` — un indicador por ID
- `http://localhost:8000/docs` — documentación interactiva Swagger
- `http://localhost:8000/indicadores?scraper=true` — con scraping en tiempo real

### 5. Ver el dashboard

Abrí `dashboard/index.html` en el navegador (con el servidor corriendo en paso 4).

El dashboard carga automáticamente los datos desde el endpoint.
Si el servidor no está disponible, muestra datos de fallback hardcodeados.

---

## 📊 Los 12 Indicadores de Eficiencia

### Dimensión I – Costos e Insumos (Finanzas Legislativas)

| ID  | Indicador                            | Fórmula                                  | Fuente                     | Automático |
|-----|--------------------------------------|------------------------------------------|----------------------------|------------|
| CPR | Costo Per Cápita de Representación   | P_total / Pop_total                      | Presupuesto + INDEC        | ✅ CSV      |
| TPS | Tasa de Profesionalización del Staff | (S_perm / (S_perm + S_temp)) × 100      | RRHH HCDN                  | ⏳ Manual   |
| CAF | Coeficiente de Autonomía Fiscal      | P_devengado / P_solicitado               | Presupuesto Abierto        | ✅ CSV      |

### Dimensión II – Eficiencia en el Proceso (Productividad)

| ID  | Indicador                             | Fórmula                                   | Fuente                     | Automático |
|-----|---------------------------------------|-------------------------------------------|----------------------------|------------|
| TMM | Tiempo Medio de Maduración Legislativa | Σ(F_dictamen − F_ingreso) / n            | SIL HCDN                   | ✅ Scraper  |
| ITT | Intensidad de Trabajo Técnico         | ΣH_com / ΣH_pleno                        | Actas comisión HCDN        | ✅ Scraper  |
| IQP | Índice de Quórum y Permanencia        | [Σ(L_presentes / L_totales)] / V         | Votaciones nominales HCDN  | ✅ Scraper  |

### Dimensión III – Desempeño y Calidad (Impacto)

| ID  | Indicador                            | Fórmula                                   | Fuente                     | Automático |
|-----|--------------------------------------|-------------------------------------------|----------------------------|------------|
| CUN | Costo Unitario por Norma Sancionada  | P_total / L_sancionadas                   | Presupuesto + BO           | ✅ CSV      |
| CLS | Calidad Legislativa Sustantiva       | (L_sust / L_total) × 100                 | BO / clasificación manual  | ⏳ Manual   |
| TEF | Tasa de Efectividad de Fiscalización | IC_resueltos / IF_recibidos               | AGN + Mesa de entradas     | ⏳ Manual   |

### Dimensión IV – Transparencia y Datos (Tecnología)

| ID  | Indicador                                  | Fórmula                                          | Fuente               | Automático |
|-----|--------------------------------------------|--------------------------------------------------|----------------------|------------|
| CAD | Coeficiente de Apertura de Datos           | Σ(V_formato × W_tiempo) / Max_Score             | Auditoría propia     | ⏳ Manual   |
| EVD | Error de Veracidad de Datos                | D_erroneos / D_verificables                      | Comparación SIL/BO   | ⏳ Manual   |
| TCI | Tasa de Conversión de Interacción Ciudadana | (U_activos / U_totales) × 100                   | Google Analytics     | ⏳ Manual   |

---

## 🌐 Deploy / GitHub Pages

Para publicar el dashboard en GitHub Pages sin servidor:
1. El `dashboard/index.html` tiene fallback con datos hardcodeados cuando el servidor no responde.
2. Para datos dinámicos en producción, desplegá el servidor FastAPI en Render/Railway/Fly.io
   y definí `window.API_URL = 'https://tu-api.render.com'` antes del `<script>` en el HTML.

---

## 📚 Bibliografía y Fuentes

- **HCDN** – https://datos.hcdn.gob.ar
- **SIL** – https://www.infoleg.gob.ar
- **Presupuesto Abierto** – https://www.presupuestoabierto.gob.ar
- **INDEC Censo 2022** – https://www.indec.gob.ar
- **AGN** – https://www.agn.gob.ar
- **Boletín Oficial** – https://www.boletinoficial.gob.ar
- **IPU Parliamentary Indicators** – https://www.ipu.org
- **OCDE Government at a Glance** – https://www.oecd.org
- **Open Government Partnership** – https://www.opengovpartnership.org