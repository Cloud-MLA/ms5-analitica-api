"""Endpoints analíticos — stubs.

Cada endpoint mapea a una consulta Athena (Q1..Q5) o a una vista definida en
el repo `aeropuerto-data-science/athena/`.

La implementación real llega en MS5-03..MS5-07 (F2 del plan), después de que:
- Los 3 devs hayan cargado 20k+ registros en sus BDs.
- La ingesta (DS-06/07/08) haya poblado `s3://mla-aeropuerto-lake/raw/`.
- El catálogo Glue esté listo (DS-09/10) y las queries portadas a Athena (DS-11).
- Las 2 vistas estén creadas (DS-12).
"""
from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api/analitica", tags=["analitica"])


def _stub_501(tarea: str, query: str, params: dict | None = None) -> None:
    detail = {"tarea": tarea, "query_athena": query, "mensaje": f"{tarea} pendiente"}
    if params:
        detail["params"] = params
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=detail)


@router.get(
    "/recursos-mas-fallas",
    summary="Recurso (manga/radar) con más incidencias en los últimos N días",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def recursos_mas_fallas(dias: int = 7) -> dict:
    _stub_501("MS5-03", "Q1", {"dias": dias})


@router.get(
    "/retraso-promedio",
    summary="Retraso medio (minutos) de vuelos por tipo",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def retraso_promedio(tipo: str = "Internacional") -> dict:
    _stub_501("MS5-04", "Q2", {"tipo": tipo})


@router.get(
    "/incidencias-combustible-por-aerolinea",
    summary="Ranking de aerolíneas por incidencias de tipo Falta_Combustible",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def incidencias_combustible_por_aerolinea() -> dict:
    _stub_501("MS5-05", "Q3")


@router.get(
    "/recaudacion-tuua-por-categoria",
    summary="Recaudación estimada TUUA por categoría migratoria",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def recaudacion_tuua_por_categoria() -> dict:
    _stub_501("MS5-06", "vw_recaudacion_tuua")


@router.get(
    "/vuelos-hora-punta-retrasados",
    summary="Porcentaje de vuelos en hora punta (06–09h / 18–21h) retrasados",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def vuelos_hora_punta_retrasados() -> dict:
    _stub_501("MS5-07", "vw_retrasos_hora_punta")
