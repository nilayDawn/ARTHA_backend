from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(api_router, prefix=settings.API_V1_STR)
@app.get("/")
def read_root():
    return {"status": "online", "message": "FinPilot AI Backend API is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

