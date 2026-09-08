# ms5-analitica-api
MS5 — Analítico · Python + FastAPI + boto3 → Athena

Parte del Proyecto Parcial CS2032 — Cloud Computing (2026-2).
Contexto y arquitectura: [`cloud-computing-proyecto`](https://github.com/btoroled/cloud-computing-proyecto) ·
Plan de tareas: [`plan/backend.md` §8](https://github.com/btoroled/cloud-computing-proyecto/blob/main/docs/plan/backend.md) ·
Dueño: Fabricio.

> Depende de Data Science: bucket S3 + catálogo Glue con datos. Ver
> [`plan/data-science.md`](https://github.com/btoroled/cloud-computing-proyecto/blob/main/docs/plan/data-science.md).

## Puesta en marcha (base desde la plantilla · BE-TX-02)

Ya trae: `.editorconfig`, `.env.example`, `.github/workflows/build-push-ghcr.yml`
(el `.gitignore` de Python ya existía). Fuente: [plantilla común](https://github.com/Cloud-MLA/aeropuerto-infra-deploy/tree/main/plantilla).

**Pendiente de scaffold (MS5-01, Fabricio):**
- Copiar `plantilla/docker/Dockerfile.python` como `Dockerfile`.
- Config Athena (workgroup, output S3, región) con `LabRole`.
- Capa de ejecución Athena: lanzar query, *poll*, leer resultados, cache por TTL.
- `GET /health` y `GET /docs`.
- `openapi.yaml` borrador (BE-TX-03).

## Convenciones

- **Puerto interno:** `8005`.
- **Errores:** [contrato común](https://github.com/btoroled/cloud-computing-proyecto/blob/main/docs/contratos/errores.md)
  (`ATHENA_QUERY_ERROR` → 502 si el catálogo no está listo).
- **Imagen:** `git tag vX.Y && git push --tags` → `ghcr.io/cloud-mla/ms5-analitica-api:vX.Y`.

## Endpoints (previstos)

| Método | Ruta | Consulta Athena |
|---|---|---|
| GET | `/health` | — |
| GET | `/analitica/recursos-mas-fallas?dias=` | Q1 |
| GET | `/analitica/retraso-promedio?tipo=` | Q2 |
| GET | `/analitica/incidencias-combustible-por-aerolinea` | Q3 |
| GET | `/analitica/recaudacion-tuua-por-categoria` | vista `vw_recaudacion_tuua` |
| GET | `/analitica/vuelos-hora-punta-retrasados` | vista `vw_retrasos_hora_punta` |
