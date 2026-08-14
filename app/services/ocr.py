
from app.core.llm_setup import generate_with_fallback_ocr
from app.schemas.document import BankStatementExtraction, ExtractedTransaction


def process_receipt_with_gemini(image_bytes: bytes, mime_type: str) -> ExtractedTransaction | None:
    """
    Sends raw image bytes to Gemini 2.5 Flash and enforces structured JSON parsing 
    matching the ExtractedTransaction schema.
    """

    try:
        
        prompt = """
        Analyze this receipt or financial document image. 
        Extract the merchant/vendor name, total monetary amount, expense category, transaction date, 
        and a short description of the line items.
        If any field is unclear, make your best reasonable inference based on typical receipts.
        """
        
        response = generate_with_fallback_ocr(image_bytes, mime_type, prompt)

        if response:
            extracted = ExtractedTransaction.model_validate_json(response)
            return extracted

    except Exception as e:
        print(f"[Gemini OCR Error]: {e}")
        return None

    return None

def process_bank_statement_pdf_with_gemini(file_bytes: bytes) -> list[ExtractedTransaction]:
    """Passes PDF bytes directly to Gemini 2.5 Flash to extract all transactions."""

    prompt = (
        "Analyze this bank statement PDF. Extract all individual debit and credit transactions. "
        "For each transaction, extract the merchant/description, amount (positive number), category "
        "(Food, Groceries, Shopping, Transport, Bills, Entertainment, Healthcare, Education, Income, Others), "
        "and date in YYYY-MM-DD format."
    )

    try:
        response = generate_with_fallback_ocr(file_bytes, "application/pdf", prompt)
        
        extracted = BankStatementExtraction.model_validate_json(response)
        return extracted.transactions
    except Exception as e:
        print(f"[Gemini PDF OCR Error]: {e}")
        return []