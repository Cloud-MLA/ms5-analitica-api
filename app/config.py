"""Configuración leída de variables de entorno (12-factor)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Config de MS5 — Analítico (Athena).

    Todos los campos pueden sobreescribirse con variables de entorno del mismo
    nombre. Ver `.env.example`.

    En EC2 con Learner Lab, boto3 toma las credenciales del `LabInstanceProfile`
    automáticamente. En local, exportar `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
    y `AWS_SESSION_TOKEN` desde la consola del laboratorio.
    """

    port: int = 8005
    env: str = "local"

    aws_region: str = "us-east-1"

    athena_database: str = "aeropuerto_lake"
    athena_output: str = "s3://mla-aeropuerto-lake/athena-results/"
    athena_workgroup: str = "primary"
    athena_cache_ttl_seconds: int = 300

    log_level: str = "info"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
