"""
indicadores/calculos.py
=======================
12 Indicadores de Eficiencia Legislativa – Monitor Legislativo Argentina
Basado en Dimensiones I-IV (Costos, Productividad, Impacto, Transparencia)

Cada función acepta un dict con los datos necesarios y devuelve un dict con:
  - valor    : float calculado
  - formula  : str con la fórmula en notación matemática
  - unidad   : str
  - interpretacion: str breve
"""

from __future__ import annotations
from datetime import date
from typing import Union


# ─────────────────────────────────────────────────────────────────────────────
# DIMENSIÓN I: Costos e Insumos (Finanzas Legislativas)
# ─────────────────────────────────────────────────────────────────────────────

def costo_per_capita_representacion(presupuesto_total: float, poblacion_total: int) -> dict:
    """
    Indicador 1 – Costo Per Cápita de Representación (CPR)
    CPR = P_total / Pop_total

    Fuentes:
      presupuesto_total : Presupuesto ejecutado Jurisdicción 01 (en $ ARS)
      poblacion_total   : Censo INDEC (habitantes)
    """
    if poblacion_total <= 0:
        raise ValueError("La población total debe ser > 0")
    valor = presupuesto_total / poblacion_total
    return {
        "id": "CPR",
        "nombre": "Costo Per Cápita de Representación",
        "dimension": "I – Costos e Insumos",
        "valor": round(valor, 2),
        "formula": "CPR = P_total / Pop_total",
        "unidad": "$ ARS por habitante",
        "interpretacion": "A mayor valor, mayor costo que cada ciudadano solventa para mantener el Congreso.",
        "inputs": {"presupuesto_total": presupuesto_total, "poblacion_total": poblacion_total},
    }


def tasa_profesionalizacion_staff(planta_permanente: int, planta_temporaria: int) -> dict:
    """
    Indicador 2 – Tasa de Profesionalización del Staff (TPS)
    TPS = (S_perm / (S_perm + S_temp)) × 100

    Fuentes:
      planta_permanente : Agentes en carrera (Planta Permanente)
      planta_temporaria : Asesores políticos y contratados (Planta Temporaria)
    """
    total = planta_permanente + planta_temporaria
    if total <= 0:
        raise ValueError("La suma de planta permanente + temporaria debe ser > 0")
    valor = (planta_permanente / total) * 100
    return {
        "id": "TPS",
        "nombre": "Tasa de Profesionalización del Staff",
        "dimension": "I – Costos e Insumos",
        "valor": round(valor, 2),
        "formula": "TPS = (S_perm / (S_perm + S_temp)) × 100",
        "unidad": "%",
        "interpretacion": "Porcentaje del personal con estabilidad en la carrera. Mayor valor = mayor profesionalización.",
        "inputs": {"planta_permanente": planta_permanente, "planta_temporaria": planta_temporaria},
    }


def coeficiente_autonomia_fiscal(presupuesto_devengado: float, presupuesto_solicitado: float) -> dict:
    """
    Indicador 3 – Coeficiente de Autonomía Fiscal (CAF)
    CAF = P_devengado / P_solicitado

    Fuentes:
      presupuesto_devengado : Presupuesto que efectivamente recibió el Congreso
      presupuesto_solicitado: Presupuesto pedido en el anteproyecto original
    """
    if presupuesto_solicitado <= 0:
        raise ValueError("El presupuesto solicitado debe ser > 0")
    valor = presupuesto_devengado / presupuesto_solicitado
    return {
        "id": "CAF",
        "nombre": "Coeficiente de Autonomía Fiscal",
        "dimension": "I – Costos e Insumos",
        "valor": round(valor, 4),
        "formula": "CAF = P_devengado / P_solicitado",
        "unidad": "ratio (0–1+)",
        "interpretacion": "CAF=1.0: asignación completa. <1: recorte. >1: refuerzo. Mide autonomía presupuestaria del Congreso.",
        "inputs": {"presupuesto_devengado": presupuesto_devengado, "presupuesto_solicitado": presupuesto_solicitado},
    }


# ─────────────────────────────────────────────────────────────────────────────
# DIMENSIÓN II: Eficiencia en el Proceso (Productividad)
# ─────────────────────────────────────────────────────────────────────────────

def tiempo_medio_maduracion(proyectos: list[dict]) -> dict:
    """
    Indicador 4 – Tiempo Medio de Maduración Legislativa (TMM)
    TMM = Σ(F_dictamen_i - F_ingreso_i) / n

    Cada elemento de `proyectos` debe tener:
      fecha_ingreso  : date  (Mesa de Entradas)
      fecha_dictamen : date  (Despacho de Comisión)
    """
    if not proyectos:
        raise ValueError("La lista de proyectos no puede estar vacía")
    diferencias = []
    for p in proyectos:
        fi = p["fecha_ingreso"]
        fd = p["fecha_dictamen"]
        if isinstance(fi, str):
            fi = date.fromisoformat(fi)
        if isinstance(fd, str):
            fd = date.fromisoformat(fd)
        dias = (fd - fi).days
        diferencias.append(dias)
    valor = sum(diferencias) / len(diferencias)
    return {
        "id": "TMM",
        "nombre": "Tiempo Medio de Maduración Legislativa",
        "dimension": "II – Eficiencia en el Proceso",
        "valor": round(valor, 1),
        "formula": "TMM = Σ(F_dictamen_i − F_ingreso_i) / n",
        "unidad": "días",
        "interpretacion": "Promedio de días que tarda un proyecto en obtener dictamen. Menor valor = mayor agilidad.",
        "inputs": {"n_proyectos": len(proyectos)},
    }


def intensidad_trabajo_tecnico(horas_comision: float, horas_pleno: float) -> dict:
    """
    Indicador 5 – Intensidad de Trabajo Técnico (ITT)
    ITT = ΣH_com / ΣH_pleno

    Fuentes:
      horas_comision : Horas totales de reuniones de comisión
      horas_pleno    : Horas totales de sesiones en el recinto
    """
    if horas_pleno <= 0:
        raise ValueError("Las horas de pleno deben ser > 0")
    valor = horas_comision / horas_pleno
    return {
        "id": "ITT",
        "nombre": "Intensidad de Trabajo Técnico",
        "dimension": "II – Eficiencia en el Proceso",
        "valor": round(valor, 3),
        "formula": "ITT = ΣH_com / ΣH_pleno",
        "unidad": "ratio",
        "interpretacion": "ITT>1: el trabajo técnico supera al debate plenario. Indica mayor elaboración pre-legislativa.",
        "inputs": {"horas_comision": horas_comision, "horas_pleno": horas_pleno},
    }


def indice_quorum_permanencia(votaciones: list[dict], total_escanos: int) -> dict:
    """
    Indicador 6 – Índice de Quórum y Permanencia (IQP)
    IQP = [Σ(L_presentes_v / L_totales)] / V

    Cada elemento de `votaciones` debe tener:
      presentes : int  (legisladores que emitieron voto)

    total_escanos : 257 (Diputados) o 72 (Senado)
    """
    if not votaciones:
        raise ValueError("Debe haber al menos una votación")
    if total_escanos <= 0:
        raise ValueError("El total de escaños debe ser > 0")
    cocientes = [v["presentes"] / total_escanos for v in votaciones]
    valor = sum(cocientes) / len(cocientes)
    return {
        "id": "IQP",
        "nombre": "Índice de Quórum y Permanencia",
        "dimension": "II – Eficiencia en el Proceso",
        "valor": round(valor, 4),
        "formula": "IQP = [Σ(L_presentes_v / L_totales)] / V",
        "unidad": "ratio (0–1)",
        "interpretacion": "Promedio de asistencia efectiva en votaciones. Máximo=1.0. Mayor valor = mayor compromiso.",
        "inputs": {"total_votaciones": len(votaciones), "total_escanos": total_escanos},
    }


# ─────────────────────────────────────────────────────────────────────────────
# DIMENSIÓN III: Desempeño y Calidad (Impacto)
# ─────────────────────────────────────────────────────────────────────────────

def costo_unitario_norma_sancionada(presupuesto_total: float, leyes_sancionadas: int) -> dict:
    """
    Indicador 7 – Costo Unitario por Norma Sancionada (CUN)
    CUN = P_total / L_sancionadas

    leyes_sancionadas: Leyes publicadas en Boletín Oficial
    """
    if leyes_sancionadas <= 0:
        raise ValueError("Las leyes sancionadas deben ser > 0")
    valor = presupuesto_total / leyes_sancionadas
    return {
        "id": "CUN",
        "nombre": "Costo Unitario por Norma Sancionada",
        "dimension": "III – Desempeño y Calidad",
        "valor": round(valor, 2),
        "formula": "CUN = P_total / L_sancionadas",
        "unidad": "$ ARS por ley",
        "interpretacion": "Costo promedio de producir una ley. Permite comparación interanual e intercameral.",
        "inputs": {"presupuesto_total": presupuesto_total, "leyes_sancionadas": leyes_sancionadas},
    }


def calidad_legislativa_sustantiva(leyes_sustantivas: int, leyes_total: int) -> dict:
    """
    Indicador 8 – Calidad Legislativa Sustantiva (CLS)
    CLS = (L_sust / L_total) × 100

    leyes_sustantivas : Leyes que modifican cuerpo normativo de fondo
    leyes_total       : Total de leyes (incluye declaraciones, días nacionales, etc.)
    """
    if leyes_total <= 0:
        raise ValueError("El total de leyes debe ser > 0")
    valor = (leyes_sustantivas / leyes_total) * 100
    return {
        "id": "CLS",
        "nombre": "Calidad Legislativa Sustantiva",
        "dimension": "III – Desempeño y Calidad",
        "valor": round(valor, 2),
        "formula": "CLS = (L_sust / L_total) × 100",
        "unidad": "%",
        "interpretacion": "Proporción de legislación de fondo sobre el total. Mayor % = mayor sustancia normativa.",
        "inputs": {"leyes_sustantivas": leyes_sustantivas, "leyes_total": leyes_total},
    }


def tasa_efectividad_fiscalizacion(informes_resueltos: int, informes_recibidos: int) -> dict:
    """
    Indicador 9 – Tasa de Efectividad de Fiscalización (TEF)
    TEF = IC_resueltos / IF_recibidos

    informes_resueltos : Informes AGN / pedidos de informe respondidos con seguimiento
    informes_recibidos : Total de informes/pedidos de control ingresados
    """
    if informes_recibidos <= 0:
        raise ValueError("Los informes recibidos deben ser > 0")
    valor = informes_resueltos / informes_recibidos
    return {
        "id": "TEF",
        "nombre": "Tasa de Efectividad de Fiscalización",
        "dimension": "III – Desempeño y Calidad",
        "valor": round(valor, 4),
        "formula": "TEF = IC_resueltos / IF_recibidos",
        "unidad": "ratio (0–1)",
        "interpretacion": "Proporción de controles que generaron seguimiento efectivo. Máximo=1.0.",
        "inputs": {"informes_resueltos": informes_resueltos, "informes_recibidos": informes_recibidos},
    }


# ─────────────────────────────────────────────────────────────────────────────
# DIMENSIÓN IV: Transparencia y Datos (Tecnología)
# ─────────────────────────────────────────────────────────────────────────────

# Tablas de puntaje para CAD
FORMATO_SCORE = {"PDF": 1, "Excel": 3, "JSON": 5, "API": 5}
TIEMPO_PESO = {"inmediato": 1.0, "semana": 0.5, "mes": 0.1}


def coeficiente_apertura_datos(datasets: list[dict], max_score: float | None = None) -> dict:
    """
    Indicador 10 – Coeficiente de Apertura de Datos (CAD)
    CAD = Σ(V_formato × W_tiempo) / Max_Score

    Cada elemento de `datasets` debe tener:
      formato : "PDF" | "Excel" | "JSON" | "API"
      tiempo  : "inmediato" | "semana" | "mes"

    max_score : puntaje teórico máximo (si None, se calcula como n × 5 × 1.0)
    """
    if not datasets:
        raise ValueError("Debe haber al menos un dataset evaluado")
    puntajes = []
    for d in datasets:
        v = FORMATO_SCORE.get(d["formato"], 1)
        w = TIEMPO_PESO.get(d["tiempo"], 0.1)
        puntajes.append(v * w)
    suma = sum(puntajes)
    ms = max_score if max_score else len(datasets) * 5 * 1.0
    valor = suma / ms
    return {
        "id": "CAD",
        "nombre": "Coeficiente de Apertura de Datos",
        "dimension": "IV – Transparencia y Datos",
        "valor": round(valor, 4),
        "formula": "CAD = Σ(V_formato × W_tiempo) / Max_Score",
        "unidad": "ratio (0–1)",
        "interpretacion": "Mide calidad y accesibilidad de los datos publicados. Mayor valor = mayor apertura real.",
        "inputs": {"n_datasets": len(datasets), "max_score": ms},
    }


def error_veracidad_datos(datos_verificables: int, datos_erroneos: int) -> dict:
    """
    Indicador 11 – Error de Veracidad de Datos (EVD)
    EVD = 1 − ((D_verificables − D_erroneos) / D_verificables)
         = D_erroneos / D_verificables

    datos_verificables : Puntos auditados contra fuente primaria (SIL / BO)
    datos_erroneos     : Datos que no coinciden con la fuente
    """
    if datos_verificables <= 0:
        raise ValueError("Los datos verificables deben ser > 0")
    valor = datos_erroneos / datos_verificables
    return {
        "id": "EVD",
        "nombre": "Error de Veracidad de Datos",
        "dimension": "IV – Transparencia y Datos",
        "valor": round(valor, 4),
        "formula": "EVD = D_erroneos / D_verificables",
        "unidad": "ratio (0–1)",
        "interpretacion": "Tasa de error respecto a la fuente primaria. EVD=0 es lo ideal; mayor valor = menos confiable.",
        "inputs": {"datos_verificables": datos_verificables, "datos_erroneos": datos_erroneos},
    }


def tasa_conversion_interaccion_ciudadana(usuarios_activos: int, sesiones_totales: int) -> dict:
    """
    Indicador 12 – Tasa de Conversión de Interacción Ciudadana (TCI)
    TCI = (U_activos / U_totales) × 100

    usuarios_activos : Usuarios que hicieron clic en Comentar/Votar/Descargar
    sesiones_totales : Sesiones totales en el sitio del monitor (Google Analytics)
    """
    if sesiones_totales <= 0:
        raise ValueError("Las sesiones totales deben ser > 0")
    valor = (usuarios_activos / sesiones_totales) * 100
    return {
        "id": "TCI",
        "nombre": "Tasa de Conversión de Interacción Ciudadana",
        "dimension": "IV – Transparencia y Datos",
        "valor": round(valor, 2),
        "formula": "TCI = (U_activos / U_totales) × 100",
        "unidad": "%",
        "interpretacion": "Porcentaje de visitantes que interactúan activamente. Mayor valor = mayor participación ciudadana.",
        "inputs": {"usuarios_activos": usuarios_activos, "sesiones_totales": sesiones_totales},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Runner de demostración con datos de ejemplo
# ─────────────────────────────────────────────────────────────────────────────

DATOS_EJEMPLO = {
    # Dimensión I
    "presupuesto_total": 185_000_000_000,   # $185 mil millones ARS (referencia Ley Presupuesto)
    "poblacion_total":   46_654_581,         # INDEC Censo 2022
    "planta_permanente": 3_800,
    "planta_temporaria": 1_200,
    "presupuesto_devengado": 178_000_000_000,
    "presupuesto_solicitado": 185_000_000_000,

    # Dimensión II
    "proyectos": [
        {"fecha_ingreso": "2024-03-01", "fecha_dictamen": "2024-05-15"},
        {"fecha_ingreso": "2024-04-10", "fecha_dictamen": "2024-06-20"},
        {"fecha_ingreso": "2024-01-05", "fecha_dictamen": "2024-03-10"},
    ],
    "horas_comision": 1_240,
    "horas_pleno":    320,
    "votaciones": [{"presentes": 210}, {"presentes": 198}, {"presentes": 225}],
    "total_escanos_diputados": 257,

    # Dimensión III
    "leyes_sancionadas": 84,
    "leyes_sustantivas": 31,
    "leyes_total": 84,
    "informes_resueltos": 18,
    "informes_recibidos": 42,

    # Dimensión IV
    "datasets": [
        {"formato": "JSON",  "tiempo": "inmediato"},
        {"formato": "Excel", "tiempo": "semana"},
        {"formato": "PDF",   "tiempo": "mes"},
        {"formato": "API",   "tiempo": "inmediato"},
        {"formato": "PDF",   "tiempo": "semana"},
    ],
    "datos_verificables": 200,
    "datos_erroneos":     14,
    "usuarios_activos":   3_200,
    "sesiones_totales":   48_000,
}


def calcular_todos(datos: dict = DATOS_EJEMPLO) -> list[dict]:
    """Ejecuta los 12 indicadores y devuelve la lista de resultados."""
    d = datos
    resultados = [
        costo_per_capita_representacion(d["presupuesto_total"], d["poblacion_total"]),
        tasa_profesionalizacion_staff(d["planta_permanente"], d["planta_temporaria"]),
        coeficiente_autonomia_fiscal(d["presupuesto_devengado"], d["presupuesto_solicitado"]),
        tiempo_medio_maduracion(d["proyectos"]),
        intensidad_trabajo_tecnico(d["horas_comision"], d["horas_pleno"]),
        indice_quorum_permanencia(d["votaciones"], d["total_escanos_diputados"]),
        costo_unitario_norma_sancionada(d["presupuesto_total"], d["leyes_sancionadas"]),
        calidad_legislativa_sustantiva(d["leyes_sustantivas"], d["leyes_total"]),
        tasa_efectividad_fiscalizacion(d["informes_resueltos"], d["informes_recibidos"]),
        coeficiente_apertura_datos(d["datasets"]),
        error_veracidad_datos(d["datos_verificables"], d["datos_erroneos"]),
        tasa_conversion_interaccion_ciudadana(d["usuarios_activos"], d["sesiones_totales"]),
    ]
    return resultados


if __name__ == "__main__":
    import json
    print("=" * 70)
    print("   MONITOR LEGISLATIVO – 12 INDICADORES DE EFICIENCIA")
    print("=" * 70)
    for r in calcular_todos():
        print(f"\n[{r['id']}] {r['nombre']}")
        print(f"   Dimensión : {r['dimension']}")
        print(f"   Valor     : {r['valor']} {r['unidad']}")
        print(f"   Fórmula   : {r['formula']}")
        print(f"   Lectura   : {r['interpretacion']}")
    print("\n" + "=" * 70)