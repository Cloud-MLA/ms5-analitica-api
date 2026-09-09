"""Health check del servicio.

MS5 no consume otros microservicios — solo Athena (AWS Managed). El health
check no verifica Athena porque:
- Verificarlo lanzaría una query real → costo y latencia.
- El indicador correcto es la respuesta del propio endpoint analítico.
"""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Estado propio del servicio")
async def health() -> dict[str, str]:
    return {"status": "up", "service": "ms5-analitica-api"}
