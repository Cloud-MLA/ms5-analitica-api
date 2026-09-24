"""Tests para MS5-02..07 usando MagicMock del cliente boto3 Athena.

Estos tests NO requieren AWS ni credenciales — inyectan un mock en
`athena_client._boto` que simula start_query_execution → poll → results.
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import queries
from app.services import athena as athena_module
from app.services.athena import AthenaQueryError, athena_client

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers para construir mocks realistas
# ---------------------------------------------------------------------------
def _fake_page(columns: list[tuple[str, str]], rows_data: list[list[str | None]]):
    """Construye una página en el formato que devuelve get_query_results."""
    header = {"Data": [{"VarCharValue": name} for name, _ in columns]}
    data_rows = []
    for r in rows_data:
        cells = []
        for v in r:
            if v is None:
                cells.append({})  # NULL en Athena → dict sin VarCharValue
            else:
                cells.append({"VarCharValue": v})
        data_rows.append({"Data": cells})
    return {
        "ResultSet": {
            "ResultSetMetadata": {
                "ColumnInfo": [{"Name": n, "Type": t} for n, t in columns],
            },
            "Rows": [header] + data_rows,
        }
    }


def _mock_boto_success(columns, rows):
    """MagicMock boto3 Athena que responde con éxito."""
    m = MagicMock()
    m.start_query_execution.return_value = {"QueryExecutionId": "test-query-id"}
    m.get_query_execution.return_value = {
        "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
    }
    paginator = MagicMock()
    paginator.paginate.return_value = [_fake_page(columns, rows)]
    m.get_paginator.return_value = paginator
    return m


def _mock_boto_failed(reason: str = "syntax error"):
    m = MagicMock()
    m.start_query_execution.return_value = {"QueryExecutionId": "test-query-id"}
    m.get_query_execution.return_value = {
        "QueryExecution": {
            "Status": {"State": "FAILED", "StateChangeReason": reason},
        }
    }
    return m


@pytest.fixture(autouse=True)
def _reset_cache_and_boto():
    """Cada test empieza con cache limpio y sin cliente boto instanciado."""
    athena_client._cache.clear()
    athena_client._boto = None
    yield
    athena_client._cache.clear()
    athena_client._boto = None


# ---------------------------------------------------------------------------
# Tests de la capa Athena
# ---------------------------------------------------------------------------
def test_execute_query_devuelve_rows_tipadas():
    athena_client._boto = _mock_boto_success(
        columns=[("id", "bigint"), ("nombre", "varchar"), ("tarifa", "decimal")],
        rows=[["1", "Nacional", "12.50"], ["2", "Internacional", "38.45"]],
    )
    import asyncio
    rows = asyncio.run(athena_client.execute_query("SELECT * FROM x"))

    assert len(rows) == 2
    assert rows[0] == {"id": 1, "nombre": "Nacional", "tarifa": 12.5}
    assert rows[1] == {"id": 2, "nombre": "Internacional", "tarifa": 38.45}
    # Los ints y decimals deben venir tipados, no como string
    assert isinstance(rows[0]["id"], int)
    assert isinstance(rows[0]["tarifa"], float)


def test_execute_query_failed_lanza_error():
    athena_client._boto = _mock_boto_failed("Table 'x' does not exist")
    import asyncio
    with pytest.raises(AthenaQueryError) as exc_info:
        asyncio.run(athena_client.execute_query("SELECT * FROM x"))
    assert "Table 'x' does not exist" in str(exc_info.value)


def test_cache_evita_llamada_repetida():
    mock = _mock_boto_success(columns=[("v", "integer")], rows=[["42"]])
    athena_client._boto = mock

    import asyncio
    asyncio.run(athena_client.execute_query("SELECT 42"))
    asyncio.run(athena_client.execute_query("SELECT 42"))  # cache hit
    asyncio.run(athena_client.execute_query("SELECT 42"))  # cache hit

    # start_query_execution debe haberse llamado UNA sola vez
    assert mock.start_query_execution.call_count == 1


def test_cache_no_afecta_query_distinta():
    mock = _mock_boto_success(columns=[("v", "integer")], rows=[["1"]])
    athena_client._boto = mock

    import asyncio
    asyncio.run(athena_client.execute_query("SELECT 1"))
    asyncio.run(athena_client.execute_query("SELECT 2"))  # distinta → no cache
    assert mock.start_query_execution.call_count == 2


def test_null_athena_se_convierte_a_None():
    athena_client._boto = _mock_boto_success(
        columns=[("id", "bigint"), ("nombre", "varchar")],
        rows=[["1", None]],
    )
    import asyncio
    rows = asyncio.run(athena_client.execute_query("SELECT * FROM x"))
    assert rows[0] == {"id": 1, "nombre": None}


# ---------------------------------------------------------------------------
# Tests de los 5 endpoints
# ---------------------------------------------------------------------------
def test_q1_recursos_mas_fallas():
    athena_client._boto = _mock_boto_success(
        columns=[("recurso_id", "bigint"), ("nombre_tecnico_locacion", "varchar"),
                 ("incidencias_total", "bigint"), ("severidad_ponderada", "bigint")],
        rows=[["7", "Espigon A - Puente A07", "59", "122"]],
    )
    r = client.get("/api/analitica/recursos-mas-fallas?dias=7")
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "Q1"
    assert body["params"] == {"dias": 7}
    assert body["count"] == 1
    assert body["rows"][0]["recurso_id"] == 7


def test_q2_retraso_promedio_tipo_valido():
    athena_client._boto = _mock_boto_success(
        columns=[("grupo", "varchar"), ("categoria", "varchar"), ("vuelos", "bigint")],
        rows=[["GLOBAL", "Todo el periodo", "9149"]],
    )
    r = client.get("/api/analitica/retraso-promedio?tipo=Internacional")
    assert r.status_code == 200
    assert r.json()["params"]["tipo"] == "Internacional"


def test_q2_retraso_promedio_tipo_invalido_422():
    r = client.get("/api/analitica/retraso-promedio?tipo=Cualquiera")
    assert r.status_code == 422   # FastAPI valida el Literal


def test_q1_dias_fuera_de_rango_422():
    r = client.get("/api/analitica/recursos-mas-fallas?dias=999")
    assert r.status_code == 422


def test_q3_incidencias_combustible():
    athena_client._boto = _mock_boto_success(
        columns=[("ruc", "varchar"), ("aerolinea", "varchar"),
                 ("vuelos_afectados", "bigint"), ("tasa_por_1000_vuelos", "double")],
        rows=[["20100000001", "LATAM Airlines Peru", "2410", "891.27"]],
    )
    r = client.get("/api/analitica/incidencias-combustible-por-aerolinea")
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "Q3"
    assert body["rows"][0]["aerolinea"] == "LATAM Airlines Peru"
    assert body["rows"][0]["tasa_por_1000_vuelos"] == 891.27


def test_q4_recaudacion_tuua():
    athena_client._boto = _mock_boto_success(
        columns=[("categoria", "varchar"), ("pasajeros", "bigint"),
                 ("recaudacion_soles", "double")],
        rows=[["Internacional", "5769", "221818.05"]],
    )
    r = client.get("/api/analitica/recaudacion-tuua-por-categoria")
    assert r.status_code == 200
    assert r.json()["rows"][0]["recaudacion_soles"] == 221818.05


def test_q5_hora_punta():
    athena_client._boto = _mock_boto_success(
        columns=[("franja", "varchar"), ("tipo", "varchar"), ("pct_retrasados", "double")],
        rows=[["HORA PUNTA (06-09h)", "Internacional", "38.85"]],
    )
    r = client.get("/api/analitica/vuelos-hora-punta-retrasados")
    assert r.status_code == 200
    assert r.json()["query"] == "Q5"


def test_endpoint_devuelve_502_si_athena_falla():
    athena_client._boto = _mock_boto_failed("permission denied")
    r = client.get("/api/analitica/incidencias-combustible-por-aerolinea")
    assert r.status_code == 502
    body = r.json()
    assert body["detail"]["error"] == "ATHENA_QUERY_ERROR"
    assert "permission denied" in body["detail"]["message"]


def test_queries_convierten_fechas_csv_antes_de_operar():
    """Glue cataloga las fechas ISO 8601 del CSV como VARCHAR."""
    q1 = queries.Q1_RECURSOS_MAS_FALLAS.format(dias=7)
    q2 = queries.Q2_RETRASO_PROMEDIO.format(tipo="Internacional")
    q5 = queries.Q5_HORA_PUNTA

    assert "TRY(from_iso8601_timestamp(i.fecha_reporte))" in q1
    assert "TRY(from_iso8601_timestamp(i.fecha_cierre))" in q1
    assert "TRY(from_iso8601_timestamp(v.hora_programada))" in q2
    assert "TRY(from_iso8601_timestamp(v.hora_real))" in q2
    assert "TRY(from_iso8601_timestamp(v.hora_programada))" in q5
    assert "TRY(from_iso8601_timestamp(v.hora_real))" in q5
