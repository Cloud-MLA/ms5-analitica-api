"""Endpoints analíticos — MS5-03..07 implementados.

Cada endpoint ejecuta una query Athena predefinida contra el catálogo Glue
`aeropuerto_lake`. Los parámetros del usuario se validan con Pydantic +
whitelist antes de interpolarse en el SQL (evita SQL injection).
"""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.services.athena import AthenaQueryError, athena_client
from app.services import queries

router = APIRouter(prefix="/api/analitica", tags=["analitica"])


# --- Ejemplos para OpenAPI/Swagger ---
_EJ_Q1 = {
    "query": "Q1", "params": {"dias": 7}, "count": 3,
    "rows": [
        {"recurso_id": 461, "tipo": "radar", "nombre_tecnico_locacion": "Radar Norte - Torre 23",
         "incidencias_total": 59, "severidad_ponderada": 122, "incidencias_criticas": 5,
         "incidencias_abiertas": 17, "pct_abiertas": 28.81, "tpr_minutos_promedio": 2297.1},
    ],
}
_EJ_Q3 = {
    "query": "Q3", "count": 2,
    "rows": [
        {"ruc": "20100000001", "aerolinea": "LATAM Airlines Peru", "alianza": "Ninguna",
         "total_vuelos": 2704, "vuelos_afectados": 2410, "tasa_por_1000_vuelos": 891.27,
         "pct_vuelos_afectados": 89.13},
        {"ruc": "20100000006", "aerolinea": "Copa Airlines", "alianza": "Star Alliance",
         "total_vuelos": 2604, "vuelos_afectados": 2341, "tasa_por_1000_vuelos": 899.0,
         "pct_vuelos_afectados": 89.9},
    ],
}
_EJ_502 = {"detail": {"error": "ATHENA_QUERY_ERROR",
                       "message": "Athena query xxx FAILED: Table 'aeropuerto_lake.vuelo' does not exist"}}


async def _run(sql: str) -> list[dict]:
    try:
        rows = await athena_client.execute_query(sql)
    except AthenaQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "ATHENA_QUERY_ERROR", "message": str(exc)},
        )
    return rows


@router.get(
    "/recursos-mas-fallas",
    summary="Q1 — Recurso (manga/radar) con más incidencias en los últimos N días",
    description=(
        "Devuelve el top 10 de recursos con más incidencias en la ventana `dias`, "
        "con severidad ponderada, % abiertas y tiempo promedio de reparación."
    ),
    responses={
        200: {"content": {"application/json": {"example": _EJ_Q1}}},
        502: {"content": {"application/json": {"example": _EJ_502}}},
    },
)
async def recursos_mas_fallas(
    dias: int = Query(default=7, ge=1, le=365, description="Ventana en días (1-365)"),
) -> dict:
    sql = queries.Q1_RECURSOS_MAS_FALLAS.format(dias=dias)
    rows = await _run(sql)
    return {"query": "Q1", "params": {"dias": dias}, "count": len(rows), "rows": rows}


@router.get(
    "/retraso-promedio",
    summary="Q2 — Retraso promedio (min) por tipo de vuelo, con percentiles",
    description=(
        "Devuelve retraso GLOBAL + desglose POR FRANJA (madrugada/mañana/tarde/noche) "
        "con media, desv. estándar, P50/P90/P99. Solo vuelos que efectivamente "
        "despegaron o aterrizaron."
    ),
)
async def retraso_promedio(
    tipo: Literal["Nacional", "Internacional"] = Query(default="Internacional"),
) -> dict:
    sql = queries.Q2_RETRASO_PROMEDIO.format(tipo=tipo)
    rows = await _run(sql)
    return {"query": "Q2", "params": {"tipo": tipo}, "count": len(rows), "rows": rows}


@router.get(
    "/incidencias-combustible-por-aerolinea",
    summary="Q3 — Ranking de aerolíneas por incidencias de Falta_Combustible",
    description=(
        "Cruza incidencias con vuelos afectados y aerolíneas. Incluye tasa por "
        "1000 vuelos (métrica comparable entre aerolíneas grandes y pequeñas)."
    ),
    responses={
        200: {"content": {"application/json": {"example": _EJ_Q3}}},
        502: {"content": {"application/json": {"example": _EJ_502}}},
    },
)
async def incidencias_combustible_por_aerolinea() -> dict:
    rows = await _run(queries.Q3_INCIDENCIAS_COMBUSTIBLE)
    return {"query": "Q3", "count": len(rows), "rows": rows}


@router.get(
    "/recaudacion-tuua-por-categoria",
    summary="Q4 — Recaudación TUUA por categoría migratoria",
    description=(
        "Suma la tarifa TUUA solo de pasajeros efectivos (Check-in o Embarcado) "
        "en vuelos no cancelados. Incluye share %."
    ),
)
async def recaudacion_tuua_por_categoria() -> dict:
    rows = await _run(queries.Q4_RECAUDACION_TUUA)
    return {"query": "Q4", "count": len(rows), "rows": rows}


@router.get(
    "/vuelos-hora-punta-retrasados",
    summary="Q5 — % de vuelos en hora punta (06-09h / 18-21h) retrasados",
    description=(
        "Comparación A/B entre hora pico y no pico, desglosado por tipo (Nacional "
        "vs Internacional), con retraso promedio y P90."
    ),
)
async def vuelos_hora_punta_retrasados() -> dict:
    rows = await _run(queries.Q5_HORA_PUNTA)
    return {"query": "Q5", "count": len(rows), "rows": rows}
