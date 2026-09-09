"""Smoke tests del scaffold. Corre con: pytest -q"""
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


def test_analitica_endpoints_devuelven_501():
    for path, tarea in [
        ("/api/analitica/recursos-mas-fallas", "MS5-03"),
        ("/api/analitica/retraso-promedio", "MS5-04"),
        ("/api/analitica/incidencias-combustible-por-aerolinea", "MS5-05"),
        ("/api/analitica/recaudacion-tuua-por-categoria", "MS5-06"),
        ("/api/analitica/vuelos-hora-punta-retrasados", "MS5-07"),
    ]:
        response = client.get(path)
        assert response.status_code == 501, path
        assert response.json()["detail"]["tarea"] == tarea, path
