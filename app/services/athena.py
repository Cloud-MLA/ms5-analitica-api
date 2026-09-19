"""Cliente Athena — implementación real (MS5-02).

Flujo por query:
1. `start_query_execution` con workgroup + output S3 + database del catálogo Glue.
2. Poll a `get_query_execution` hasta estado terminal (SUCCEEDED/FAILED/CANCELLED).
3. `get_query_results` → transformación a `list[dict]` con conversión de tipos.
4. Cache por SHA-256 del SQL con TTL de `settings.athena_cache_ttl_seconds`.
5. Mapeo de errores de Athena → `AthenaQueryError` → HTTP 502 en el router.

En EC2 con Learner Lab, boto3 usa el `LabInstanceProfile` automáticamente.
En local, credenciales por env (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_SESSION_TOKEN`).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

logger = logging.getLogger(__name__)

# Estados terminales de Athena que detienen el poll.
_ATHENA_TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}
_POLL_INTERVAL_SECONDS = 0.5
_POLL_TIMEOUT_SECONDS = 60


class AthenaQueryError(Exception):
    """Falla al ejecutar una query Athena — mapea a HTTP 502 en los routers."""


def _sha(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def _cast_athena_value(raw: str | None, athena_type: str) -> Any:
    """Convierte un valor devuelto por Athena (siempre string) a su tipo Python.

    Athena types comunes: varchar, bigint, integer, double, decimal, boolean,
    timestamp, date. Ver docs: 'get_query_results' devuelve todos los valores
    como strings — la conversión la hace el cliente.
    """
    if raw is None:
        return None
    try:
        t = athena_type.lower()
        if t in ("bigint", "integer", "int", "tinyint", "smallint"):
            return int(raw)
        if t in ("double", "float", "real", "decimal"):
            return float(raw)
        if t == "boolean":
            return raw.lower() == "true"
        # varchar, timestamp, date, y desconocidos: dejamos string.
        return raw
    except (ValueError, AttributeError):
        return raw


class AthenaClient:
    """Cliente Athena con poll síncrono adaptado a asyncio y cache en memoria."""

    def __init__(self) -> None:
        self._database = settings.athena_database
        self._output = settings.athena_output
        self._workgroup = settings.athena_workgroup
        self._region = settings.aws_region
        self._cache_ttl = settings.athena_cache_ttl_seconds
        # Cache: {sha_del_sql: (timestamp_epoch, resultado)}
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        # boto3 client se crea lazy para permitir tests sin AWS.
        self._boto: Any = None
        logger.info(
            "AthenaClient inicializado db=%s workgroup=%s region=%s cache_ttl=%ss",
            self._database, self._workgroup, self._region, self._cache_ttl,
        )

    def _client(self):
        if self._boto is None:
            self._boto = boto3.client("athena", region_name=self._region)
        return self._boto

    async def execute_query(self, sql: str, use_cache: bool = True) -> list[dict[str, Any]]:
        """Ejecuta una query Athena y devuelve las filas como lista de dicts.

        Raises:
            AthenaQueryError: si Athena reporta FAILED/CANCELLED, timeout o
                              error de boto3.
        """
        cache_key = _sha(sql)
        now = time.time()

        # Cache hit
        if use_cache and cache_key in self._cache:
            ts, cached = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                logger.debug("cache hit sha=%s edad=%.1fs", cache_key[:8], now - ts)
                return cached
            # Cache stale — se sobrescribe abajo tras la ejecución
            logger.debug("cache stale sha=%s edad=%.1fs", cache_key[:8], now - ts)

        # Ejecutar (boto3 es síncrono; corremos en threadpool para no bloquear el loop)
        rows = await asyncio.to_thread(self._run_sync, sql)

        if use_cache:
            self._cache[cache_key] = (now, rows)

        return rows

    def _run_sync(self, sql: str) -> list[dict[str, Any]]:
        client = self._client()
        try:
            resp = client.start_query_execution(
                QueryString=sql,
                QueryExecutionContext={"Database": self._database},
                WorkGroup=self._workgroup,
                ResultConfiguration={"OutputLocation": self._output},
            )
        except (BotoCoreError, ClientError) as exc:
            raise AthenaQueryError(f"Athena start_query_execution failed: {exc}") from exc

        query_id = resp["QueryExecutionId"]
        logger.info("Athena query %s iniciada", query_id)

        # Poll
        deadline = time.time() + _POLL_TIMEOUT_SECONDS
        while True:
            if time.time() > deadline:
                # Intento cancelarla y salimos
                try:
                    client.stop_query_execution(QueryExecutionId=query_id)
                except Exception:  # noqa: BLE001
                    pass
                raise AthenaQueryError(
                    f"Athena query {query_id} timeout tras {_POLL_TIMEOUT_SECONDS}s"
                )

            try:
                info = client.get_query_execution(QueryExecutionId=query_id)
            except (BotoCoreError, ClientError) as exc:
                raise AthenaQueryError(f"Athena get_query_execution failed: {exc}") from exc

            status = info["QueryExecution"]["Status"]
            state = status["State"]

            if state in _ATHENA_TERMINAL:
                if state != "SUCCEEDED":
                    reason = status.get("StateChangeReason", "sin detalle")
                    raise AthenaQueryError(f"Athena query {query_id} {state}: {reason}")
                break

            time.sleep(_POLL_INTERVAL_SECONDS)

        # Obtener resultados (paginados si son muchas filas)
        try:
            return self._collect_results(client, query_id)
        except (BotoCoreError, ClientError) as exc:
            raise AthenaQueryError(f"Athena get_query_results failed: {exc}") from exc

    @staticmethod
    def _collect_results(client, query_id: str) -> list[dict[str, Any]]:
        """Junta todas las páginas de resultados y devuelve list[dict] con tipos."""
        paginator = client.get_paginator("get_query_results")
        columns: list[tuple[str, str]] | None = None  # (name, athena_type)
        rows: list[dict[str, Any]] = []

        for page_idx, page in enumerate(paginator.paginate(QueryExecutionId=query_id)):
            result_set = page["ResultSet"]

            # Los nombres+tipos de columna vienen en cada página en ResultSetMetadata
            if columns is None:
                columns = [
                    (col["Name"], col["Type"])
                    for col in result_set["ResultSetMetadata"]["ColumnInfo"]
                ]

            # La primera fila de la primera página es el header, se descarta
            data_rows = result_set["Rows"]
            if page_idx == 0 and data_rows:
                data_rows = data_rows[1:]

            for row in data_rows:
                cells = row.get("Data", [])
                doc = {}
                for (name, athena_type), cell in zip(columns, cells):
                    raw = cell.get("VarCharValue")  # None si NULL
                    doc[name] = _cast_athena_value(raw, athena_type)
                rows.append(doc)

        return rows


# Singleton usado por los routers.
athena_client = AthenaClient()
