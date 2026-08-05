from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "FinPilot AI"
    API_V1_STR: str = "/api/v1"
    SUPABASE_URL: str | None
    SUPABASE_PASSWORD: str | None
    SUPABASE_ANON_KEY: str | None
    SUPABASE_SERVICE_ROLE_KEY: str | None

    class Config:
        env_file = ".env"

settings = Settings()