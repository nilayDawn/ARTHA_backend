from qdrant_client import QdrantClient
from app.core.config import settings

qdrant_client = None

if settings.QDRANT_URL and settings.QDRANT_API_KEY:
    qdrant_client = QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )