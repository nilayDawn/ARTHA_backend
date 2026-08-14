from app.schemas.document import ExtractedTransaction
from app.core.config import settings
from google import genai

API_KEYS = [
    settings.GEMINI_API_KEY_1,
    settings.GEMINI_API_KEY_2,
    settings.GEMINI_API_KEY_3,
]

API_KEYS = [key for key in API_KEYS if key]

def generate_with_fallback(prompt):
    last_error = None
    model_name = settings.MODEL_NAME or "gemini-3.6-flash"

    for key in API_KEYS:
        try:
            client = genai.Client(api_key=key)

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )

            return response.text

        except Exception as e:
            last_error = e
            print(f"Key failed: {e}")
            continue

    raise RuntimeError(
        f"All Gemini API keys failed. Last error: {last_error}"
    )


def generate_with_fallback_ocr(image_bytes, mime_type, prompt):
    last_error = None
    model_name = settings.MODEL_NAME or "gemini-3.6-flash"

    for key in API_KEYS:
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
            print(f"Key failed: {e}")
            continue

    raise RuntimeError(
        f"All Gemini API keys failed. Last error: {last_error}"
    )

def generate_with_fallback_embedding(text):
    last_error = None

    for key in API_KEYS:
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
            print(f"Key failed: {e}")
            continue

    raise RuntimeError(
        f"All Gemini API keys failed. Last error: {last_error}"
    )