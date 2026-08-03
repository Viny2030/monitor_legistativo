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
  - exit code 1 si hay hallazgos de severidad "alta" (para que el workflow
    decida si dispara una notificación), exit code 0 en cualquier otro caso.

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

    DATA_DIR.mkdir(exist_ok=True)
    with open(ALERTAS_FILE, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Resultado completo guardado en {ALERTAS_FILE}")

    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(data_actual, f, ensure_ascii=False)
    print(f"✅ Snapshot actualizado en {SNAPSHOT_FILE} (para la próxima comparación)")

    return 1 if analisis["por_severidad"]["alta"] > 0 else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente autónomo de monitoreo de anomalías")
    parser.add_argument("--data-file", default=None, help="Ruta a diputados.json (default: data/diputados.json)")
    args = parser.parse_args()
    sys.exit(main(args.data_file))
