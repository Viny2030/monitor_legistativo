"""Red de coincidencia de votos (red_votos.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import red_votos as rv  # noqa: E402


def _votaciones(n=25):
    # A y B votan siempre igual; C vota igual que A salvo en 5; D siempre al revés de A.
    out = []
    for i in range(n):
        a = "si" if i % 2 else "no"
        c = a if i >= 5 else ("no" if a == "si" else "si")
        d = "no" if a == "si" else "si"
        out.append({"Pérez, Ana": a, "Gómez, Bruno": a, "Ríos, Carla": c, "Díaz, Dario": d,
                    "Sosa, Eva": "ausente"})
    return out


BLOQUES = {"PEREZ ANA": "Azul", "GOMEZ BRUNO": "Azul", "RIOS CARLA": "Rojo", "DIAZ DARIO": "Rojo"}


def test_normalizar_y_codigos():
    assert rv.normalizar_nombre("Ríos, Carla María") == "RIOS CARLA MARIA"
    assert rv.codigo_voto("Afirmativo") == rv.codigo_voto("si") == 1
    assert rv.codigo_voto("negativo") == 2 and rv.codigo_voto("abstención") == 3
    assert rv.codigo_voto("ausente") == 0 and rv.codigo_voto("presidente") == 0


def test_coincidencias_y_aristas():
    red = rv.construir_red(_votaciones(), BLOQUES, k=1)
    por = {n["id"]: n for n in red["nodos"]}
    # Sosa nunca votó: queda sin coincidencias y fuera de la nómina actual
    assert por["Sosa, Eva"]["bloque"] == rv.SIN_BLOQUE and por["Sosa, Eva"]["votos"] == 0
    a = next(x for x in red["aristas"] if {x["from"], x["to"]} == {"Pérez, Ana", "Gómez, Bruno"})
    assert a["coincidencia"] == 100.0 and not a["entre_bloques"]
    c = next(x for x in red["aristas"] if "Ríos, Carla" in (x["from"], x["to"]) and x["entre_bloques"])
    assert c["entre_bloques"] and c["coincidencia"] == 80.0  # 20 de 25
    assert por["Ríos, Carla"]["mas_cercano_otro_bloque"]["coincidencia"] == 80.0
    assert por["Díaz, Dario"]["coincidencia_otros"] < 25


def test_minimo_de_votaciones_en_comun():
    red = rv.construir_red(_votaciones(10), BLOQUES, k=3, min_comunes=20)
    assert red["aristas"] == []


def test_bloque_por_apellido_y_primer_nombre():
    assert rv.buscar_bloque("Ríos, Carla Beatriz", BLOQUES) == "Rojo"
    assert rv.buscar_bloque("Nadie, Otro", BLOQUES) is None


def test_cache():
    c, llamadas = rv.Cache(60), []
    f = lambda: llamadas.append(1) or {"ok": True}  # noqa: E731
    assert c.obtener("x", f) == c.obtener("x", f) == {"ok": True}
    assert len(llamadas) == 1
    c.obtener("y", f)
    assert len(llamadas) == 2


# ── Endpoint GET /api/red-votos (api_server.py) ───────────────────────────────
def _cliente():
    os.environ.setdefault("REFRESH_TOKEN", "test_token_ci")
    import api_server
    from fastapi.testclient import TestClient
    api_server._RED_CACHE = None
    return api_server, TestClient(api_server.app)


def test_endpoint_red_votos(monkeypatch):
    api_server, client = _cliente()
    monkeypatch.setattr(api_server, "_actas_diputados", lambda anio: _votaciones())
    monkeypatch.setattr(api_server, "load_data", lambda: {"diputados": [
        {"nombre": "Pérez, Ana", "bloque": "Azul"}, {"nombre": "Gómez, Bruno", "bloque": "Azul"},
        {"nombre": "Ríos, Carla", "bloque": "Rojo"}, {"nombre": "Díaz, Dario", "bloque": "Rojo"}]})
    r = client.get("/api/red-votos?k=1")
    assert r.status_code == 200
    red = r.json()
    assert red["resumen"]["legisladores"] == 5 and red["resumen"]["k"] == 1
    assert {n["id"]: n["bloque"] for n in red["nodos"]}["Ríos, Carla"] == "Rojo"


def test_endpoint_red_votos_fuente_caida(monkeypatch):
    api_server, client = _cliente()

    def falla(anio):
        raise RuntimeError("timeout")
    monkeypatch.setattr(api_server, "_actas_diputados", falla)
    r = client.get("/api/red-votos")
    assert r.status_code == 503 and "Diputados" in r.json()["detail"]
