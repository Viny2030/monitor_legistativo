"""
agentic_ai.py — Agentic AI para el Monitor Legislativo (Diputados).

Mismo patrón que en los repos hermanos monitor_contratos y justicia1: usa la
API de Anthropic (Claude) para generar explicaciones narrativas en lenguaje
natural sobre los indicadores que ya calcula el resto del sistema (CPR, TPS,
CAF, TMM, ITT, IQP, CUN, CLS, TEF, CAD, EVD, TCI, NAPE, TPMP, ITC, COLS, IAP),
sin volver a tocar los datos.

Degradación elegante: si no está configurada ANTHROPIC_API_KEY, o falla la
librería `anthropic`, todas las llamadas devuelven
{"disponible": False, "motivo": "..."} en vez de romper el endpoint.
"""

import os

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

try:
    import anthropic
    _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
except ImportError:
    anthropic = None
    _client = None


def ia_disponible() -> bool:
    """True si hay librería `anthropic` instalada Y ANTHROPIC_API_KEY configurada."""
    return _client is not None


def _no_disponible(motivo: str) -> dict:
    return {"disponible": False, "motivo": motivo}


def _pedir_a_claude(system: str, prompt: str, max_tokens: int = 500) -> dict:
    if not ia_disponible():
        if anthropic is None:
            return _no_disponible(
                "La librería 'anthropic' no está instalada en este entorno."
            )
        return _no_disponible(
            "ANTHROPIC_API_KEY no está configurada — el asistente de IA está deshabilitado."
        )
    try:
        resp = _client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        texto = "".join(
            bloque.text for bloque in resp.content if getattr(bloque, "type", "") == "text"
        )
        return {"disponible": True, "explicacion": texto.strip()}
    except Exception as e:
        return _no_disponible(f"Error al consultar la IA: {e}")


_SYSTEM_BASE = (
    "Sos un analista de transparencia legislativa que explica, en español "
    "rioplatense claro y sin tecnicismos innecesarios, indicadores algorítmicos "
    "sobre el desempeño de la Cámara de Diputados de la Nación Argentina "
    "(asistencia, producción legislativa, ejecución presupuestaria, apertura "
    "de datos). No acusás a nadie de mal desempeño: describís qué significa el "
    "número, por qué es relevante para la rendición de cuentas (no una "
    "determinación de responsabilidad), y qué pregunta de control ciudadano "
    "ayudaría a contextualizarlo. Sé concreto y breve (4-8 líneas)."
)


def explicar_indicador(perfil: dict) -> dict:
    """
    Explica un indicador puntual del dashboard (una de las 12 tarjetas:
    CPR, TPS, CAF, TMM, ITT, IQP, CUN, CLS, TEF, CAD, EVD, TCI) o de
    /api/indicadores (NAPE, TPMP, ITC, COLS, IAP).

    perfil: dict con al menos id/nombre/valor/unidad; opcionalmente formula,
            interpretacion, fuente, advertencia — lo que ya use el frontend
            para pintar la tarjeta.
    """
    prompt = f"""Indicador "{perfil.get('nombre', perfil.get('id', ''))}" ({perfil.get('id', '—')}):

- Valor actual: {perfil.get('valor', '—')} {perfil.get('unidad', '')}
- Fórmula: {perfil.get('formula', '—')}
- Interpretación oficial: {perfil.get('interpretacion', '—')}
- Fuente: {perfil.get('fuente', 'CKAN HCDN / scraper_pipeline.py')}
{f"- Advertencia de calidad de dato: {perfil['advertencia']}" if perfil.get('advertencia') else ""}

Explicá qué indica este valor sobre el funcionamiento de la Cámara de Diputados,
si es un valor saludable o preocupante en el contexto de una legislatura
democrática, y qué pregunta de control ciudadano ayudaría a profundizarlo."""
    return _pedir_a_claude(_SYSTEM_BASE, prompt)


def explicar_diputado(perfil: dict) -> dict:
    """
    Explica el perfil de un diputado individual (asistencia, proyectos, IQP).
    perfil: dict tal cual lo devuelve /api/diputados/{nombre}.
    """
    prompt = f"""Perfil del diputado/a "{perfil.get('nombre', '—')}" (bloque {perfil.get('bloque', '—')}, distrito {perfil.get('distrito', '—')}):

- Asistencia: {perfil.get('asistencia_pct', '—')}%
- Proyectos presentados: {perfil.get('proyectos_presentados', '—')}
- Proyectos aprobados: {perfil.get('proyectos_aprobados', '—')}
- IQP (Índice de Quórum y Permanencia): {perfil.get('iqp', '—')}

Explicá qué indica este perfil sobre el desempeño legislativo de este diputado/a
y qué habría que contextualizar (por ejemplo: antigüedad en el cargo, comisión
que integra) antes de sacar conclusiones."""
    return _pedir_a_claude(_SYSTEM_BASE, prompt)


def explicar_bloque(perfil: dict) -> dict:
    """
    Explica el desempeño agregado de un bloque parlamentario.
    perfil: dict tal cual lo devuelve /api/bloques (un elemento de la lista).
    """
    prompt = f"""Bloque parlamentario "{perfil.get('bloque', '—')}":

- Diputados: {perfil.get('cantidad', '—')} ({perfil.get('mujeres', '—')} mujeres, {perfil.get('pct_mujeres', '—')}%)
- Asistencia promedio: {perfil.get('asistencia_pct', '—')}%
- Proyectos presentados: {perfil.get('proyectos_presentados', '—')}
- Proyectos aprobados: {perfil.get('proyectos_aprobados', '—')}
- Tasa de aprobación: {perfil.get('tasa_aprobacion', '—')}%
- IQP promedio: {perfil.get('iqp_promedio', '—')}
- Distritos representados: {perfil.get('distritos', [])}

Explicá qué indica este perfil sobre la productividad legislativa y la
representación territorial del bloque."""
    return _pedir_a_claude(_SYSTEM_BASE, prompt)


def explicar(tipo: str, datos: dict) -> dict:
    """Punto de entrada genérico único (mismo patrón que justicia1)."""
    if tipo == "diputado":
        return explicar_diputado(datos or {})
    if tipo == "bloque":
        return explicar_bloque(datos or {})
    return explicar_indicador(datos or {})
