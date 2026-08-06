import io
from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.document import ExtractedTransaction

def process_receipt_with_gemini(image_bytes: bytes, mime_type: str) -> ExtractedTransaction | None:
    """
    Sends raw image bytes to Gemini 2.5 Flash and enforces structured JSON parsing 
    matching the ExtractedTransaction schema.
    """
    if not settings.GEMINI_API_KEY:
        print("[OCR Error] GEMINI_API_KEY is not configured.")
        return None

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        prompt = """
        Analyze this receipt or financial document image. 
        Extract the merchant/vendor name, total monetary amount, expense category, transaction date, 
        and a short description of the line items.
        If any field is unclear, make your best reasonable inference based on typical receipts.
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                ),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExtractedTransaction,
                temperature=0.1,
            ),
        )

        if response.text:
            extracted_data = ExtractedTransaction.model_validate_json(response.text)
            return extracted_data

    except Exception as e:
        print(f"[Gemini OCR Error]: {e}")
        return None

    return None