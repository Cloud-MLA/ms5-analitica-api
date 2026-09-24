# ms5-analitica-api · v1.0

**MS5 — Analítico.** Microservicio Python + FastAPI + `boto3` que ejecuta las **5 consultas de negocio (Q1–Q5)** contra el data lake `s3://mla-aeropuerto-lake/` vía **AWS Athena** (catálogo Glue `aeropuerto_lake`).

Parte del Proyecto Parcial CS2032 — Cloud Computing (UTEC 2026-2).
[`cloud-computing-proyecto`](https://github.com/btoroled/cloud-computing-proyecto) ·
[`plan/hito2.md §2.6`](https://github.com/btoroled/cloud-computing-proyecto/blob/main/docs/plan/hito2.md#26-ms5--analítico--python--fastapi--boto3--athena-fabricio) ·
Dueño: **Fabricio**.

> **Depende de Data Science:** requiere el catálogo Glue con las tablas creadas por la ingesta (DS-06/07/08 → DS-09/10 del [plan de DS](https://github.com/btoroled/cloud-computing-proyecto/blob/main/docs/plan/data-science.md)).

---

## Endpoints analíticos

Base path: `/api/analitica`.

| Método | Ruta | Query Athena | Parámetros |
|---|---|---|---|
| `GET` | `/health` | — | — |
| `GET` | `/api/analitica/recursos-mas-fallas` | **Q1** — recurso con más incidencias | `?dias=N` (1–365) |
| `GET` | `/api/analitica/retraso-promedio` | **Q2** — retraso medio por tipo | `?tipo=Nacional\|Internacional` |
| `GET` | `/api/analitica/incidencias-combustible-por-aerolinea` | **Q3** — ranking Falta_Combustible | — |
| `GET` | `/api/analitica/recaudacion-tuua-por-categoria` | **Q4** — recaudación TUUA (vista `vw_recaudacion_tuua`) | — |
| `GET` | `/api/analitica/vuelos-hora-punta-retrasados` | **Q5** — % retrasos hora pico (vista `vw_retrasos_hora_punta`) | — |
| `GET` | `/docs` · `/openapi.json` | — | — |

Las 5 queries SQL viven en [`app/services/queries.py`](app/services/queries.py) — portadas de [`aeropuerto-data-science/athena/queries/*.sql`](https://github.com/Cloud-MLA/aeropuerto-data-science/tree/main/athena/queries) con la sintaxis Athena/Trino.

## Ejemplo `curl`

```bash
# Q1 — top 10 recursos con más fallas en la última semana
curl https://<api-gateway>/api/analitica/recursos-mas-fallas?dias=7

# Q3 — ranking de aerolíneas por incidencias de combustible
curl https://<api-gateway>/api/analitica/incidencias-combustible-por-aerolinea
```

Respuesta (recortada):

```json
{
  "query": "Q3",
  "count": 24,
  "rows": [
    {"ruc": "20100000001", "aerolinea": "LATAM Airlines Peru", "alianza": "Ninguna",
     "total_vuelos": 2704, "vuelos_afectados": 2410, "tasa_por_1000_vuelos": 891.27},
    {"ruc": "20100000006", "aerolinea": "Copa Airlines", "alianza": "Star Alliance",
     "total_vuelos": 2604, "vuelos_afectados": 2341, "tasa_por_1000_vuelos": 899.00}
  ]
}
```

## Errores (contrato común)

Si Athena falla (catálogo no listo, workgroup mal configurado, query con error de sintaxis), MS5 devuelve **502**:

```json
{
  "detail": {
    "error": "ATHENA_QUERY_ERROR",
    "message": "Athena query xxx FAILED: Table aeropuerto_lake.vuelo does not exist"
  }
}
```

Parámetros inválidos (`?dias=999`, `?tipo=Cualquiera`) devuelven **422** con detalle Pydantic.

---

## Correr localmente

Requiere credenciales AWS temporales del Learner Lab en el `.env` local (Athena es un servicio managed — no se levanta local).

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # Linux/Mac
pip install -r requirements.txt
copy .env.example .env            # Windows (o cp)
# Editar .env: pegar AWS_ACCESS_KEY_ID / SECRET / SESSION_TOKEN del laboratorio
uvicorn app.main:app --reload --port 8005
```

Abre http://localhost:8005/docs.

**Con Docker:**

```bash
docker compose up --build
```

**Correr tras corte de sesión del Learner Lab** (<15 min):

```bash
# Pegar credenciales nuevas en .env y reiniciar el contenedor
docker compose restart ms5
```

En EC2 con Learner Lab, boto3 toma las credenciales del `LabInstanceProfile` automáticamente — **no** hay que pasar claves en `.env`.

---

## Configuración (env vars)

Ver `.env.example`.

| Variable | Default | Descripción |
|---|---|---|
| `PORT` | `8005` | Puerto interno |
| `AWS_REGION` | `us-east-1` | Región de AWS |
| `ATHENA_DATABASE` | `aeropuerto_lake` | Base de datos Glue |
| `ATHENA_OUTPUT` | `s3://mla-aeropuerto-lake/athena-results/` | Bucket de salida de Athena |
| `ATHENA_WORKGROUP` | `primary` | Workgroup |
| `ATHENA_CACHE_TTL_SECONDS` | `300` | TTL del cache local por SHA del SQL |
| `LOG_LEVEL` | `info` | `debug`/`info`/`warning`/`error` |
| `ENV` | `local` | Nombre del entorno |

---

## Arquitectura interna

```
app/
├── main.py                     FastAPI 0.115
├── config.py                   pydantic-settings (Athena config por env)
├── services/
│   ├── athena.py               AthenaClient real (start → poll → results + cache SHA + TTL)
│   └── queries.py              Las 5 SQL Q1-Q5 en sintaxis Athena/Trino
└── routers/
    ├── health.py               /health
    └── analitica.py            Los 5 endpoints Q1-Q5
tests/                          16 tests con MagicMock boto3 (no requieren AWS)
```

## Decisiones técnicas

- **`boto3.client("athena")` lazy** — instanciado en la primera query, no al arrancar. Permite tests sin AWS y arranque incluso sin credenciales.
- **Poll síncrono en `asyncio.to_thread`** — boto3 no es async; usarlo directo bloquea el event loop de FastAPI. Con `to_thread` lo movemos a un threadpool.
- **Cache por SHA-256 del SQL** — el mismo `?dias=7` no consulta Athena dos veces en 5 min. TTL configurable.
- **Validación de parámetros con Pydantic `Literal` + `Query(ge, le)`** — el usuario no puede inyectar SQL. `dias` se cast a int y se valida rango; `tipo` es enum estricto.
- **`ATHENA_QUERY_ERROR → 502`** siguiendo el [contrato común de errores](https://github.com/btoroled/cloud-computing-proyecto/blob/main/docs/contratos/errores.md).

---

## Tests

```bash
pytest -q
```

17 tests · 2 seg. Con `MagicMock` de boto3 — **no requieren AWS**. Cubren:

- **AthenaClient:** query exitosa → filas tipadas, FAILED → `AthenaQueryError`, timeout, cache TTL, cache no cruza entre queries distintas, NULL de Athena → `None`.
- **Los 5 endpoints:** 200 con datos mockeados de Q1-Q5, validación 422 de params fuera de rango, 502 si Athena falla.

---

## Publicación de imagen

Un merge en `main` dispara [`build-push-dockerhub.yml`](.github/workflows/build-push-dockerhub.yml) → publica `btoroled/ms5-analitica-api:latest` en Docker Hub. Los tags `vX.Y` también publican una versión etiquetada.

En producción, `compose/vm-prod/docker-compose.yml` del repo [`aeropuerto-infra-deploy`](https://github.com/Cloud-MLA/aeropuerto-infra-deploy) usa esa imagen. Tras publicar una nueva versión, hay que actualizar MS5 en ambas VM-PROD con `docker compose pull ms5 && docker compose up -d ms5` desde el directorio del compose (o mediante el procedimiento de despliegue automatizado del equipo).

---

## Convenciones del proyecto

- **Puerto interno:** `8005`.
- **Errores:** [contrato común](https://github.com/btoroled/cloud-computing-proyecto/blob/main/docs/contratos/errores.md) (`ATHENA_QUERY_ERROR` → 502 si el catálogo no está listo).
- **Imagen:** merge en `main` → `btoroled/ms5-analitica-api:latest`; tag `vX.Y` → imagen versionada.

Ver el [checklist personal de Fabricio](https://github.com/btoroled/cloud-computing-proyecto/blob/main/docs/plan/personas/fabricio.md) en el repo de docs.
