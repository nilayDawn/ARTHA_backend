from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "ARTHA AI"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    SUPABASE_URL: str | None
    SUPABASE_ANON_KEY: str | None
    SUPABASE_SERVICE_ROLE_KEY: str | None
    BUCKET_NAME: str | None

    GEMINI_API_KEY: str | None = None
    GEMINI_API_KEY_1: str | None = None
    GEMINI_API_KEY_2: str | None = None
    GEMINI_API_KEY_3: str | None = None
    MODEL_NAME: str | None = "gemini-3.6-flash"

    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None
    COLLECTION_NAME: str | None = "user_memories"
    VECTOR_SIZE: int | None = 3072

    TELEGRAM_BOT_TOKEN: str | None = None

    EMAIL_FROM: str = "ARTHA AI <onboarding@resend.dev>"
    SMTP_SERVER: str | None = "smtp.gmail.com"
    SMTP_PORT: int | None = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    RESEND_API_KEY: str | None = None

    # Redis Cache Configuration
    REDIS_URL: str | None = None

    # Worker Threadpool Concurrency
    THREADPOOL_LIMIT: int = 100

    # Allowed CORS Origins (comma-separated or *)
    CORS_ORIGINS: str | None = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings():
    return Settings()

settings = get_settings()