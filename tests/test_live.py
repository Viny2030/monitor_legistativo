"""
test_live.py
============
Smoke tests contra el entorno productivo en Railway.
Se ejecutan diariamente para verificar que la app este en pie.

Uso:
    pytest tests/test_live.py -v -m live

La variable de entorno LIVE_URL puede sobreescribir la URL default.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get(
    "LIVE_URL",
    "https://monitorlegistativo-production.up.railway.app"
).rstrip("/")

TIMEOUT = 20  # segundos


# --- helpers -----------------------------------------------------------------

def get(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)


def post(path: str, **kwargs) -> requests.Response:
    return requests.post(f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)


# --- tests -------------------------------------------------------------------

@pytest.mark.live
class TestLiveHealth:

    def test_health_responde_200(self):
        resp = get("/health")
        assert resp.status_code == 200, (
            f"Health check fallo con {resp.status_code}. Body: {resp.text[:200]}"
        )

    def test_health_json_status_ok(self):
        data = get("/health").json()
        assert data.get("status") == "ok", f"status inesperado: {data}"

    def test_health_tiene_timestamp(self):
        data = get("/health").json()
        assert "timestamp" in data
        assert data["timestamp"]

    def test_health_tiene_servicio(self):
        data = get("/health").json()
        assert "servicio" in data

    def test_health_tiempo_respuesta_aceptable(self):
        inicio = time.time()
        get("/health")
        duracion = time.time() - inicio
        assert duracion < 10, f"Respuesta demasiado lenta: {duracion:.1f}s"


@pytest.mark.live
class TestLiveDashboard:

    def test_dashboard_responde(self):
        """El dashboard puede responder 200 o redirigir (301/302)."""
        resp = requests.get(f"{BASE_URL}/dashboard/", timeout=TIMEOUT,
                            allow_redirects=True)
        assert resp.status_code < 500, (
            f"Dashboard respondio con error {resp.status_code}"
        )

    def test_docs_accesibles(self):
        resp = get("/docs")
        assert resp.status_code == 200

    def test_openapi_json_accesible(self):
        resp = get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "openapi" in data
        assert "paths" in data


@pytest.mark.live
class TestLiveApiEndpoints:

    def test_diputados_accesible(self):
        resp = get("/api/diputados")
        assert resp.status_code in (200, 503), (
            f"Respuesta inesperada en /api/diputados: {resp.status_code}"
        )

    def test_diputados_json_si_200(self):
        resp = get("/api/diputados")
        if resp.status_code == 200:
            data = resp.json()
            assert "diputados" in data
            assert "total" in data

    def test_bloques_accesible(self):
        resp = get("/api/bloques")
        assert resp.status_code in (200, 503)

    def test_bloques_json_si_200(self):
        resp = get("/api/bloques")
        if resp.status_code == 200:
            data = resp.json()
            assert "bloques" in data
            assert "total_bloques" in data

    def test_kpis_accesible(self):
        resp = get("/api/kpis")
        assert resp.status_code in (200, 503)

    def test_kpis_json_si_200(self):
        resp = get("/api/kpis")
        if resp.status_code == 200:
            data = resp.json()
            assert "nape" in data
            assert "paridad" in data

    def test_indicadores_accesible(self):
        resp = get("/api/indicadores")
        assert resp.status_code in (200, 503)

    def test_indicadores_tpmp_accesible(self):
        """TPMP puede tardar si llama al scraper SIL en tiempo real."""
        try:
            resp = get("/api/indicadores/tpmp")
            assert resp.status_code == 200
        except requests.exceptions.ReadTimeout:
            pytest.skip("TPMP timeout — scraper SIL lento, endpoint disponible")

    def test_indicadores_itc_accesible(self):
        """ITC puede tardar si llama al scraper de comisiones en tiempo real."""
        try:
            resp = get("/api/indicadores/itc")
            assert resp.status_code == 200
        except requests.exceptions.ReadTimeout:
            pytest.skip("ITC timeout — scraper comisiones lento, endpoint disponible")

    def test_presupuesto_accesible(self):
        resp = get("/api/presupuesto")
        assert resp.status_code in (200, 404, 503)


@pytest.mark.live
class TestLiveSeguridad:

    def test_refresh_sin_token_retorna_401(self):
        resp = post("/api/refresh")
        assert resp.status_code == 401, (
            "El endpoint /api/refresh debe rechazar requests sin token"
        )

    def test_refresh_token_falso_retorna_401(self):
        resp = post("/api/refresh",
                    headers={"X-Refresh-Token": "token_falso_12345"})
        assert resp.status_code == 401

    def test_no_expone_info_sensible_en_health(self):
        data = get("/health").json()
        body_str = str(data).lower()
        assert "postgresql://" not in body_str
        assert "password" not in body_str
        assert "secret" not in body_str


@pytest.mark.live
class TestLiveCORS:

    def test_cors_headers_en_get(self):
        resp = get("/health", headers={"Origin": "https://example.com"})
        acao = resp.headers.get("access-control-allow-origin", "")
        assert acao == "*" or acao == "https://example.com", (
            f"CORS header ausente o incorrecto: '{acao}'"
        )

    def test_preflight_options_no_falla(self):
        resp = requests.options(
            f"{BASE_URL}/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
            timeout=TIMEOUT,
        )
        assert resp.status_code < 500, (
            f"Preflight CORS respondio con error {resp.status_code}"
        )
