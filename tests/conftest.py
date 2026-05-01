"""
conftest.py
===========
Fixtures compartidas para los tests del Monitor Legislativo.
"""
import os
import pytest

os.environ.setdefault("REFRESH_TOKEN", "test_token_ci")
os.environ.setdefault("DATA_FILE", "data/diputados.json")


@pytest.fixture
def sample_data():
    """Payload completo que simula data/diputados.json."""
    return {
        "meta": {
            "ultima_actualizacion": "2026-05-01T00:00:00",
            "anio": 2026,
            "fuente": "HCDN"
        },
        "diputados": [
            {
                "nombre": "GARCIA JUAN",
                "distrito": "Buenos Aires",
                "bloque": "UCR",
                "genero": "M",
                "asistencia_pct": 80.0,
                "proyectos_presentados": 6,
                "proyectos_aprobados": 2,
                "iqp": 0.72,
                "nape": None,
            },
            {
                "nombre": "LOPEZ MARIA",
                "distrito": "Cordoba",
                "bloque": "UCR",
                "genero": "F",
                "asistencia_pct": 90.0,
                "proyectos_presentados": 4,
                "proyectos_aprobados": 1,
                "iqp": 0.85,
                "nape": None,
            },
            {
                "nombre": "PEREZ CARLOS",
                "distrito": "Santa Fe",
                "bloque": "PRO",
                "genero": "M",
                "asistencia_pct": 70.0,
                "proyectos_presentados": 2,
                "proyectos_aprobados": 0,
                "iqp": 0.50,
                "nape": None,
            },
            {
                "nombre": "RODRIGUEZ ANA",
                "distrito": "Buenos Aires",
                "bloque": "PRO",
                "genero": "F",
                "asistencia_pct": 95.0,
                "proyectos_presentados": 8,
                "proyectos_aprobados": 3,
                "iqp": 0.91,
                "nape": None,
            },
            {
                "nombre": "MARTINEZ LUIS",
                "distrito": "Mendoza",
                "bloque": "UxP",
                "genero": "M",
                "asistencia_pct": None,
                "proyectos_presentados": None,
                "proyectos_aprobados": 0,
                "iqp": None,
                "nape": None,
            },
        ],
        "presupuesto": {
            "iap": 0.87,
            "fuente": "ONP / Presupuesto Abierto",
            "anio": 2026,
        },
        "tpmp": {
            "valor": 105.0,
            "fuente": "SIL",
            "n_proyectos": 120,
            "mediana_dias": 90,
            "advertencia": None,
        },
        "itc": {
            "id": "ITC",
            "valor": 3.5,
            "fuente": "HCDN actas",
            "horas_comision": 800,
            "horas_pleno": 230,
            "n_reuniones": 42,
            "advertencia": None,
        },
    }


@pytest.fixture
def sample_diputados(sample_data):
    """Solo la lista de diputados."""
    return sample_data["diputados"]
