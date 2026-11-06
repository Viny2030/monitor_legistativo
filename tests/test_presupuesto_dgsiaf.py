"""STEP 4 de scraper_pipeline: presupuesto HCDN desde Presupuesto Abierto (sin red)."""
import io
import zipfile

import scraper_pipeline as sp

CAB = ("jurisdiccion_id,servicio_id,servicio_desc,credito_presupuestado,credito_vigente,"
       "credito_devengado,ultima_actualizacion_fecha\n")


def _zip(filas: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("credito-anual.csv", ("\ufeff" + CAB + filas).encode("utf-8"))
    return buf.getvalue()


class _Res:
    def __init__(self, status, content=b""):
        self.status_code, self.content = status, content


def test_suma_solo_el_saf_313_y_usa_el_ejercicio_cerrado_para_iap(monkeypatch):
    actual = _zip('1,313,HCDN,"100,5","200,0","150,0",Última actualización del ejercicio 2026: 04 Noviembre 2026.\n'
                  '1,313,HCDN,"0,5","50,0","25,0",Última actualización del ejercicio 2026: 04 Noviembre 2026.\n'
                  '1,312,Senado,"999","999","999",x\n'
                  '20,313,Otro,"999","999","999",x\n')
    cerrado = _zip('1,313,HCDN,"90","100","98",Última actualización del ejercicio 2025: 31 Diciembre 2025.\n')

    def get(url, **_):
        return _Res(200, actual if "/2026/" in url else cerrado)

    monkeypatch.setattr(sp.requests, "get", get)
    monkeypatch.setattr(sp, "datetime", type("D", (), {"now": staticmethod(lambda: __import__("datetime").datetime(2026, 11, 6))}))
    r = sp.scrape_presupuesto()
    assert r["credito_presupuestado_m"] == 101.0
    assert r["credito_vigente_m"] == 250.0
    assert r["devengado_m"] == 175.0
    assert r["ejecucion_al_corte"] == 0.7
    assert r["corte"] == "04 Noviembre 2026"
    assert r["iap"] == 0.98 and r["iap_ejercicio"] == 2025


def test_sin_fuente_vuelve_al_valor_historico(monkeypatch):
    monkeypatch.setattr(sp.requests, "get", lambda url, **_: _Res(404))
    r = sp.scrape_presupuesto()
    assert r["iap"] == 0.951 and r["fuente"] == "historico OPC 2024"
    assert r["credito_vigente_m"] is None
