"""Entry point de MS5 — Analítico (Athena)."""
import logging

from fastapi import FastAPI

from app.config import settings
from app.routers import analitica, health

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="MS5 — Analítico",
    version="0.1.0",
    description=(
        "Endpoints analíticos sobre el data lake del aeropuerto. Cada endpoint "
        "ejecuta una consulta Athena predefinida (o lee una vista) y devuelve el "
        "resultado. Consulta el catálogo Glue `aeropuerto_lake`."
    ),
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.include_router(health.router)
app.include_router(analitica.router)
