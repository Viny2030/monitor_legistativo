"""Tests de scripts/actualizar_nomina_html.py (sin red)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import actualizar_nomina_html as anh  # noqa: E402

HTML = (
    "<p>12 indicadores — datos al 27 de marzo de 2026</p>\n"
    "<script>\n"
    "const DIPUTADOS = [\n"
    '  {nombre:"Viejo, Uno",distrito:"CHACO",bloque:"BLOQUE VIEJO",mandato:"2023-2027",asistencia:97.5}\n'
    "];\n"
    "const total = DIPUTADOS.length;\n"
    "</script>\n"
)

DIPUTADOS = [
    {"nombre": "Nuevo, Dos", "distrito": "SALTA", "bloque": 'BLOQUE "NUEVO"',
     "mandato_hasta": "2025-2029", "asistencia_pct": 93.333, "genero": "F"},
    {"nombre": "Nuevo, Tres", "distrito": "JUJUY", "bloque": "OTRO",
     "mandato_hasta": "2023-2027", "asistencia_pct": None, "genero": "M"},
]


def test_fecha_larga():
    assert anh.fecha_larga("2026-11-06T09:30:01.379160") == "6 de noviembre de 2026"


def test_reescribe_array_y_fecha_con_los_campos_de_la_pagina():
    nuevo, reescrito = anh.actualizar_pagina(HTML, DIPUTADOS, "6 de noviembre de 2026")
    assert reescrito
    assert "datos al 6 de noviembre de 2026" in nuevo and "27 de marzo" not in nuevo
    assert "Viejo, Uno" not in nuevo
    # mismos campos que la fila original; genero no estaba, no se agrega
    assert '{nombre:"Nuevo, Dos",distrito:"SALTA",bloque:"BLOQUE \\"NUEVO\\"",mandato:"2025-2029",asistencia:93.3}' in nuevo
    # asistencia sin dato se omite (la página la trata como ausente)
    assert '{nombre:"Nuevo, Tres",distrito:"JUJUY",bloque:"OTRO",mandato:"2023-2027"}' in nuevo
    assert "genero" not in nuevo
    # el resto del script queda intacto
    assert "const total = DIPUTADOS.length;" in nuevo


def test_pagina_sin_array_solo_cambia_la_fecha():
    html = "<p>257 diputados · datos al 27 de marzo de 2026</p><script>let DIPUTADOS = [];</script>"
    nuevo, reescrito = anh.actualizar_pagina(html, DIPUTADOS, "6 de noviembre de 2026")
    assert not reescrito
    assert nuevo == html.replace("27 de marzo de 2026", "6 de noviembre de 2026")


def test_respeta_finales_de_linea_crlf():
    html = HTML.replace("\n", "\r\n")
    nuevo, _ = anh.actualizar_pagina(html, DIPUTADOS, "6 de noviembre de 2026")
    assert "\n" not in nuevo.replace("\r\n", "")
