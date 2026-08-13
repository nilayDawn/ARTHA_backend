from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.services.memory import init_memory_collection

app = FastAPI(title=settings.PROJECT_NAME)

# Enable CORS for Frontend Development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# initialize Qdrant collection on startup
@app.on_event("startup")
def startup_event():
    init_memory_collection()

app.include_router(api_router, prefix=settings.API_V1_STR)
@app.get("/")
def read_root():
    return {"status": "online", "message": "FinPilot AI Backend API is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

