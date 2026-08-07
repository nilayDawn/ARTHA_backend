from typing import List
from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.document import ExtractedTransaction, BankStatementExtraction

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

def process_bank_statement_pdf_with_gemini(file_bytes: bytes) -> List[ExtractedTransaction]:
    """Passes PDF bytes directly to Gemini 2.5 Flash to extract all transactions."""
    if not settings.GEMINI_API_KEY:
        return []

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    prompt = (
        "Analyze this bank statement PDF. Extract all individual debit and credit transactions. "
        "For each transaction, extract the merchant/description, amount (positive number), category "
        "(Food, Groceries, Shopping, Transport, Bills, Entertainment, Healthcare, Education, Income, Others), "
        "and date in YYYY-MM-DD format."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(
                    data=file_bytes,
                    mime_type="application/pdf"
                ),
                prompt
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=BankStatementExtraction,
                temperature=0.1
            )
        )
        
        extracted = BankStatementExtraction.model_validate_json(response.text)
        return extracted.transactions
    except Exception as e:
        print(f"[Gemini PDF OCR Error]: {e}")
        return []