from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DocumentResponse(BaseModel):
    id: str
    user_id: str
    file_url: str
    signed_url: Optional[str] = None
    document_type: str
    uploaded_date: datetime