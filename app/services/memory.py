import uuid

from qdrant_client.http import models

from app.core.config import settings
from app.core.llm_setup import generate_with_fallback_embedding
from app.core.vector_db import qdrant_client
from app.utils.logger import logger

COLLECTION_NAME = settings.COLLECTION_NAME or "user_memories"
VECTOR_SIZE = settings.VECTOR_SIZE or 3072


def _get_embedding(text: str) -> list[float]:
    return generate_with_fallback_embedding(text)


def init_memory_collection():
    if not qdrant_client:
        logger.warning("[Qdrant] Qdrant client is not initialized.")
        return

    try:
        collections = qdrant_client.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)

        if not exists:
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE,
                ),
            )
            logger.info("[Qdrant] Created collection '%s' successfully.", COLLECTION_NAME)

        
        try:
            qdrant_client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="user_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass

    except Exception as e:
        logger.error("[Qdrant Init Error]: %s", e)


def save_user_memory(user_id: str, memory_text: str, category: str = "general") -> bool:
    if not qdrant_client:
        return False

    try:
        init_memory_collection()

        vector = _get_embedding(memory_text)
        point_id = str(uuid.uuid4())

        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "user_id": user_id,
                        "memory": memory_text,
                        "category": category,
                    },
                )
            ],
        )
        logger.info("[Qdrant] Saved memory for UserID: %s | Text: '%s'", user_id, memory_text)
        return True
    except Exception as e:
        logger.error("[Qdrant Save Memory Error]: %s", e)
        return False


def search_user_memories(user_id: str, query: str, limit: int = 5) -> list[str]:
    if not qdrant_client:
        return []

    try:
        init_memory_collection()

        query_vector = _get_embedding(query)

        search_result = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_id",
                        match=models.MatchValue(value=user_id),
                    )
                ]
            ),
            limit=limit,
        )

        memories = [
            hit.payload.get("memory") for hit in search_result.points if hit.payload
        ]
        logger.info("[Qdrant] Retrieved %d memory vectors for UserID: %s", len(memories), user_id)
        return memories 
    except Exception as e:
        logger.error("[Qdrant Search Memory Error]: %s", e)
        return []