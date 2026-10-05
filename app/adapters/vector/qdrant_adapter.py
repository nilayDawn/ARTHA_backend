import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.core.config import settings
from app.ports.vector_store import VectorStorePort
from app.utils.logger import logger


class QdrantVectorAdapter(VectorStorePort):
    """
    Qdrant Cloud vector database adapter.
    Fixes redundant collection checks by tracking initialization state.
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str | None = None,
        vector_size: int = 3072,
    ):
        self.url = url or settings.QDRANT_URL
        self.api_key = api_key or settings.QDRANT_API_KEY
        self.collection_name = collection_name or settings.COLLECTION_NAME or "user_memories"
        self.vector_size = vector_size or settings.VECTOR_SIZE or 3072
        self.client: QdrantClient | None = None
        self._initialized = False

        if self.url and self.api_key:
            self.client = QdrantClient(url=self.url, api_key=self.api_key)

    def initialize_store(self) -> None:
        if not self.client:
            logger.warning("[Qdrant] Client not configured. Skipping vector store initialization.")
            return

        if self._initialized:
            return

        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if not exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_size,
                        distance=models.Distance.COSINE,
                    ),
                )
                logger.info("[Qdrant] Created collection '%s' successfully.", self.collection_name)

            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="user_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            except Exception:
                pass

            self._initialized = True
            logger.info("[Qdrant] Vector collection '%s' verified and indexed.", self.collection_name)
        except Exception as e:
            logger.error("[Qdrant Init Error]: %s", e)

    def upsert_memory(
        self,
        user_id: str,
        text: str,
        category: str,
        vector: list[float],
    ) -> bool:
        if not self.client:
            return False

        try:
            if not self._initialized:
                self.initialize_store()

            point_id = str(uuid.uuid4())
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "user_id": user_id,
                            "memory": text,
                            "category": category,
                        },
                    )
                ],
            )
            logger.debug("[Qdrant] Saved memory for UserID: %s", user_id)
            return True
        except Exception as e:
            logger.error("[Qdrant Save Memory Error]: %s", e)
            return False

    def search_memories(
        self,
        user_id: str,
        query_vector: list[float],
        limit: int = 5,
    ) -> list[str]:
        if not self.client:
            return []

        try:
            if not self._initialized:
                self.initialize_store()

            search_result = self.client.query_points(
                collection_name=self.collection_name,
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

            return [
                hit.payload.get("memory")
                for hit in search_result.points
                if hit.payload and hit.payload.get("memory")
            ]
        except Exception as e:
            logger.error("[Qdrant Search Memory Error]: %s", e)
            return []
