from contextvars import ContextVar
from typing import Any

from google import genai

from app.core.config import settings
from app.modules.documents.schemas import ExtractedTransaction
from app.ports.llm import LLMProviderPort
from app.utils.logger import logger

custom_api_key_ctx: ContextVar[str | None] = ContextVar("custom_api_key_ctx", default=None)


class GeminiLLMAdapter(LLMProviderPort):
    """
    Adapter for Google Gemini AI models.
    Supports thread-safe custom API keys, multi-key failover, structured JSON vision extraction,
    and text embeddings.
    """

    def __init__(
        self,
        system_keys: list[str] | None = None,
        default_model: str = "gemini-3.6-flash",
        embedding_model: str = "gemini-embedding-001",
    ):
        raw_keys = system_keys or [
            settings.GEMINI_API_KEY,
            settings.GEMINI_API_KEY_1,
            settings.GEMINI_API_KEY_2,
            settings.GEMINI_API_KEY_3,
        ]
        self.system_keys = [k.strip() for k in raw_keys if k and k.strip()]     #list of non-empty, stripped keys
        self.default_model = settings.MODEL_NAME or default_model
        self.embedding_model = embedding_model

    def _get_candidate_keys(self, custom_api_key: str | None = None) -> list[str]:
        user_key = custom_api_key or custom_api_key_ctx.get(None)
        keys_to_try = []
        if user_key and user_key.strip():
            keys_to_try.append(user_key.strip())
        for k in self.system_keys:
            if k not in keys_to_try:
                keys_to_try.append(k)
        return keys_to_try

    def generate_text(
        self,
        contents: Any,
        custom_api_key: str | None = None,
        model_name: str | None = None,
    ) -> str:
        keys = self._get_candidate_keys(custom_api_key)
        if not keys:
            raise RuntimeError("No Gemini API keys available.")

        target_model = model_name or self.default_model
        last_error = None

        for key in keys:
            try:
                client = genai.Client(api_key=key)
                response = client.models.generate_content(
                    model=target_model,
                    contents=contents,
                )
                return response.text or ""
            except Exception as e:
                last_error = e
                logger.warning("[Gemini Text Key Fail]: Key '...%s': %s", key[-4:] if len(key) >= 4 else key, e)
                continue

        raise RuntimeError(f"All Gemini API keys failed during generate_text. Last error: {last_error}")

    def generate_structured(
        self,
        file_bytes: bytes,
        mime_type: str,
        prompt: str,
        schema: Any,
        custom_api_key: str | None = None,
    ) -> str:
        keys = self._get_candidate_keys(custom_api_key)
        if not keys:
            raise RuntimeError("No Gemini API keys available.")

        schema_to_use = schema if schema is not None else ExtractedTransaction
        last_error = None

        for key in keys:
            try:
                client = genai.Client(api_key=key)
                response = client.models.generate_content(
                    model=self.default_model,
                    contents=[
                        genai.types.Part.from_bytes(data=file_bytes, mime_type=mime_type),    #tells Gemini to treat this as a file
                        prompt,
                    ],
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema_to_use,      
                        temperature=0.1,
                    ),
                )
                return response.text or ""
            except Exception as e:
                last_error = e
                logger.warning("[Gemini Vision Key Fail]: Key '...%s': %s", key[-4:] if len(key) >= 4 else key, e)
                continue

        raise RuntimeError(f"All Gemini API keys failed during generate_structured. Last error: {last_error}")

    def generate_embedding(
        self,
        text: str,
        custom_api_key: str | None = None,
    ) -> list[float]:
        keys = self._get_candidate_keys(custom_api_key)
        if not keys:
            raise RuntimeError("No Gemini API keys available.")

        last_error = None
        for key in keys:
            try:
                client = genai.Client(api_key=key)
                response = client.models.embed_content(
                    model=self.embedding_model,
                    contents=text,
                )
                if not response.embeddings or not response.embeddings[0].values:
                    raise ValueError("No embeddings returned.")
                return response.embeddings[0].values
            except Exception as e:
                last_error = e
                logger.warning("[Gemini Embedding Key Fail]: Key '...%s': %s", key[-4:] if len(key) >= 4 else key, e)
                continue

        raise RuntimeError(f"All Gemini API keys failed during generate_embedding. Last error: {last_error}")

    def validate_key(self, api_key: str) -> tuple[bool, str]:
        if not api_key or not api_key.strip():
            return False, "API key cannot be empty."

        try:
            client = genai.Client(api_key=api_key.strip())
            response = client.models.generate_content(
                model=self.default_model,
                contents="Ping test to verify API key.",
            )
            if response and response.text:
                return True, "API Key is valid and active!"
            return False, "Received empty response from Gemini API."
        except Exception as e:
            return False, f"Key validation failed: {e!s}"
