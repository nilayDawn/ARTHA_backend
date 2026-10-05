from typing import Any

from app.ports.llm import LLMProviderPort
from app.utils.logger import logger


class OpenAILLMAdapter(LLMProviderPort):
    """
    Extensible OpenAI / compatible LLM provider adapter.
    Demonstrates zero-code-change pluggability for alternative LLM providers.
    """

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def generate_text(
        self,
        contents: Any,
        custom_api_key: str | None = None,
        model_name: str | None = None,
    ) -> str:
        # Ready for openai.OpenAI client integration
        logger.info("[OpenAILLMAdapter] generate_text called (Pluggable adapter)")
        return "OpenAI adapter response placeholder"

    def generate_structured(
        self,
        file_bytes: bytes,
        mime_type: str,
        prompt: str,
        schema: Any,
        custom_api_key: str | None = None,
    ) -> str:
        raise NotImplementedError("OpenAI multimodal vision structured parsing ready to be wired.")

    def generate_embedding(
        self,
        text: str,
        custom_api_key: str | None = None,
    ) -> list[float]:
        raise NotImplementedError("OpenAI text-embedding-3-small ready to be wired.")

    def validate_key(self, api_key: str) -> tuple[bool, str]:
        return bool(api_key), "Key validation ready."
