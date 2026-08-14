from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.services.memory import init_memory_collection
from app.utils.logger import logger

app = FastAPI(title=settings.PROJECT_NAME)

# Enable CORS for Frontend Development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    logger.info("Initializing %s backend application...", settings.PROJECT_NAME)
    init_memory_collection()
    logger.info("Qdrant memory collection check completed.")


app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def read_root():
    logger.info("Root endpoint / ping received.")
    return {"status": "online", "message": f"{settings.PROJECT_NAME} Backend API is running"}


@app.get("/health")
def health_check():
    logger.debug("Health check request received.")
    return {"status": "healthy"}

