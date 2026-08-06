import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from app.schemas.document import DocumentUploadResponse, DocumentResponse
from app.core.database import supabase_admin
from app.core.security import get_current_user
from app.core.config import settings
from app.services.ocr import process_receipt_with_gemini

router = APIRouter(prefix="/documents", tags=["Documents"])

BUCKET_NAME = settings.BUCKET_NAME
SUPPORTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/heic"]


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Uploads a financial document (receipt/statement), runs Gemini 2.5 Flash Vision OCR,
    and automatically creates a transaction entry if valid receipt data is extracted.
    """
    user_id = current_user["id"]
    file_bytes = await file.read()
    
    # 1. Generate path and upload to Supabase Storage
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    file_path = f"{user_id}/{uuid.uuid4()}.{file_extension}"

    storage_res = supabase_admin.storage.from_(BUCKET_NAME).upload(
        path=file_path,
        file=file_bytes,
        file_options={"content-type": file.content_type}
    )

    if hasattr(storage_res, 'error') and storage_res.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage upload failed: {storage_res.error}"
        )

    # 2. Record Document Metadata in DB
    doc_data = {
        "user_id": user_id,
        "file_url": file_path,
        "document_type": "receipt" if file.content_type in SUPPORTED_IMAGE_TYPES else "statement"
    }
    
    doc_res = supabase_admin.table("documents").insert(doc_data).execute()
    if not doc_res.data:
        raise HTTPException(status_code=500, detail="Failed to save document metadata.")
        
    created_doc = doc_res.data[0]
    
    # Generate 1-hour signed URL for secure viewing
    signed_url_res = supabase_admin.storage.from_(BUCKET_NAME).create_signed_url(file_path, 3600)
    signed_url = (
        signed_url_res.get("signedUrl") 
        if isinstance(signed_url_res, dict) 
        else getattr(signed_url_res, "signed_url", "")
    )

    # 3. AI Vision OCR Extraction
    extracted_data = None
    if file.content_type in SUPPORTED_IMAGE_TYPES:
        extracted_data = process_receipt_with_gemini(file_bytes, file.content_type)
        
        # If Gemini successfully extracted a transaction, populate the transactions table directly
        if extracted_data:
            transaction_payload = {
                "user_id": user_id,
                "amount": extracted_data.amount,
                "merchant": extracted_data.merchant,
                "category": extracted_data.category,
                "date": extracted_data.date,
                "source": "ocr_upload"
            }
            supabase_admin.table("transactions").insert(transaction_payload).execute()

    return DocumentUploadResponse(
        document_id=created_doc["id"],
        file_url=file_path,
        signed_url=signed_url,
        extracted_data=extracted_data,
        message="Document uploaded and processed successfully!"
    )


@router.get("", response_model=List[DocumentResponse])
def get_user_documents(current_user: dict = Depends(get_current_user)):
    """
    List all documents for the authenticated user, attaching signed URLs for secure access.
    """
    try:
        res = (
            supabase_admin.table("documents")
            .select("*")
            .eq("user_id", current_user["id"])
            .order("uploaded_date", desc=True)
            .execute()
        )
        documents = res.data
        
        for doc in documents:
            # Generate 1-hour signed URL for private bucket access
            signed = supabase_admin.storage.from_(BUCKET_NAME).create_signed_url(doc["file_url"], 3600)
            if isinstance(signed, dict):
                doc["signed_url"] = signed.get("signedUrl")
            elif hasattr(signed, "signed_url"):
                doc["signed_url"] = signed.signed_url
            else:
                doc["signed_url"] = None
                
        return documents
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{document_id}")
def delete_document(document_id: str, current_user: dict = Depends(get_current_user)):
    """
    Delete a document from both Supabase Storage and public.documents table.
    """
    try:
        doc_res = (
            supabase_admin.table("documents")
            .select("*")
            .eq("id", document_id)
            .eq("user_id", current_user["id"])
            .execute()
        )
        if not doc_res.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc = doc_res.data[0]
        
        # Remove from storage
        supabase_admin.storage.from_(BUCKET_NAME).remove([doc["file_url"]])
        
        # Remove from DB
        supabase_admin.table("documents").delete().eq("id", document_id).execute()
        
        return {"status": "success", "message": "Document deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))