from abc import ABC, abstractmethod
from typing import Any


class LLMProviderPort(ABC):
    """Port for LLM reasoning, document OCR extraction, and vector embeddings."""

    @abstractmethod
    def generate_text(
        self,
        contents: Any,
        custom_api_key: str | None = None,
        model_name: str | None = None,
    ) -> str:
        """Generates conversational text or answers for given prompt/contents."""

    @abstractmethod
    def generate_structured(
        self,
        file_bytes: bytes,
        mime_type: str,
        prompt: str,
        schema: Any,
        custom_api_key: str | None = None,
    ) -> str:
        """Runs multimodal vision OCR to extract structured JSON data according to schema."""

    @abstractmethod
    def generate_embedding(
        self,
        text: str,
        custom_api_key: str | None = None,
    ) -> list[float]:
        """Generates semantic dense embedding vector for text."""

    @abstractmethod
    def validate_key(self, api_key: str) -> tuple[bool, str]:
        """Validates that a user-provided LLM API key is active and functional."""
