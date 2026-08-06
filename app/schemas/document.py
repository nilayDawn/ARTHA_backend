from pydantic import BaseModel, Field
from typing import Optional

# Gemini Extraction Schema
class ExtractedTransaction(BaseModel):
    merchant: str = Field(..., description="Name of the merchant or store, e.g. Starbucks, Amazon, Walmart")
    amount: float = Field(..., description="Total monetary amount spent")
    category: str = Field(
        ..., 
        description="Category of expense: Food, Groceries, Shopping, Transport, Bills, Entertainment, Healthcare, Education, or Others"
    )
    date: str = Field(..., description="Transaction date in YYYY-MM-DD format")
    description: Optional[str] = Field(None, description="Brief summary or itemized breakdown of items bought")

# Response when uploading a document
class DocumentUploadResponse(BaseModel):
    document_id: str
    file_url: str
    signed_url: str
    extracted_data: Optional[ExtractedTransaction] = None
    message: str

# Response for listing documents (matches public.documents table rows)
class DocumentResponse(BaseModel):
    id: str
    user_id: str
    file_url: str
    signed_url: Optional[str] = None
    document_type: str
    uploaded_date: str