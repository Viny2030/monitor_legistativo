"""
Tests de los arreglos 2026-10-09: asistencia desde el PDF ESTADISTICAS de la
HCDN, match de nombres (apellidos repetidos) y límites del asistente de IA.
No hacen requests reales.
"""
import scraper_pipeline as sp

PDF_TEXTO = """Dirección de Coordinación de Labor Parlamentaria
Período 144
01/03/2026 al 09/09/2026
BLOQUE DIPUTADO/A P A L M.O.
UNIÓN POR LA PATRIA Aguirre, Hilda 5 2 0 0
Encuentro Federal Avila, Jorge Antonio 5 2 0 0
UNIÓN POR LA PATRIA Avila, Fernanda 4 2 1 0
UNIÓN POR LA PATRIA Araujo Hernández, Jorge Neri 7 0 0 0
(5) Dip. PRADES reemplazó al Dip. ACEVEDO (10 PRESENTE - 1 AUSENTE
"""


def test_parser_lee_conteos_no_porcentaje():
    filas = sp._parsear_estadisticas_asistencia(PDF_TEXTO)
    assert len(filas) == 4
    f = filas[0]
    assert (f["p"], f["a"], f["l"], f["mo"]) == (5, 2, 0, 0)
    assert "Aguirre, Hilda" in f["texto"]


def test_match_apellido_repetido_usa_nombre():
    filas = sp._parsear_estadisticas_asistencia(PDF_TEXTO)
    jorge = sp._buscar_fila_diputado("Avila, Jorge Antonio", filas)
    fernanda = sp._buscar_fila_diputado("Ávila, Fernanda", filas)
    assert jorge and "Jorge" in jorge["texto"]
    assert fernanda and "Fernanda" in fernanda["texto"]


def test_match_tildes_y_apellido_compuesto():
    filas = sp._parsear_estadisticas_asistencia(PDF_TEXTO)
    assert sp._buscar_fila_diputado("Araujo Hernandez, Jorge Neri", filas)
    assert sp._buscar_fila_diputado("Inexistente, Fulano", filas) is None


def test_porcentaje_como_la_hcdn(monkeypatch):
    """asistencia = presentes / total de sesiones (criterio de PORCENTAJE.pdf)."""
    import io

    class FakePage:
        def extract_text(self):
            return PDF_TEXTO + "\n".join(f"BLOQUE Relleno{i}, Nombre 7 0 0 0" for i in range(100))

    class FakePDF:
        pages = [FakePage()]
        def __enter__(self): return self
        def __exit__(self, *a): return False

    class FakeResp:
        status_code = 200
        content = b"%PDF-1.4 fake"

    import pdfplumber
    monkeypatch.setattr(pdfplumber, "open", lambda *_a, **_k: FakePDF())
    monkeypatch.setattr(sp, "_urls_pdf_asistencia", lambda: ["https://x/ESTADISTICAS.pdf"])
    monkeypatch.setattr(sp.requests, "get", lambda *a, **k: FakeResp())

    dips = [{"nombre": "Aguirre, Hilda"}, {"nombre": "Avila, Fernanda"}]
    sp.scrape_asistencia(dips)
    assert dips[0]["asistencia_pct"] == 71.4           # 5 / 7
    assert dips[1]["asistencia_pct"] == 57.1           # 4 / 7
    assert dips[1]["asistencia_detalle"]["licencias"] == 1
    assert sp.ASISTENCIA_META["fuente_asistencia_actualizados"] == "2/2"


def test_asistencia_conserva_valores_si_no_hay_pdf(monkeypatch):
    monkeypatch.setattr(sp, "_urls_pdf_asistencia", lambda: [])
    previos = {"Aguirre, Hilda": {"asistencia_pct": 71.4, "nape": 0.286,
                                  "asistencia_detalle": {"presentes": 5}}}
    dips = [{"nombre": "Aguirre, Hilda", "asistencia_pct": None}]
    sp.scrape_asistencia(dips, previos)
    assert dips[0]["asistencia_pct"] == 71.4


def test_clave_autor_normaliza():
    assert sp._clave_autor("Almirón, Lisandro") == ("ALMIRON", "LISANDRO")
    assert sp._clave_autor("PIETRAGALLA CORTI, HORACIO") == ("PIETRAGALLA CORTI", "HORACIO")


def test_ia_limite_por_ip():
    import api_server as api
    api._ia_por_ip.clear(); api._ia_global.clear()
    ip = "203.0.113.7"
    for _ in range(api.IA_LIMITE_POR_IP_HORA):
        assert api._ia_registrar(ip) is None
    assert "límite" in api._ia_registrar(ip)
    assert api._ia_registrar("203.0.113.8") is None   # otra IP sigue pudiendo
    api._ia_por_ip.clear(); api._ia_global.clear()
