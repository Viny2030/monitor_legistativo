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

Desde v1.1 el módulo también actúa de forma autónoma: `detectar_anomalias()`
y `resumen_diario()` no dependen de Claude — analizan data/diputados.json con
reglas estadísticas simples (IQR, umbrales, comparación contra la corrida
anterior) y devuelven hallazgos estructurados. Si hay ANTHROPIC_API_KEY,
`resumen_diario()` además le pide a Claude que redacte esos hallazgos en
lenguaje natural; si no, el agente sigue siendo útil (solo sin la prosa).
Esto es lo que permite correrlo sin pedido humano (cron/GitHub Action) en
scripts/agente_monitor.py.
"""

import os
import statistics
from datetime import datetime, timezone

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


# ---------------------------------------------------------------------------
# Detección autónoma de anomalías — no requiere Claude ni pedido humano.
# ---------------------------------------------------------------------------
UMBRAL_ASISTENCIA_CRITICA = 50.0   # % por debajo del cual se marca ausentismo crítico
UMBRAL_IQP_BAJO = 0.30             # IQP por debajo del cual se marca inactividad
UMBRAL_DATOS_DESACTUALIZADOS_DIAS = 10
MAX_HALLAZGOS_POR_TIPO = 10        # evita listas gigantes en corridas con muchos outliers


def _severidad(valor: float, umbral: float, muy_grave_a: float) -> str:
    return "alta" if valor <= muy_grave_a else "media" if valor <= umbral else "baja"


def _outliers_iqr(valores_con_id: list[tuple[str, float]]) -> list[dict]:
    """Devuelve los valores por debajo de Q1 - 1.5*IQR (outliers bajos)."""
    if len(valores_con_id) < 8:
        return []  # muestra muy chica para IQR confiable
    valores = sorted(v for _, v in valores_con_id)
    q1 = statistics.quantiles(valores, n=4)[0]
    q3 = statistics.quantiles(valores, n=4)[2]
    iqr = q3 - q1
    piso = q1 - 1.5 * iqr
    return [{"id": ident, "valor": v, "piso_iqr": round(piso, 2)}
            for ident, v in valores_con_id if v < piso]


def _dias_desde(iso_timestamp: str) -> float | None:
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except Exception:
        return None


def detectar_anomalias(data: dict, data_anterior: dict | None = None) -> dict:
    """
    Analiza data/diputados.json (o un payload equivalente) con reglas
    estadísticas simples — sin llamar a Claude, sin costo, apto para correr
    en cada actualización del pipeline.

    data_anterior (opcional): mismo formato, de la corrida previa — habilita
    detección de deltas (caídas de asistencia, cambios de composición).

    Devuelve {"generado_en": iso, "total_hallazgos": n, "hallazgos": [...]}
    con cada hallazgo: {tipo, severidad (alta/media/baja), detalle, ...}.
    """
    hallazgos: list[dict] = []
    diputados = data.get("diputados", []) or []
    meta = data.get("meta", {}) or {}

    # 1) Frescura de los datos
    ultima_act = meta.get("ultima_actualizacion")
    if ultima_act:
        dias = _dias_desde(ultima_act)
        if dias is not None and dias > UMBRAL_DATOS_DESACTUALIZADOS_DIAS:
            hallazgos.append({
                "tipo": "datos_desactualizados",
                "severidad": "alta" if dias > 30 else "media",
                "detalle": f"data/diputados.json no se actualiza hace {dias:.1f} días "
                           f"(última actualización: {ultima_act}). Revisar el pipeline diario.",
            })
    else:
        hallazgos.append({
            "tipo": "datos_sin_metadata",
            "severidad": "media",
            "detalle": "meta.ultima_actualizacion ausente — no se puede verificar frescura del dato.",
        })

    # 2) Ausentismo crítico individual
    con_asistencia = [d for d in diputados if d.get("asistencia_pct") is not None]
    criticos = sorted(
        (d for d in con_asistencia if d["asistencia_pct"] < UMBRAL_ASISTENCIA_CRITICA),
        key=lambda d: d["asistencia_pct"]
    )[:MAX_HALLAZGOS_POR_TIPO]
    for d in criticos:
        hallazgos.append({
            "tipo": "asistencia_critica",
            "severidad": _severidad(d["asistencia_pct"], UMBRAL_ASISTENCIA_CRITICA, 25.0),
            "detalle": f"{d.get('nombre', '?')} ({d.get('bloque', '?')}, {d.get('distrito', '?')}): "
                       f"asistencia {d['asistencia_pct']}%.",
            "diputado": d.get("nombre"),
        })

    # 3) IQP muy bajo (poca permanencia en quórum)
    con_iqp = [d for d in diputados if d.get("iqp") is not None]
    bajos = sorted(
        (d for d in con_iqp if d["iqp"] < UMBRAL_IQP_BAJO),
        key=lambda d: d["iqp"]
    )[:MAX_HALLAZGOS_POR_TIPO]
    for d in bajos:
        hallazgos.append({
            "tipo": "iqp_bajo",
            "severidad": _severidad(d["iqp"], UMBRAL_IQP_BAJO, 0.15),
            "detalle": f"{d.get('nombre', '?')} ({d.get('bloque', '?')}): IQP {d['iqp']} "
                       f"(índice de quórum y permanencia por debajo de {UMBRAL_IQP_BAJO}).",
            "diputado": d.get("nombre"),
        })

    # 4) Outliers estadísticos de asistencia (IQR) — captura casos que no bajan
    #    del umbral fijo pero sí se despegan mucho del resto del cuerpo.
    pares_asistencia = [(d.get("nombre", "?"), d["asistencia_pct"]) for d in con_asistencia]
    for o in _outliers_iqr(pares_asistencia)[:MAX_HALLAZGOS_POR_TIPO]:
        hallazgos.append({
            "tipo": "outlier_estadistico_asistencia",
            "severidad": "baja",
            "detalle": f"{o['id']}: asistencia {o['valor']}%, por debajo del piso estadístico "
                       f"({o['piso_iqr']}%) del resto del cuerpo.",
            "diputado": o["id"],
        })

    # 5) Indicadores con calidad de dato marcada explícitamente como estimación
    for clave in ("tpmp", "itc"):
        info = data.get(clave) or {}
        if info.get("advertencia"):
            hallazgos.append({
                "tipo": "indicador_estimado",
                "severidad": "baja",
                "detalle": f"{clave.upper()} usa un valor de referencia, no dato en vivo: "
                           f"{info['advertencia']}",
            })

    # 6) Comparación contra la corrida anterior (si se provee)
    if data_anterior:
        diputados_ant = data_anterior.get("diputados", []) or []
        asist_ant = [d["asistencia_pct"] for d in diputados_ant if d.get("asistencia_pct") is not None]
        asist_act = [d["asistencia_pct"] for d in con_asistencia]
        if asist_ant and asist_act:
            prom_ant = statistics.mean(asist_ant)
            prom_act = statistics.mean(asist_act)
            delta = prom_act - prom_ant
            if abs(delta) >= 5.0:
                hallazgos.append({
                    "tipo": "delta_asistencia_global",
                    "severidad": "alta" if abs(delta) >= 10 else "media",
                    "detalle": f"Asistencia promedio global {'subió' if delta > 0 else 'cayó'} "
                               f"{abs(round(delta, 1))} puntos vs. la corrida anterior "
                               f"({round(prom_ant, 1)}% → {round(prom_act, 1)}%).",
                })

        n_ant, n_act = len(diputados_ant), len(diputados)
        if n_ant and n_act and n_ant != n_act:
            hallazgos.append({
                "tipo": "delta_composicion",
                "severidad": "media",
                "detalle": f"La cantidad de diputados en el dataset cambió de {n_ant} a {n_act} "
                           f"entre corridas — revisar si es una actualización real de composición "
                           f"o un problema del scraper (datos parciales).",
            })

    orden_severidad = {"alta": 0, "media": 1, "baja": 2}
    hallazgos.sort(key=lambda h: orden_severidad.get(h["severidad"], 3))

    return {
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "total_hallazgos": len(hallazgos),
        "por_severidad": {
            s: sum(1 for h in hallazgos if h["severidad"] == s)
            for s in ("alta", "media", "baja")
        },
        "hallazgos": hallazgos,
    }


def resumen_diario(data: dict, data_anterior: dict | None = None) -> dict:
    """
    Punto de entrada del agente autónomo: corre detectar_anomalias() (siempre
    funciona, no depende de Claude) y, si hay IA disponible, le pide a Claude
    que redacte un resumen ejecutivo en lenguaje natural de esos hallazgos
    para mandar por email o mostrar en el dashboard.
    """
    analisis = detectar_anomalias(data, data_anterior)

    resultado = {
        "generado_en": analisis["generado_en"],
        "total_diputados": len(data.get("diputados", []) or []),
        "analisis": analisis,
        "narrativa": None,
    }

    if analisis["total_hallazgos"] == 0:
        resultado["narrativa"] = {
            "disponible": True,
            "explicacion": "Sin anomalías detectadas en esta corrida: asistencia, IQP y "
                           "frescura de datos dentro de los rangos esperados.",
        }
        return resultado

    if not ia_disponible():
        resultado["narrativa"] = _no_disponible(
            "Hallazgos estructurados generados sin problema (no requieren IA); "
            "la redacción narrativa está deshabilitada porque no hay ANTHROPIC_API_KEY."
        )
        return resultado

    resumen_hallazgos = "\n".join(
        f"- [{h['severidad'].upper()}] {h['tipo']}: {h['detalle']}"
        for h in analisis["hallazgos"][:15]
    )
    prompt = f"""El agente de monitoreo detectó {analisis['total_hallazgos']} hallazgos en la
corrida de hoy sobre la Cámara de Diputados (Alta: {analisis['por_severidad']['alta']},
Media: {analisis['por_severidad']['media']}, Baja: {analisis['por_severidad']['baja']}):

{resumen_hallazgos}

Redactá un resumen ejecutivo breve (6-10 líneas) para un email de alerta interno,
priorizando lo de severidad alta y media. No es una acusación a ningún diputado
puntual: encuadralo como control de calidad de datos y seguimiento de transparencia."""

    resultado["narrativa"] = _pedir_a_claude(_SYSTEM_BASE, prompt, max_tokens=400)
    return resultado
