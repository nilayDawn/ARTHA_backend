import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from app.schemas.document import DocumentResponse
from app.core.database import supabase_admin
from app.core.security import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/documents", tags=["Documents"])

BUCKET_NAME = settings.BUCKET_NAME

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("receipt"), 
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    
    file_bytes = file.file.read() 
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "bin"
    storage_path = f"{user_id}/{uuid.uuid4()}.{file_extension}"
    
    try:
        # 1. Use supabase_admin for Storage Upload
        upload_res = supabase_admin.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": file.content_type or "application/octet-stream"}
        )
        
        # 2. Use supabase_admin for Database Insert
        doc_record = {
            "user_id": user_id,
            "file_url": storage_path,
            "document_type": document_type
        }
        db_res = supabase_admin.table("documents").insert(doc_record).execute()
        
        if not db_res.data:
            raise HTTPException(status_code=500, detail="Failed to save document metadata")
        
        doc_data = db_res.data[0]
        
        # 3. Use supabase_admin for Signed URL
        signed = supabase_admin.storage.from_(BUCKET_NAME).create_signed_url(storage_path, 3600)
        doc_data["signed_url"] = signed.get("signedUrl") if isinstance(signed, dict) else getattr(signed, "signed_url", None)
        
        return doc_data

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Upload failed: {str(e)}")


@router.get("", response_model=List[DocumentResponse])
def get_user_documents(current_user: dict = Depends(get_current_user)):
    """
    List all documents for the authenticated user, attaching signed URLs for secure access.
    """
    try:
        res = supabase_admin.table("documents").select("*").eq("user_id", current_user["id"]).order("uploaded_date", desc=True).execute()
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
        # Check document ownership
        doc_res = supabase_admin.table("documents").select("*").eq("id", document_id).eq("user_id", current_user["id"]).execute()
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