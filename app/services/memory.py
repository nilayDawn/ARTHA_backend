import uuid
from google import genai
from qdrant_client.http import models

from app.core.config import settings
from app.core.vector_db import qdrant_client

COLLECTION_NAME = settings.COLLECTION_NAME or "user_memories"
VECTOR_SIZE = settings.VECTOR_SIZE or 3072


def _get_embedding(text: str) -> list[float]:
    """Generates a 3072-dimensional vector embedding using Gemini gemini-embedding-001."""
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
    )
    if not response.embeddings or not response.embeddings[0].values:
        raise ValueError("No embedding returned from Gemini API.")
    return response.embeddings[0].values


def init_memory_collection():
    """Initializes the Qdrant vector collection and user_id payload index if needed."""
    if not qdrant_client:
        print("[Qdrant Warning] Qdrant client is not initialized.")
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
            print(f"[Qdrant] Created collection '{COLLECTION_NAME}' successfully.")

        # Ensure payload index on user_id exists for filtered search
        try:
            qdrant_client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="user_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass

    except Exception as e:
        print(f"[Qdrant Init Error]: {e}")


def save_user_memory(user_id: str, memory_text: str, category: str = "general") -> bool:
    """
    Embeds memory_text and stores it in Qdrant with payload metadata (user_id, text, category).
    """
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
        return True
    except Exception as e:
        print(f"[Qdrant Save Memory Error]: {e}")
        return False


def search_user_memories(user_id: str, query: str, limit: int = 5) -> list[str]:
    """
    Retrieves top relevant memories for a given query filtered strictly by user_id.
    """
    if not qdrant_client:
        return []

    try:
        init_memory_collection()

        query_vector = _get_embedding(query)

        # Use query_points for qdrant-client >= 1.8 compatibility
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
        return memories
    except Exception as e:
        print(f"[Qdrant Search Memory Error]: {e}")
        return []