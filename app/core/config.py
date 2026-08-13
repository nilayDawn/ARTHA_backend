from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    PROJECT_NAME: str = "FinPilot AI"
    API_V1_STR: str = "/api/v1"
    SUPABASE_URL: str | None
    SUPABASE_PASSWORD: str | None
    SUPABASE_ANON_KEY: str | None
    SUPABASE_SERVICE_ROLE_KEY: str | None
    BUCKET_NAME: str | None

    GEMINI_API_KEY: str | None = None
    MODEL_NAME: str | None 

    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None
    COLLECTION_NAME: str | None = "user_memories"
    VECTOR_SIZE: int | None

    TELEGRAM_BOT_TOKEN: str | None = None
    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()