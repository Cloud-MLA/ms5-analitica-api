# ms5-analitica-api
MS5 — Analítico · Python + FastAPI + boto3 → Athena

Parte del Proyecto Parcial CS2032 — Cloud Computing (2026-2).
Contexto y arquitectura: [`cloud-computing-proyecto`](https://github.com/btoroled/cloud-computing-proyecto) ·
Plan de tareas: [`plan/backend.md` §8](https://github.com/btoroled/cloud-computing-proyecto/blob/main/docs/plan/backend.md) ·
Dueño: Fabricio.

> Depende de Data Science: bucket S3 + catálogo Glue con datos. Ver
> [`plan/data-science.md`](https://github.com/btoroled/cloud-computing-proyecto/blob/main/docs/plan/data-science.md).

## Estado (MS5-01 ✅)

Scaffold operativo: `GET /health` responde, los 5 endpoints analíticos existen y devuelven `501` con la referencia a su query. La capa Athena (MS5-02) es un stub — se implementa en F1.

Ya trae (base de plantilla, BE-TX-02): `.editorconfig`, `.env.example`, `.github/workflows/build-push-ghcr.yml` (el `.gitignore` de Python ya existía). Fuente: [plantilla común](https://github.com/Cloud-MLA/aeropuerto-infra-deploy/tree/main/plantilla).

Añadido en el scaffold (MS5-01):
- `app/main.py` — FastAPI 0.115 con Swagger en `/docs`.
- `app/config.py` — `pydantic-settings`, config Athena por env.
- `app/services/athena.py` — stub del cliente Athena (interfaz `execute_query`, cache TTL, mapeo `ATHENA_QUERY_ERROR → 502` — se llena en MS5-02).
- `app/routers/health.py` — `GET /health`.
- `app/routers/analitica.py` — 5 endpoints stub (`501`) con parámetros y referencia a cada Q/vista.
- `Dockerfile` multi-stage, no-root, `HEALTHCHECK` nativo.
- `docker-compose.yml` para dev local.
- `openapi.yaml` borrador (BE-TX-03).
- `tests/test_health.py` — 7 asserts que pasan.

## Correr localmente

Requiere credenciales AWS temporales del Learner Lab en el `.env` local:

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
copy .env.example .env       # Windows (o cp en Linux)
# Editar .env: pegar AWS_ACCESS_KEY_ID / SECRET / SESSION_TOKEN del laboratorio.
uvicorn app.main:app --reload --port 8005
```

Abre http://localhost:8005/docs.

## Correr con Docker

```bash
docker compose up --build
```

## Correr tras corte de sesión del Learner Lab (<15 min)

```bash
git pull                                  # trae imagen actualizada
docker compose pull && docker compose up  # imagen ya publicada en GHCR
```

Como el Learner Lab rota credenciales al reanudar, pega las nuevas en `.env` y reinicia el contenedor.

## Convenciones

- **Puerto interno:** `8005`.
- **Errores:** [contrato común](https://github.com/btoroled/cloud-computing-proyecto/blob/main/docs/contratos/errores.md)
  (`ATHENA_QUERY_ERROR` → 502 si el catálogo no está listo).
- **Imagen:** `git tag vX.Y && git push --tags` → `ghcr.io/cloud-mla/ms5-analitica-api:vX.Y`.

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

## Endpoints

Base path de negocio: `/api/analitica`.

| Método | Ruta | Consulta Athena | Estado |
|---|---|---|---|
| GET | `/health` | — | ✅ |
| GET | `/analitica/recursos-mas-fallas?dias=` | Q1 | ⏳ MS5-03 (F2) |
| GET | `/analitica/retraso-promedio?tipo=` | Q2 | ⏳ MS5-04 (F2) |
| GET | `/analitica/incidencias-combustible-por-aerolinea` | Q3 | ⏳ MS5-05 (F2) |
| GET | `/analitica/recaudacion-tuua-por-categoria` | vista `vw_recaudacion_tuua` | ⏳ MS5-06 (F2) |
| GET | `/analitica/vuelos-hora-punta-retrasados` | vista `vw_retrasos_hora_punta` | ⏳ MS5-07 (F2) |

Swagger-UI en `/docs` · OpenAPI JSON en `/openapi.json`.

Ver el [checklist personal de Fabricio](https://github.com/btoroled/cloud-computing-proyecto/blob/main/docs/plan/personas/fabricio.md) en el repo de docs.
