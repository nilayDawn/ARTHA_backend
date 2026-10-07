from abc import ABC, abstractmethod


class VectorStorePort(ABC):
    """Port for user preference and habit long-term memory vector storage."""

    @abstractmethod
    def initialize_store(self) -> None:
        """Sets up collection/indexes if not already configured."""

    @abstractmethod
    def upsert_memory(
        self,
        user_id: str,
        text: str,
        category: str,
        vector: list[float],
    ) -> bool:
        """Stores a semantic vector memory scoped to user_id."""

    @abstractmethod
    def search_memories(
        self,
        user_id: str,
        query_vector: list[float],
        limit: int = 5,
    ) -> list[str]:
        """Searches top similar memory texts scoped to user_id."""
