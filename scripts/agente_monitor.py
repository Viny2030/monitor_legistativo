"""
scripts/agente_monitor.py — Agente autónomo de monitoreo.

Corre después del pipeline diario (scraper_pipeline.py). Lee
data/diputados.json, lo compara contra la corrida anterior guardada en
data/.snapshot_anterior.json, y usa agentic_ai.resumen_diario() para:

  1. Detectar anomalías con reglas estadísticas (siempre corre, no necesita
     ANTHROPIC_API_KEY): ausentismo crítico, IQP bajo, outliers, datos
     desactualizados, indicadores estimados, deltas vs. la corrida anterior.
  2. Si hay ANTHROPIC_API_KEY, pedirle a Claude un resumen ejecutivo en
     lenguaje natural de esos hallazgos.

Esto es lo que lo hace "agente" y no solo un endpoint: se dispara solo
(GitHub Action, cron, o manualmente) y decide si hay algo para reportar sin
que nadie tenga que preguntarle.

Salidas:
  - data/alertas_agente.json      → último resultado completo (para el dashboard)
  - data/.snapshot_anterior.json  → snapshot para la próxima comparación
  - stdout                        → resumen legible (para logs de CI)
  - exit code 1 si hay algo que amerita mandar el mail de alerta (ver
    decidir_alerta() abajo), exit code 0 en cualquier otro caso.

Criterio de alerta (para no repetir el mismo mail todos los días por una
condición que ya conocés, tipo "estos 10 diputados tienen IQP bajo" — eso no
cambia de un día para el otro y mandarlo a diario sería puro ruido):

  - Hallazgos "puntuales/urgentes" (datos_desactualizados, datos_sin_metadata,
    delta_asistencia_global, delta_composicion) alertan SIEMPRE que aparezcan
    en severidad alta — son eventos, no estados persistentes.
  - Hallazgos "por diputado" (asistencia_critica, iqp_bajo,
    outlier_estadistico_asistencia) solo alertan si son NUEVOS respecto a la
    corrida anterior (el diputado no estaba en la lista de severidad alta
    ayer). Si Menem sigue con IQP 0.0 diez días seguidos, alertó el primer
    día — del segundo en adelante queda solo registrado en
    data/alertas_agente.json, sin spam de mail.

Uso:
    python scripts/agente_monitor.py
    python scripts/agente_monitor.py --data-file data/diputados.json
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agentic_ai import resumen_diario  # noqa: E402

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
SNAPSHOT_FILE = DATA_DIR / ".snapshot_anterior.json"
ALERTAS_FILE = DATA_DIR / "alertas_agente.json"

# Eventos puntuales: alertan siempre que ocurren, no son un estado que se
# arrastra día a día.
TIPOS_SIEMPRE_ALERTA = {
    "datos_desactualizados",
    "datos_sin_metadata",
    "delta_asistencia_global",
    "delta_composicion",
}
# Estados por diputado/entidad: alertan una vez, después quedan como
# "conocidos" hasta que cambien.
TIPOS_SOLO_SI_NUEVO = {
    "asistencia_critica",
    "iqp_bajo",
    "outlier_estadistico_asistencia",
}


def _identidad_hallazgo(h: dict) -> tuple:
    """Clave estable para comparar el mismo hallazgo entre corridas."""
    return (h.get("tipo"), h.get("diputado") or h.get("detalle"))


def decidir_alerta(analisis: dict, alertas_anteriores: dict | None) -> tuple:
    """
    Devuelve (requiere_alerta, hallazgos_relevantes) aplicando el criterio de
    arriba. hallazgos_relevantes es el subconjunto de hallazgos alta que
    justifica el mail — útil para loguear *por qué* se alertó, no solo que
    se alertó.
    """
    ids_alta_anteriores = set()
    if alertas_anteriores:
        analisis_ant = alertas_anteriores.get("analisis", {}) or {}
        for h in analisis_ant.get("hallazgos", []):
            if h.get("severidad") == "alta":
                ids_alta_anteriores.add(_identidad_hallazgo(h))

    relevantes = []
    for h in analisis.get("hallazgos", []):
        if h.get("severidad") != "alta":
            continue
        tipo = h.get("tipo")
        if tipo in TIPOS_SIEMPRE_ALERTA:
            relevantes.append(h)
        elif tipo in TIPOS_SOLO_SI_NUEVO:
            if _identidad_hallazgo(h) not in ids_alta_anteriores:
                relevantes.append(h)
        else:
            # Tipo no clasificado todavía (por si se agregan reglas nuevas
            # más adelante) — mejor pecar de cauteloso y alertar.
            relevantes.append(h)

    return (len(relevantes) > 0, relevantes)


def _cargar_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  No se pudo leer {path}: {e}")
        return None


def main(data_file: str = None) -> int:
    data_path = Path(data_file) if data_file else DATA_DIR / "diputados.json"
    data_actual = _cargar_json(data_path)
    if data_actual is None:
        print(f"❌ No se encontró {data_path} — correr scraper_pipeline.py primero.")
        return 2

    data_anterior = _cargar_json(SNAPSHOT_FILE)
    # Ojo: se carga ANTES de sobreescribir ALERTAS_FILE más abajo, para poder
    # comparar los hallazgos de hoy contra los de la corrida anterior.
    alertas_anteriores = _cargar_json(ALERTAS_FILE)

    print("=" * 60)
    print("=== Agente de Monitoreo — Monitor Legislativo Diputados ===")
    print("=" * 60)
    print(f"Diputados en corrida actual: {len(data_actual.get('diputados', []))}")
    print(f"Snapshot anterior disponible: {'sí' if data_anterior else 'no (primera corrida)'}")

    resultado = resumen_diario(data_actual, data_anterior)
    analisis = resultado["analisis"]

    print(f"\nHallazgos: {analisis['total_hallazgos']} "
          f"(alta: {analisis['por_severidad']['alta']}, "
          f"media: {analisis['por_severidad']['media']}, "
          f"baja: {analisis['por_severidad']['baja']})")
    for h in analisis["hallazgos"]:
        print(f"  [{h['severidad'].upper():5s}] {h['tipo']}: {h['detalle']}")

    if resultado["narrativa"] and resultado["narrativa"].get("disponible"):
        print("\n--- Resumen ejecutivo (Claude) ---")
        print(resultado["narrativa"]["explicacion"])
    elif resultado["narrativa"]:
        print(f"\n(sin resumen narrativo: {resultado['narrativa'].get('motivo')})")

    requiere_alerta, hallazgos_relevantes = decidir_alerta(analisis, alertas_anteriores)
    resultado["alerta"] = {
        "requiere_alerta": requiere_alerta,
        "criterio": "siempre para eventos puntuales; solo si es nuevo para estados por diputado",
        "hallazgos_relevantes": hallazgos_relevantes,
    }
    print(f"\n{'🚨' if requiere_alerta else 'ℹ️ '} "
          f"{'Se dispara el mail de alerta' if requiere_alerta else 'No hace falta mandar mail'} "
          f"({len(hallazgos_relevantes)} hallazgo(s) relevante(s) de {analisis['por_severidad']['alta']} en severidad alta)")
    for h in hallazgos_relevantes:
        print(f"    → {h['tipo']}: {h['detalle']}")

    DATA_DIR.mkdir(exist_ok=True)
    with open(ALERTAS_FILE, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Resultado completo guardado en {ALERTAS_FILE}")

    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(data_actual, f, ensure_ascii=False)
    print(f"✅ Snapshot actualizado en {SNAPSHOT_FILE} (para la próxima comparación)")

    return 1 if requiere_alerta else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente autónomo de monitoreo de anomalías")
    parser.add_argument("--data-file", default=None, help="Ruta a diputados.json (default: data/diputados.json)")
    args = parser.parse_args()
    sys.exit(main(args.data_file))
