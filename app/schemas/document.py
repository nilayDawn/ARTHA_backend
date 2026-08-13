
from pydantic import BaseModel, Field


# Gemini Extraction Schema
class ExtractedTransaction(BaseModel):
    merchant: str = Field(..., description="Name of the merchant or store, e.g. Starbucks, Amazon, Walmart")
    amount: float = Field(..., description="Total monetary amount spent")
    category: str = Field(
        ..., 
        description="Category of expense: Food, Groceries, Shopping, Transport, Bills, Entertainment, Healthcare, Education, or Others"
    )
    date: str = Field(..., description="Transaction date in YYYY-MM-DD format")
    description: str | None = Field(None, description="Brief summary or itemized breakdown of items bought")

# Response when uploading a document
class DocumentUploadResponse(BaseModel):
    document_id: str
    file_url: str
    signed_url: str
    extracted_data: ExtractedTransaction | None = None
    message: str

# Response for listing documents (matches public.documents table rows)
class DocumentResponse(BaseModel):
    id: str
    user_id: str
    file_url: str
    signed_url: str | None = None
    document_type: str
    uploaded_date: str

class BankStatementExtraction(BaseModel):
    transactions: list[ExtractedTransaction]