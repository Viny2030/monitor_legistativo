from .diputados import obtener_nomina
from .fuentes import (
    descargar_subsidios,
    descargar_subsidios_historico,
    descargar_nomina_personal,
    generar_tabla_remuneraciones,
    diagnosticar_fuentes,
    descargar_escala_salarial,
)
from .votaciones import descargar_votaciones, calcular_indicadores_votacion
from .parlamentario import (
    buscar_articulos,
    monitorear_modulo,
    descargar_noticias_relevantes,
)

__all__ = [
    "obtener_nomina",
    "descargar_subsidios",
    "descargar_subsidios_historico",
    "descargar_nomina_personal",
    "generar_tabla_remuneraciones",
    "diagnosticar_fuentes",
    "descargar_escala_salarial",
    "descargar_votaciones",
    "calcular_indicadores_votacion",
    "buscar_articulos",
    "monitorear_modulo",
    "descargar_noticias_relevantes",
]