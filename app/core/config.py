from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "ARTHA AI"
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
    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache
def get_settings():
    return Settings()

settings = get_settings()