from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.secrets"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PROSTOR MVP Backend"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"

    database_url: str = Field(
        default="postgresql+asyncpg://prostor:prostor@localhost:5433/prostor",
        alias="DATABASE_URL",
    )

    embedding_model_name: str = Field(
        default="intfloat/multilingual-e5-small",
        alias="EMBEDDING_MODEL_NAME",
    )
    embedding_dim: int = Field(default=384, alias="EMBEDDING_DIM")
    embedding_device: str = Field(default="cpu", alias="EMBEDDING_DEVICE")

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8080",
        ],
        alias="CORS_ORIGINS",
    )

    # --- Необязательный LLM для генерации ТЗ ---------------------------------
    # Если ключ не задан, генератор ТЗ работает офлайн на эвристиках.
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="https://api.deepseek.com", alias="LLM_BASE_URL")
    llm_model: str = Field(default="deepseek-chat", alias="LLM_MODEL")
    llm_timeout: float = Field(default=30.0, alias="LLM_TIMEOUT")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key.strip())

    # --- S3 / MinIO ----------------------------------------------------------
    # Endpoint для серверных вызовов (backend → minio по внутренней сети).
    s3_endpoint_url: str = Field(default="http://minio:9000", alias="S3_ENDPOINT_URL")
    # Endpoint, который отдаётся браузеру в presigned URL. Обычно наружу.
    s3_public_endpoint_url: str = Field(
        default="http://localhost:9000", alias="S3_PUBLIC_ENDPOINT_URL"
    )
    s3_access_key: str = Field(default="prostor", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="prostor12345", alias="S3_SECRET_KEY")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")
    s3_bucket_templates: str = Field(default="prostor-templates", alias="S3_BUCKET_TEMPLATES")
    s3_bucket_tz: str = Field(default="prostor-tz", alias="S3_BUCKET_TZ")
    s3_presign_ttl: int = Field(default=3600, alias="S3_PRESIGN_TTL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
