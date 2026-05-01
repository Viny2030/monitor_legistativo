"""
test_kpis.py
============
Tests unitarios para la logica de KPIs en api_server.py.
Prueba los calculos de NAPE, TPMP, COLS, paridad y RLS
usando el endpoint /api/kpis con TestClient y mock de load_data.
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


def _data_with(diputados, presupuesto=None):
    return {
        "meta": {"ultima_actualizacion": "2026-05-01T00:00:00"},
        "diputados": diputados,
        "presupuesto": presupuesto or {},
    }


class TestKpisNape:

    def test_nape_calculado_correctamente(self):
        """NAPE = 1 - promedio(asistencias) / 100"""
        diputados = [
            {"asistencia_pct": 80.0, "proyectos_presentados": 1, "proyectos_aprobados": 1, "iqp": 0.5},
            {"asistencia_pct": 60.0, "proyectos_presentados": 1, "proyectos_aprobados": 0, "iqp": 0.5},
        ]
        with patch("api_server.load_data", return_value=_data_with(diputados)):
            resp = client.get("/api/kpis")
        assert resp.status_code == 200
        data = resp.json()
        esperado = round(1 - (80.0 + 60.0) / 2 / 100, 4)
        assert data["nape"] == esperado

    def test_nape_none_si_sin_asistencias(self):
        diputados = [
            {"asistencia_pct": None, "proyectos_presentados": 1, "proyectos_aprobados": 0, "iqp": None}
        ]
        with patch("api_server.load_data", return_value=_data_with(diputados)):
            resp = client.get("/api/kpis")
        assert resp.json()["nape"] is None

    def test_nape_ignora_none_en_asistencia(self):
        """Solo cuenta diputados con asistencia_pct no nula."""
        diputados = [
            {"asistencia_pct": 100.0, "proyectos_presentados": 0, "proyectos_aprobados": 0, "iqp": None},
            {"asistencia_pct": None, "proyectos_presentados": 0, "proyectos_aprobados": 0, "iqp": None},
        ]
        with patch("api_server.load_data", return_value=_data_with(diputados)):
            resp = client.get("/api/kpis")
        assert resp.json()["nape"] == 0.0


class TestKpisTpmp:

    def test_tpmp_es_promedio_proyectos(self):
        diputados = [
            {"asistencia_pct": 80.0, "proyectos_presentados": 4, "proyectos_aprobados": 1, "iqp": 0.5},
            {"asistencia_pct": 70.0, "proyectos_presentados": 6, "proyectos_aprobados": 1, "iqp": 0.5},
        ]
        with patch("api_server.load_data", return_value=_data_with(diputados)):
            resp = client.get("/api/kpis")
        assert resp.json()["tpmp"] == 5.0

    def test_tpmp_none_si_sin_datos(self):
        diputados = [
            {"asistencia_pct": 80.0, "proyectos_presentados": None, "proyectos_aprobados": 0, "iqp": None}
        ]
        with patch("api_server.load_data", return_value=_data_with(diputados)):
            resp = client.get("/api/kpis")
        assert resp.json()["tpmp"] is None


class TestKpisCols:

    def test_cols_porcentaje_con_aprobado(self):
        """COLS = % diputados con al menos 1 proyecto aprobado."""
        diputados = [
            {"asistencia_pct": 80.0, "proyectos_presentados": 3, "proyectos_aprobados": 2, "iqp": 0.5},
            {"asistencia_pct": 80.0, "proyectos_presentados": 3, "proyectos_aprobados": 0, "iqp": 0.5},
            {"asistencia_pct": 80.0, "proyectos_presentados": 3, "proyectos_aprobados": 1, "iqp": 0.5},
            {"asistencia_pct": 80.0, "proyectos_presentados": 3, "proyectos_aprobados": 0, "iqp": 0.5},
        ]
        with patch("api_server.load_data", return_value=_data_with(diputados)):
            resp = client.get("/api/kpis")
        # 2 de 4 = 50%
        assert resp.json()["cols"] == 50.0

    def test_cols_cero_si_nadie_aprobado(self):
        diputados = [
            {"asistencia_pct": 80.0, "proyectos_presentados": 2, "proyectos_aprobados": 0, "iqp": 0.5}
        ]
        with patch("api_server.load_data", return_value=_data_with(diputados)):
            resp = client.get("/api/kpis")
        assert resp.json()["cols"] == 0.0


class TestKpisParidad:

    def test_paridad_correcta(self):
        diputados = [
            {"genero": "F", "asistencia_pct": 80.0, "proyectos_presentados": 1, "proyectos_aprobados": 0, "iqp": None},
            {"genero": "M", "asistencia_pct": 80.0, "proyectos_presentados": 1, "proyectos_aprobados": 0, "iqp": None},
            {"genero": "M", "asistencia_pct": 80.0, "proyectos_presentados": 1, "proyectos_aprobados": 0, "iqp": None},
        ]
        with patch("api_server.load_data", return_value=_data_with(diputados)):
            resp = client.get("/api/kpis")
        paridad = resp.json()["paridad"]
        assert paridad["mujeres"] == 1
        assert paridad["hombres"] == 2
        assert paridad["pct_mujeres"] == round(1 / 3 * 100, 1)

    def test_estructura_paridad(self):
        diputados = [
            {"genero": "F", "asistencia_pct": 80.0, "proyectos_presentados": 1, "proyectos_aprobados": 1, "iqp": 0.7}
        ]
        with patch("api_server.load_data", return_value=_data_with(diputados)):
            resp = client.get("/api/kpis")
        assert "mujeres" in resp.json()["paridad"]
        assert "hombres" in resp.json()["paridad"]
        assert "pct_mujeres" in resp.json()["paridad"]


class TestKpisIap:

    def test_iap_tomado_del_presupuesto(self):
        diputados = [
            {"asistencia_pct": 80.0, "proyectos_presentados": 2, "proyectos_aprobados": 1, "iqp": 0.7}
        ]
        presupuesto = {"iap": 0.87}
        with patch("api_server.load_data", return_value=_data_with(diputados, presupuesto)):
            resp = client.get("/api/kpis")
        assert resp.json()["iap"] == 0.87

    def test_iap_none_si_sin_presupuesto(self):
        diputados = [
            {"asistencia_pct": 80.0, "proyectos_presentados": 2, "proyectos_aprobados": 1, "iqp": 0.7}
        ]
        with patch("api_server.load_data", return_value=_data_with(diputados, presupuesto={})):
            resp = client.get("/api/kpis")
        assert resp.json()["iap"] is None


class TestKpisRls:

    def test_rls_proporcional_a_total(self):
        """RLS = n / 46.6"""
        diputados = [
            {"asistencia_pct": 80.0, "proyectos_presentados": 1, "proyectos_aprobados": 0, "iqp": None}
        ] * 10
        with patch("api_server.load_data", return_value=_data_with(diputados)):
            resp = client.get("/api/kpis")
        assert resp.json()["rls"] == round(10 / 46.6, 2)


class TestKpisGeneral:

    def test_estructura_respuesta(self):
        diputados = [
            {"asistencia_pct": 80.0, "proyectos_presentados": 2,
             "proyectos_aprobados": 1, "iqp": 0.7, "genero": "M"}
        ]
        with patch("api_server.load_data", return_value=_data_with(diputados)):
            resp = client.get("/api/kpis")
        assert resp.status_code == 200
        data = resp.json()
        for campo in ("total_diputados", "nape", "tpmp", "cols", "iap",
                      "iqp_global", "rls", "paridad", "meta"):
            assert campo in data, f"Falta campo: {campo}"

    def test_sin_diputados_retorna_503(self):
        with patch("api_server.load_data", return_value=_data_with([])):
            resp = client.get("/api/kpis")
        assert resp.status_code == 503
