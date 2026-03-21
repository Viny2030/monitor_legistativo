# 🏛️ Monitor de Eficiencia Legislativa – República Argentina

> Herramienta de análisis y visualización del desempeño del Congreso Nacional,
> basada en **12 indicadores cuantitativos** distribuidos en 4 dimensiones.

---

## 📁 Estructura del proyecto

```
monitor_legistativo/
│
├── obtener_datos.py          # Extracción de fuentes oficiales (HCDN, INDEC, BO)
├── scraper_diputados.py      # Scraping básico de nómina
├── nomina_diputados.csv      # Última nómina descargada
│
├── indicadores/
│   └── calculos.py           # ← NUEVO: 12 indicadores con fórmulas y validaciones
│
├── dashboard/
│   └── index.html            # ← NUEVO: Dashboard HTML con los 12 indicadores (14px)
│
├── data/                     # CSVs generados por obtener_datos.py
├── requirements.txt
└── README.md
```

---

## 📊 Los 12 Indicadores de Eficiencia

### Dimensión I – Costos e Insumos (Finanzas Legislativas)

| ID  | Indicador | Fórmula | Fuente |
|-----|-----------|---------|--------|
| CPR | Costo Per Cápita de Representación | `P_total / Pop_total` | Presupuesto Jurisdicción 01 + INDEC |
| TPS | Tasa de Profesionalización del Staff | `(S_perm / (S_perm + S_temp)) × 100` | RRHH Cámara |
| CAF | Coeficiente de Autonomía Fiscal | `P_devengado / P_solicitado` | Presupuesto Abierto |

### Dimensión II – Eficiencia en el Proceso (Productividad)

| ID  | Indicador | Fórmula | Fuente |
|-----|-----------|---------|--------|
| TMM | Tiempo Medio de Maduración Legislativa | `Σ(F_dictamen − F_ingreso) / n` | SIL – Sistema de Información Legislativa |
| ITT | Intensidad de Trabajo Técnico | `ΣH_com / ΣH_pleno` | Actas de comisión / Diario de Sesiones |
| IQP | Índice de Quórum y Permanencia | `[Σ(L_presentes / L_totales)] / V` | Votaciones nominales HCDN |

### Dimensión III – Desempeño y Calidad (Impacto)

| ID  | Indicador | Fórmula | Fuente |
|-----|-----------|---------|--------|
| CUN | Costo Unitario por Norma Sancionada | `P_total / L_sancionadas` | Presupuesto + Boletín Oficial |
| CLS | Calidad Legislativa Sustantiva | `(L_sust / L_total) × 100` | Boletín Oficial / clasificación manual |
| TEF | Tasa de Efectividad de Fiscalización | `IC_resueltos / IF_recibidos` | AGN + Mesa de entradas |

### Dimensión IV – Transparencia y Datos (Tecnología)

| ID  | Indicador | Fórmula | Fuente |
|-----|-----------|---------|--------|
| CAD | Coeficiente de Apertura de Datos | `Σ(V_formato × W_tiempo) / Max_Score` | Auditoría propia del monitor |
| EVD | Error de Veracidad de Datos | `D_erroneos / D_verificables` | Comparación SIL / Boletín Oficial |
| TCI | Tasa de Conversión de Interacción Ciudadana | `(U_activos / U_totales) × 100` | Google Analytics |

---

## ⚠️ Problema detectado: Acceso a DDJJ

El portal **https://ddjj.diputados.gov.ar/** bloquea requests programáticos
(responde HTTP 000 o sin respuesta al detectar que no es un navegador real).

### Causas
- Protección anti-bot (Cloudflare JS Challenge o equivalente)
- El sitio requiere ejecución de JavaScript del lado del cliente

### Soluciones (en orden de recomendación)

**Opción A – Playwright (recomendada, automática):**
```bash
pip install playwright
playwright install chromium
```
```python
from obtener_datos import ddjj_con_playwright
df = ddjj_con_playwright()
```

**Opción B – Descarga manual:**
1. Abrir https://ddjj.diputados.gov.ar/ en el navegador
2. Exportar el listado como CSV o Excel
3. Colocar el archivo en `data/ddjj_diputados.csv`
4. Cargar con:
```python
from obtener_datos import cargar_ddjj_manual
df = cargar_ddjj_manual()
```

**Opción C – datos.gob.ar:**
Verificar si existe dataset en https://datos.gob.ar/dataset/poder-legislativo-declaraciones-juradas

---

## 🚀 Uso rápido

```bash
# Instalar dependencias
pip install -r requirements.txt

# Extraer datos
python obtener_datos.py

# Calcular los 12 indicadores (con datos de ejemplo)
python indicadores/calculos.py

# Ver dashboard
# Abrir dashboard/index.html en el navegador
```

### Calcular con datos reales

```python
from indicadores.calculos import calcular_todos

mis_datos = {
    "presupuesto_total": 185_000_000_000,
    "poblacion_total":   46_654_581,
    "planta_permanente": 3_800,
    "planta_temporaria": 1_200,
    "presupuesto_devengado":  178_000_000_000,
    "presupuesto_solicitado": 185_000_000_000,
    "proyectos": [
        {"fecha_ingreso": "2024-03-01", "fecha_dictamen": "2024-05-15"},
    ],
    "horas_comision": 1240,
    "horas_pleno":    320,
    "votaciones": [{"presentes": 210}, {"presentes": 225}],
    "total_escanos_diputados": 257,
    "leyes_sancionadas": 84,
    "leyes_sustantivas": 31,
    "leyes_total": 84,
    "informes_resueltos": 18,
    "informes_recibidos": 42,
    "datasets": [
        {"formato": "JSON", "tiempo": "inmediato"},
        {"formato": "Excel", "tiempo": "semana"},
    ],
    "datos_verificables": 200,
    "datos_erroneos": 14,
    "usuarios_activos": 3200,
    "sesiones_totales": 48000,
}

resultados = calcular_todos(mis_datos)
for r in resultados:
    print(f"[{r['id']}] {r['valor']} {r['unidad']}")
```

---

## 🔧 Requirements

```
requests>=2.31
beautifulsoup4>=4.12
pandas>=2.0
playwright>=1.40     # opcional, para DDJJ
lxml>=4.9
```

---

## 📚 Bibliografía y Fuentes

- HCDN – https://datos.hcdn.gob.ar
- SIL – https://www.infoleg.gob.ar
- Presupuesto Abierto – https://www.presupuestoabierto.gob.ar
- INDEC Censo 2022 – https://www.indec.gob.ar
- AGN – https://www.agn.gob.ar
- Boletín Oficial – https://www.boletinoficial.gob.ar
- DDJJ Diputados – https://ddjj.diputados.gov.ar (ver nota ⚠️ arriba)