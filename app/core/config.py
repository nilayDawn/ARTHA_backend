from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "FinPilot AI"
    API_V1_STR: str = "/api/v1"
    SUPABASE_URL: str | None
    SUPABASE_PASSWORD: str | None
    SUPABASE_ANON_KEY: str | None
    SUPABASE_SERVICE_ROLE_KEY: str | None
    BUCKET_NAME: str | None

    GEMINI_API_KEY: str | None = None
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None

    TELEGRAM_BOT_TOKEN: str | None = None
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()