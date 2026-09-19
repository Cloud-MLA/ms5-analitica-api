"""Smoke tests. Corre con: pytest -q"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_up():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "up", "service": "ms5-analitica-api"}


def test_openapi_disponible():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    body = response.json()
    assert body["info"]["title"] == "MS5 — Analítico"


def test_los_5_endpoints_analiticos_estan_expuestos():
    """Verifica que los 5 endpoints Q1-Q5 estén registrados en OpenAPI."""
    body = client.get("/openapi.json").json()
    paths = set(body["paths"].keys())
    esperados = {
        "/api/analitica/recursos-mas-fallas",
        "/api/analitica/retraso-promedio",
        "/api/analitica/incidencias-combustible-por-aerolinea",
        "/api/analitica/recaudacion-tuua-por-categoria",
        "/api/analitica/vuelos-hora-punta-retrasados",
    }
    assert esperados.issubset(paths), f"Faltan: {esperados - paths}"
