"""Cliente Athena (stub) — llena en MS5-02.

Interfaz pública que los routers de `analitica` van a usar:

    from app.services.athena import athena_client
    resultado = await athena_client.execute_query("SELECT ...")

MS5-02 (Fabricio, F1) debe implementar:
- `execute_query(sql: str) -> list[dict]`:
  1. `start_query_execution` con workgroup, output S3 y database.
  2. Poll a `get_query_execution` hasta estado SUCCEEDED / FAILED / CANCELLED.
  3. `get_query_results` y transformar a `list[dict]` (con conversión de tipos).
  4. Cache por SHA del SQL con TTL `ATHENA_CACHE_TTL_SECONDS`.
  5. Mapear errores de Athena al contrato `ATHENA_QUERY_ERROR` → 502.

Este stub deja la interfaz lista para que los endpoints puedan importarse hoy
sin depender de credenciales AWS ni del catálogo Glue.
"""
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class AthenaQueryError(Exception):
    """Falla al ejecutar una query Athena — mapea a HTTP 502 en los routers."""


class AthenaClient:
    """Stub del cliente Athena. La implementación real llega en MS5-02."""

    def __init__(self) -> None:
        self._database = settings.athena_database
        self._output = settings.athena_output
        self._workgroup = settings.athena_workgroup
        self._region = settings.aws_region
        self._cache_ttl = settings.athena_cache_ttl_seconds
        logger.info(
            "AthenaClient inicializado (stub) db=%s workgroup=%s region=%s",
            self._database, self._workgroup, self._region,
        )

    async def execute_query(self, sql: str) -> list[dict]:
        raise NotImplementedError(
            "MS5-02 pendiente — implementar la capa de ejecucion Athena"
        )


athena_client = AthenaClient()
