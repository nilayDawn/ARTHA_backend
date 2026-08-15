from contextvars import ContextVar
from google import genai
from app.core.config import settings
from app.schemas.document import ExtractedTransaction

# Context variable to hold user-supplied custom API key per request context
custom_api_key_ctx: ContextVar[str | None] = ContextVar("custom_api_key_ctx", default=None)

API_KEYS = [
    settings.GEMINI_API_KEY_1,
    settings.GEMINI_API_KEY_2,
    settings.GEMINI_API_KEY_3,
]

SYSTEM_API_KEYS = [key for key in API_KEYS if key]


def get_effective_api_keys(override_key: str | None = None) -> list[str]:
    """
    Returns prioritized list of API keys:
    1. override_key or custom_api_key_ctx (if provided by user)
    2. SYSTEM_API_KEYS (configured application defaults)
    """
    user_key = override_key or custom_api_key_ctx.get(None)
    keys_to_try = []

    if user_key and user_key.strip():
        keys_to_try.append(user_key.strip())

    for k in SYSTEM_API_KEYS:
        if k and k not in keys_to_try:
            keys_to_try.append(k)

    return keys_to_try


def validate_gemini_api_key(api_key: str) -> tuple[bool, str]:
    """
    Validates a provided Gemini API key by making a lightweight test query.
    Returns (True, success_msg) or (False, error_msg).
    """
    if not api_key or not api_key.strip():
        return False, "API key cannot be empty."

    try:
        client = genai.Client(api_key=api_key.strip())
        model_name = settings.MODEL_NAME or "gemini-2.5-flash"
        response = client.models.generate_content(
            model=model_name,
            contents="Ping test to verify API key.",
        )
        if response and response.text:
            return True, "API Key is valid and active!"
        return False, "Received empty response from Gemini API."
    except Exception as e:
        return False, f"Key validation failed: {e!s}"


def generate_with_fallback(prompt, custom_api_key: str | None = None):
    last_error = None
    model_name = settings.MODEL_NAME or "gemini-2.5-flash"
    keys_to_try = get_effective_api_keys(custom_api_key)

    if not keys_to_try:
        raise RuntimeError("No Gemini API keys available (neither custom nor system keys set).")

    for key in keys_to_try:
        try:
            client = genai.Client(api_key=key)

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )

            return response.text

        except Exception as e:
            last_error = e
            print(f"[LLM Key Failure]: Key ending in '...{key[-4:] if len(key) >= 4 else key}' failed: {e}")
            continue

    raise RuntimeError(
        f"All Gemini API keys failed. Last error: {last_error}"
    )


def generate_with_fallback_ocr(image_bytes, mime_type, prompt, custom_api_key: str | None = None):
    last_error = None
    model_name = settings.MODEL_NAME or "gemini-2.5-flash"
    keys_to_try = get_effective_api_keys(custom_api_key)

    if not keys_to_try:
        raise RuntimeError("No Gemini API keys available (neither custom nor system keys set).")

    for key in keys_to_try:
        try:
            client = genai.Client(api_key=key)

            response = client.models.generate_content(
                model=model_name,
                contents=[
                    genai.types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=mime_type,
                    ),
                    prompt,
                ],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExtractedTransaction,
                    temperature=0.1,
                ),
            )

            return response.text

        except Exception as e:
            last_error = e
            print(f"[LLM OCR Key Failure]: Key ending in '...{key[-4:] if len(key) >= 4 else key}' failed: {e}")
            continue

    raise RuntimeError(
        f"All Gemini API keys failed. Last error: {last_error}"
    )


def generate_with_fallback_embedding(text, custom_api_key: str | None = None):
    last_error = None
    keys_to_try = get_effective_api_keys(custom_api_key)

    if not keys_to_try:
        raise RuntimeError("No Gemini API keys available (neither custom nor system keys set).")

    for key in keys_to_try:
        try:
            client = genai.Client(api_key=key)

            response = client.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
            )
            if not response.embeddings or not response.embeddings[0].values:
                raise ValueError("No embedding returned from Gemini API.")
            return response.embeddings[0].values

        except Exception as e:
            last_error = e
            print(f"[LLM Embedding Key Failure]: Key ending in '...{key[-4:] if len(key) >= 4 else key}' failed: {e}")
            continue

    raise RuntimeError(
        f"All Gemini API keys failed. Last error: {last_error}"
    )