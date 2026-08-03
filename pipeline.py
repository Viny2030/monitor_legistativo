"""
pipeline.py — DEPRECATED, no usar directamente.

Este archivo era una copia desactualizada de scripts/cruzar_presupuesto.py
(mismo contenido, docstring incluido) con un bug: su main() intentaba
`tc, tc_info = obtener_tipo_cambio()` pero esa función siempre devolvió un
solo float, nunca una tupla — es decir, `python pipeline.py` rompía con
TypeError en cualquier ejecución real. No estaba importado desde ningún
otro módulo del repo ni referenciado en workflows/README.

Se deja como shim que delega en la versión real y mantenida
(scripts/cruzar_presupuesto.py) para no romper a quien todavía tenga el
hábito de correr `python pipeline.py`. El código fuente vive en un solo
lugar de ahora en más.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scripts.cruzar_presupuesto import main  # noqa: E402

if __name__ == "__main__":
    print("⚠️  pipeline.py está deprecado — delegando en scripts/cruzar_presupuesto.py")
    main()
