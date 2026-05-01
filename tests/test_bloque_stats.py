"""
test_bloque_stats.py
====================
Tests unitarios para _bloque_stats() en api_server.py.

Cubre:
  - Agregacion por bloque (cantidad, mujeres, hombres)
  - Calculo de pct_mujeres, asistencia_pct, nape, tasa_aprobacion
  - Manejo de valores None en campos opcionales
  - Entrada vacia
  - Diputado sin bloque cae en 'Sin bloque'
  - Ordenamiento por cantidad descendente
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("REFRESH_TOKEN", "test_token_ci")
os.environ.setdefault("DATA_FILE", "data/diputados.json")

from api_server import _bloque_stats


# --- helpers -----------------------------------------------------------------

def _dip(nombre="GARCIA JUAN", bloque="UCR", genero="M",
         asistencia_pct=80.0, proyectos_presentados=4,
         proyectos_aprobados=1, iqp=0.7, distrito="Buenos Aires"):
    return {
        "nombre": nombre,
        "bloque": bloque,
        "genero": genero,
        "asistencia_pct": asistencia_pct,
        "proyectos_presentados": proyectos_presentados,
        "proyectos_aprobados": proyectos_aprobados,
        "iqp": iqp,
        "distrito": distrito,
    }


# --- tests -------------------------------------------------------------------

class TestBloqueStats:

    def test_lista_vacia_retorna_lista_vacia(self):
        assert _bloque_stats([]) == []

    def test_un_diputado_crea_un_bloque(self):
        result = _bloque_stats([_dip()])
        assert len(result) == 1
        assert result[0]["bloque"] == "UCR"

    def test_cantidad_correcta(self):
        diputados = [_dip(bloque="UCR"), _dip(bloque="UCR"), _dip(bloque="PRO")]
        result = {b["bloque"]: b for b in _bloque_stats(diputados)}
        assert result["UCR"]["cantidad"] == 2
        assert result["PRO"]["cantidad"] == 1

    def test_mujeres_y_hombres_correctos(self):
        diputados = [
            _dip(bloque="UCR", genero="F"),
            _dip(bloque="UCR", genero="M"),
            _dip(bloque="UCR", genero="F"),
        ]
        result = _bloque_stats(diputados)[0]
        assert result["mujeres"] == 2
        assert result["hombres"] == 1

    def test_pct_mujeres_calculado(self):
        diputados = [
            _dip(bloque="UCR", genero="F"),
            _dip(bloque="UCR", genero="M"),
        ]
        result = _bloque_stats(diputados)[0]
        assert result["pct_mujeres"] == 50.0

    def test_asistencia_pct_promedio(self):
        diputados = [
            _dip(bloque="UCR", asistencia_pct=80.0),
            _dip(bloque="UCR", asistencia_pct=60.0),
        ]
        result = _bloque_stats(diputados)[0]
        assert result["asistencia_pct"] == 70.0

    def test_nape_calculado(self):
        """NAPE = 1 - asistencia_pct/100"""
        diputados = [_dip(bloque="UCR", asistencia_pct=80.0)]
        result = _bloque_stats(diputados)[0]
        assert result["nape"] == round(1 - 0.80, 4)

    def test_asistencia_none_no_rompe(self):
        """Diputados sin asistencia_pct no deben contar en el promedio."""
        diputados = [_dip(bloque="UCR", asistencia_pct=None)]
        result = _bloque_stats(diputados)[0]
        assert result["asistencia_pct"] is None
        assert result["nape"] is None

    def test_tasa_aprobacion_calculada(self):
        diputados = [
            _dip(bloque="PRO", proyectos_presentados=10, proyectos_aprobados=2),
            _dip(bloque="PRO", proyectos_presentados=10, proyectos_aprobados=8),
        ]
        result = _bloque_stats(diputados)[0]
        # 10 aprobados / 20 presentados = 50%
        assert result["tasa_aprobacion"] == 50.0

    def test_tasa_aprobacion_none_si_sin_proyectos(self):
        diputados = [_dip(bloque="UxP", proyectos_presentados=0, proyectos_aprobados=0)]
        result = _bloque_stats(diputados)[0]
        assert result["tasa_aprobacion"] is None

    def test_iqp_promedio_calculado(self):
        diputados = [
            _dip(bloque="UCR", iqp=0.6),
            _dip(bloque="UCR", iqp=0.8),
        ]
        result = _bloque_stats(diputados)[0]
        assert result["iqp_promedio"] == round((0.6 + 0.8) / 2, 4)

    def test_iqp_none_no_rompe(self):
        diputados = [_dip(bloque="UCR", iqp=None)]
        result = _bloque_stats(diputados)[0]
        assert result["iqp_promedio"] is None

    def test_sin_bloque_cae_en_sin_bloque(self):
        diputados = [
            {**_dip(), "bloque": None},
        ]
        bloques = {b["bloque"] for b in _bloque_stats(diputados)}
        assert "Sin bloque" in bloques

    def test_ordenado_por_cantidad_descendente(self):
        diputados = (
            [_dip(bloque="UCR")] * 3
            + [_dip(bloque="PRO")] * 5
            + [_dip(bloque="UxP")] * 1
        )
        result = _bloque_stats(diputados)
        cantidades = [b["cantidad"] for b in result]
        assert cantidades == sorted(cantidades, reverse=True)

    def test_distritos_agrupados(self):
        diputados = [
            _dip(bloque="UCR", distrito="Buenos Aires"),
            _dip(bloque="UCR", distrito="Cordoba"),
            _dip(bloque="UCR", distrito="Buenos Aires"),
        ]
        result = _bloque_stats(diputados)[0]
        assert set(result["distritos"]) == {"Buenos Aires", "Cordoba"}

    def test_estructura_resultado(self):
        result = _bloque_stats([_dip()])[0]
        for campo in ("bloque", "cantidad", "mujeres", "hombres", "pct_mujeres",
                      "asistencia_pct", "nape", "proyectos_presentados",
                      "proyectos_aprobados", "tasa_aprobacion", "iqp_promedio", "distritos"):
            assert campo in result, f"Falta campo: {campo}"
