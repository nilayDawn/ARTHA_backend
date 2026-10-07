import uuid

from app.modules.documents.schemas import (
    BankStatementExtraction,
    DocumentResponse,
    DocumentUploadResponse,
    ExtractedTransaction,
)
from app.modules.finance.service import TransactionService
from app.ports.database import DocumentRepositoryPort
from app.ports.llm import LLMProviderPort
from app.ports.storage import StorageProviderPort
from app.utils.logger import logger

SUPPORTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/heic"]


class DocumentService:
    """
    Domain service for financial document uploads, storage lifecycle,
    and Gemini multimodal OCR parsing for receipts and bank statements.
    """

    def __init__(
        self,
        doc_repo: DocumentRepositoryPort,
        storage_provider: StorageProviderPort,
        llm_provider: LLMProviderPort,
        tx_service: TransactionService,
    ):
        self.doc_repo = doc_repo
        self.storage = storage_provider
        self.llm = llm_provider
        self.tx_service = tx_service

    def extract_transactions(self, file_bytes: bytes, mime_type: str) -> list[ExtractedTransaction]:
        prompt = (
            "Analyze this financial document / bank statement / receipt image or PDF carefully. "
            "Extract ALL individual debit and credit transactions listed in the document. "
            "For each transaction line, extract:\n"
            "- merchant: Name of vendor, merchant, or line item description\n"
            "- amount: Positive monetary number\n"
            "- category: Appropriate category ('Income' for credit/deposits/transfers in, or 'Food & Dining', 'Shopping', 'Utilities', 'Transport', 'Insurance', 'Loans', 'Bills', 'Entertainment', 'Health', 'Education', 'Other')\n"
            "- date: Transaction date in YYYY-MM-DD format (infer year if missing, e.g. 01/15/26 -> 2026-01-15)\n"
            "- description: Optional brief note or description\n"
            "If it is a statement containing multiple transactions, return EVERY transaction row in the statement."
        )

        try:
            res = self.llm.generate_structured(file_bytes, mime_type, prompt, schema=BankStatementExtraction)
            if res:
                extracted = BankStatementExtraction.model_validate_json(res)
                if extracted and extracted.transactions:
                    return extracted.transactions
        except Exception as e:
            logger.warning("[DocumentService Multi-Tx Extraction Warning]: %s", e)

        try:
            res = self.llm.generate_structured(file_bytes, mime_type, prompt, schema=ExtractedTransaction)
            if res:
                single = ExtractedTransaction.model_validate_json(res)
                if single and single.amount > 0:
                    return [single]
        except Exception as e:
            logger.warning("[DocumentService Single-Tx Extraction Warning]: %s", e)

        return []

    async def upload_and_process_document(
        self,
        user_id: str,
        filename: str,
        file_bytes: bytes,
        content_type: str,
    ) -> DocumentUploadResponse:
        file_ext = filename.split(".")[-1].lower() if "." in filename else "jpg"
        mime_type = (content_type or "").lower()
        if not mime_type or mime_type == "application/octet-stream":
            if file_ext in ["jpg", "jpeg"]:
                mime_type = "image/jpeg"
            elif file_ext == "png":
                mime_type = "image/png"
            elif file_ext == "webp":
                mime_type = "image/webp"
            elif file_ext == "pdf":
                mime_type = "application/pdf"
            else:
                mime_type = "image/jpeg"

        # 1. Upload to storage
        storage_path = f"{user_id}/{uuid.uuid4()}.{file_ext}"
        try:
            self.storage.upload_file(storage_path, file_bytes, mime_type)
            signed_url = self.storage.create_signed_url(storage_path, 3600)
        except Exception as e:
            logger.error("[DocumentService Storage Error]: %s", e)
            signed_url = ""

        # 2. Record document metadata
        doc_type = "receipt" if mime_type in SUPPORTED_IMAGE_TYPES else "statement"
        doc_record = self.doc_repo.create_document({
            "user_id": user_id,
            "file_url": storage_path,
            "document_type": doc_type,
        })
        doc_id = str(doc_record.get("id", uuid.uuid4()))

        # 3. Vision OCR extraction & transaction logging
        extracted_txs = self.extract_transactions(file_bytes, mime_type)
        stored_count = 0
        first_tx = extracted_txs[0] if extracted_txs else None

        if extracted_txs:
            payloads = []
            for tx in extracted_txs:
                payloads.append({
                    "amount": float(tx.amount or 0.0),
                    "merchant": str(tx.merchant or "Unknown").strip(),
                    "category": (tx.category or "Other").strip(),
                    "date": str(tx.date or "").strip(),
                    "source": "ocr_upload",
                })
            created_txs = self.tx_service.bulk_create_transactions(user_id, payloads)
            stored_count = len(created_txs)

        msg = (
            f"Document processed! Stored {stored_count} transactions in database successfully."
            if stored_count > 0
            else "Document uploaded, but failed to store extracted transactions." if extracted_txs
            else "Document uploaded successfully!"
        )

        return DocumentUploadResponse(
            document_id=doc_id,
            file_url=storage_path,
            signed_url=signed_url,
            extracted_data=first_tx,
            message=msg,
        )

    def get_user_documents(self, user_id: str) -> list[DocumentResponse]:
        docs = self.doc_repo.get_documents(user_id)
        results = []
        for d in docs:
            signed = self.storage.create_signed_url(d.get("file_url", ""), 3600)
            results.append(DocumentResponse(
                id=str(d.get("id")),
                user_id=str(d.get("user_id")),
                file_url=str(d.get("file_url")),
                signed_url=signed or None,
                document_type=str(d.get("document_type", "receipt")),
                uploaded_date=str(d.get("uploaded_date", "")),
            ))
        return results

    def delete_document(self, user_id: str, document_id: str) -> bool:
        doc = self.doc_repo.get_document_by_id(user_id, document_id)
        if not doc:
            return False

        file_url = doc.get("file_url")
        if file_url:
            self.storage.delete_file(file_url)

        return self.doc_repo.delete_document(user_id, document_id)
