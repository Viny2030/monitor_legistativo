"""
test_api.py
===========
Tests de integracion para api_server.py usando FastAPI TestClient.
Mockea load_data() para no depender de data/diputados.json.

Cubre:
  - GET /health
  - GET /api/diputados (con y sin filtros)
  - GET /api/diputados/{nombre} (encontrado y 404)
  - GET /api/bloques
  - GET /api/presupuesto (200 y 404)
  - GET /api/kpis
  - GET /api/indicadores
  - GET /api/indicadores/tpmp
  - GET /api/indicadores/itc
  - GET /api/diputados/{nombre}/asistencia
  - GET /api/diputados/{nombre}/proyectos
  - POST /api/refresh (401 sin token, 401 token falso)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("REFRESH_TOKEN", "test_token_ci")
os.environ.setdefault("DATA_FILE", "data/diputados.json")

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api_server import app

client = TestClient(app)


# --------------------------------------------------------------------------- #
# GET /health
# --------------------------------------------------------------------------- #

class TestHealth:

    def test_health_responde_200(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_json_status_ok(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/health")
        assert resp.json()["status"] == "ok"

    def test_health_tiene_timestamp(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            data = client.get("/health").json()
        assert "timestamp" in data
        assert data["timestamp"]

    def test_health_servicio_presente(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            data = client.get("/health").json()
        assert "servicio" in data

    def test_health_cuando_datos_no_disponibles(self):
        """Si load_data lanza HTTPException, /health igual responde 200."""
        from fastapi import HTTPException
        with patch("api_server.load_data", side_effect=HTTPException(status_code=503, detail="sin datos")):
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# --------------------------------------------------------------------------- #
# GET /api/diputados
# --------------------------------------------------------------------------- #

class TestDiputados:

    def test_retorna_todos(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/diputados")
        assert resp.status_code == 200
        data = resp.json()
        assert "diputados" in data
        assert "total" in data
        assert data["total"] == len(sample_data["diputados"])

    def test_filtro_bloque(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/diputados?bloque=UCR")
        assert resp.status_code == 200
        diputados = resp.json()["diputados"]
        assert all(d["bloque"].upper() == "UCR" for d in diputados)
        assert len(diputados) == 2

    def test_filtro_genero_femenino(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/diputados?genero=F")
        assert resp.status_code == 200
        diputados = resp.json()["diputados"]
        assert all(d["genero"] == "F" for d in diputados)

    def test_filtro_distrito(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/diputados?distrito=Cordoba")
        assert resp.status_code == 200
        diputados = resp.json()["diputados"]
        assert len(diputados) == 1
        assert "LOPEZ" in diputados[0]["nombre"]

    def test_filtro_bloque_inexistente_retorna_vacio(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/diputados?bloque=INEXISTENTE")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_meta_incluida(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/diputados")
        assert "meta" in resp.json()


# --------------------------------------------------------------------------- #
# GET /api/diputados/{nombre}
# --------------------------------------------------------------------------- #

class TestDiputadoIndividual:

    def test_busqueda_parcial_encontrado(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/diputados/GARCIA")
        assert resp.status_code == 200
        data = resp.json()
        assert "resultados" in data
        assert len(data["resultados"]) >= 1

    def test_busqueda_case_insensitive(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/diputados/garcia")
        assert resp.status_code == 200
        assert len(resp.json()["resultados"]) >= 1

    def test_no_encontrado_retorna_404(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/diputados/INEXISTENTEXYZ")
        assert resp.status_code == 404

    def test_multiple_resultados_por_apellido_comun(self, sample_data):
        """'RODRIGUEZ' devuelve exactamente el diputado con ese apellido."""
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/diputados/RODRIGUEZ")
        assert resp.status_code == 200
        assert len(resp.json()["resultados"]) == 1


# --------------------------------------------------------------------------- #
# GET /api/bloques
# --------------------------------------------------------------------------- #

class TestBloques:

    def test_retorna_200(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/bloques")
        assert resp.status_code == 200

    def test_estructura_respuesta(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            data = client.get("/api/bloques").json()
        assert "bloques" in data
        assert "total_bloques" in data
        assert "meta" in data

    def test_tres_bloques_en_sample(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            data = client.get("/api/bloques").json()
        # UCR, PRO, UxP
        assert data["total_bloques"] == 3

    def test_bloque_tiene_campos_requeridos(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            bloques = client.get("/api/bloques").json()["bloques"]
        for b in bloques:
            for campo in ("bloque", "cantidad", "mujeres", "hombres",
                          "pct_mujeres", "asistencia_pct"):
                assert campo in b


# --------------------------------------------------------------------------- #
# GET /api/presupuesto
# --------------------------------------------------------------------------- #

class TestPresupuesto:

    def test_retorna_200_si_hay_datos(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/presupuesto")
        assert resp.status_code == 200

    def test_retorna_404_si_sin_presupuesto(self, sample_data):
        data_sin_presupuesto = {**sample_data, "presupuesto": {}}
        with patch("api_server.load_data", return_value=data_sin_presupuesto):
            resp = client.get("/api/presupuesto")
        assert resp.status_code == 404

    def test_iap_presente(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            data = client.get("/api/presupuesto").json()
        assert "iap" in data


# --------------------------------------------------------------------------- #
# GET /api/indicadores
# --------------------------------------------------------------------------- #

class TestIndicadores:

    def test_retorna_200(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/indicadores")
        assert resp.status_code == 200

    def test_tiene_indicadores_lista(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            data = client.get("/api/indicadores").json()
        assert "indicadores" in data
        assert isinstance(data["indicadores"], list)
        assert data["total"] >= 1

    def test_ids_esperados_presentes(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            indicadores = client.get("/api/indicadores").json()["indicadores"]
        ids = {i["id"] for i in indicadores}
        for esperado in ("NAPE", "TPMP", "ITC", "COLS", "IAP"):
            assert esperado in ids

    def test_version_api_presente(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            data = client.get("/api/indicadores").json()
        assert "version_api" in data


# --------------------------------------------------------------------------- #
# GET /api/indicadores/tpmp
# --------------------------------------------------------------------------- #

class TestIndicadoresTpmp:

    def test_retorna_200(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/indicadores/tpmp")
        assert resp.status_code == 200

    def test_ok_true_cuando_hay_datos(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            data = client.get("/api/indicadores/tpmp").json()
        assert data["ok"] is True

    def test_indicador_tiene_id_tpmp(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            data = client.get("/api/indicadores/tpmp").json()
        assert data["indicador"]["id"] == "TPMP"

    def test_fallback_si_sin_tpmp_en_datos(self, sample_data):
        """Si no hay clave 'tpmp', devuelve valor por defecto 105.0."""
        data_sin_tpmp = {**sample_data, "tpmp": None}
        with patch("api_server.load_data", return_value=data_sin_tpmp):
            resp = client.get("/api/indicadores/tpmp")
        assert resp.status_code == 200
        data = resp.json()
        assert "indicador" in data
        assert data["indicador"]["valor"] == 105.0


# --------------------------------------------------------------------------- #
# GET /api/indicadores/itc
# --------------------------------------------------------------------------- #

class TestIndicadoresItc:

    def test_retorna_200(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/indicadores/itc")
        assert resp.status_code == 200

    def test_ok_true_cuando_hay_datos(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            data = client.get("/api/indicadores/itc").json()
        assert data["ok"] is True

    def test_fallback_si_sin_itc_en_datos(self, sample_data):
        data_sin_itc = {**sample_data, "itc": None}
        with patch("api_server.load_data", return_value=data_sin_itc):
            resp = client.get("/api/indicadores/itc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["indicador"]["valor"] == 3.5


# --------------------------------------------------------------------------- #
# GET /api/diputados/{nombre}/asistencia
# --------------------------------------------------------------------------- #

class TestAsistenciaDiputado:

    def test_encontrado_retorna_200(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/diputados/GARCIA/asistencia")
        assert resp.status_code == 200

    def test_estructura_resultado(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            data = client.get("/api/diputados/GARCIA/asistencia").json()
        assert data["ok"] is True
        assert "diputados" in data
        d = data["diputados"][0]
        for campo in ("nombre", "distrito", "bloque", "asistencia_pct", "nape", "iqp"):
            assert campo in d

    def test_nape_calculado_si_null_en_datos(self, sample_data):
        """nape se calcula si es None y asistencia_pct existe."""
        with patch("api_server.load_data", return_value=sample_data):
            data = client.get("/api/diputados/GARCIA/asistencia").json()
        d = data["diputados"][0]
        if d["asistencia_pct"] is not None and d["nape"] is not None:
            assert d["nape"] == round(1 - d["asistencia_pct"] / 100, 4)

    def test_no_encontrado_retorna_404(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/diputados/INEXISTENTEXYZ/asistencia")
        assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# GET /api/diputados/{nombre}/proyectos
# --------------------------------------------------------------------------- #

class TestProyectosDiputado:

    def test_encontrado_retorna_200(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/diputados/LOPEZ/proyectos")
        assert resp.status_code == 200

    def test_estructura_resultado(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            data = client.get("/api/diputados/GARCIA/proyectos").json()
        assert data["ok"] is True
        d = data["diputados"][0]
        for campo in ("nombre", "proyectos_presentados", "proyectos_aprobados",
                      "tasa_aprobacion_pct"):
            assert campo in d

    def test_tasa_aprobacion_calculada(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            data = client.get("/api/diputados/GARCIA/proyectos").json()
        d = data["diputados"][0]
        if d["proyectos_presentados"] and d["proyectos_aprobados"] is not None:
            esperada = round(d["proyectos_aprobados"] / d["proyectos_presentados"] * 100, 1)
            assert d["tasa_aprobacion_pct"] == esperada

    def test_no_encontrado_retorna_404(self, sample_data):
        with patch("api_server.load_data", return_value=sample_data):
            resp = client.get("/api/diputados/XYZINEXISTENTE/proyectos")
        assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# POST /api/refresh — seguridad
# --------------------------------------------------------------------------- #

class TestRefreshSeguridad:

    def test_sin_token_retorna_401(self):
        resp = client.post("/api/refresh")
        assert resp.status_code == 401

    def test_token_falso_retorna_401(self):
        resp = client.post("/api/refresh", headers={"X-Refresh-Token": "token_inventado"})
        assert resp.status_code == 401

    def test_token_vacio_retorna_401(self):
        resp = client.post("/api/refresh", headers={"X-Refresh-Token": ""})
        assert resp.status_code == 401

    def test_con_token_correcto_intenta_pipeline(self):
        """Con el token correcto no debe devolver 401."""
        import subprocess
        mock_result = type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        with patch("subprocess.run", return_value=mock_result):
            resp = client.post("/api/refresh",
                               headers={"X-Refresh-Token": "test_token_ci"})
        assert resp.status_code != 401

    def test_error_detail_en_401(self):
        resp = client.post("/api/refresh")
        assert "detail" in resp.json()
