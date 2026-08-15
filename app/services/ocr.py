
from app.core.llm_setup import generate_with_fallback_ocr
from app.schemas.document import BankStatementExtraction, ExtractedTransaction


def extract_transactions_from_document(file_bytes: bytes, mime_type: str) -> list[ExtractedTransaction]:
    """
    Analyzes any financial image or PDF document (bank statement, receipt photo, invoice, statement of account) 
    using Gemini Flash Vision OCR and extracts all individual debit and credit transactions.
    """
    prompt = (
        "Analyze this financial document / bank statement / receipt image or PDF carefully. "
        "Extract ALL individual debit and credit transactions listed in the document. "
        "For each transaction line, extract:\n"
        "- merchant: Name of vendor, merchant, or line item description (e.g. 'Payment - Credit Card', 'Account Transfer In', 'Payment - Electricity', 'Starbucks')\n"
        "- amount: Positive monetary number\n"
        "- category: Appropriate category ('Income' for credit/deposits/transfers in, or 'Food & Dining', 'Shopping', 'Utilities', 'Transport', 'Insurance', 'Loans', 'Bills', 'Entertainment', 'Health', 'Education', 'Other')\n"
        "- date: Transaction date in YYYY-MM-DD format (infer year if missing, e.g. 01/15/26 -> 2026-01-15)\n"
        "- description: Optional brief note or description\n"
        "If it is a statement containing multiple transactions, return EVERY transaction row in the statement."
    )

    # 1. Attempt multi-transaction statement extraction using BankStatementExtraction schema
    try:
        response = generate_with_fallback_ocr(file_bytes, mime_type, prompt, schema=BankStatementExtraction)
        if response:
            extracted = BankStatementExtraction.model_validate_json(response)
            if extracted and extracted.transactions:
                return extracted.transactions
    except Exception as e:
        print(f"[Gemini Multi-Tx Extraction Warning]: {e}")

    # 2. Fallback to single receipt extraction if BankStatementExtraction schema failed
    try:
        response = generate_with_fallback_ocr(file_bytes, mime_type, prompt, schema=ExtractedTransaction)
        if response:
            single_tx = ExtractedTransaction.model_validate_json(response)
            if single_tx and single_tx.amount > 0:
                return [single_tx]
    except Exception as e:
        print(f"[Gemini Single-Tx Extraction Warning]: {e}")

    return []


def process_receipt_with_gemini(image_bytes: bytes, mime_type: str) -> ExtractedTransaction | None:
    txs = extract_transactions_from_document(image_bytes, mime_type)
    return txs[0] if txs else None


def process_bank_statement_pdf_with_gemini(file_bytes: bytes) -> list[ExtractedTransaction]:
    return extract_transactions_from_document(file_bytes, "application/pdf")