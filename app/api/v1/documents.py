import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.cache import invalidate_user_caches
from app.core.config import settings
from app.core.database import supabase_admin
from app.core.security import get_current_user
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.services.ocr import extract_transactions_from_document

router = APIRouter(prefix="/documents", tags=["Documents"])

BUCKET_NAME = settings.BUCKET_NAME or "financial_documents"
SUPPORTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/heic"]


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Uploads a financial document (receipt photo or PDF statement), runs Gemini 3.6 Flash Vision OCR,
    and automatically creates transaction entries if valid receipt or statement data is extracted.
    """
    user_id = current_user["id"]
    file_bytes = await file.read()
    
    # MIME type detection & fallback from filename
    raw_content_type = (file.content_type or "").lower()
    file_extension = file.filename.split(".")[-1].lower() if "." in (file.filename or "") else "jpg"
    
    mime_type = raw_content_type
    if not mime_type or mime_type == "application/octet-stream":
        if file_extension in ["jpg", "jpeg"]:
            mime_type = "image/jpeg"
        elif file_extension == "png":
            mime_type = "image/png"
        elif file_extension == "webp":
            mime_type = "image/webp"
        elif file_extension == "heic":
            mime_type = "image/heic"
        elif file_extension == "pdf":
            mime_type = "application/pdf"
        else:
            mime_type = "image/jpeg"

    # 1. Upload to Supabase Storage (if available)
    file_path = f"{user_id}/{uuid.uuid4()}.{file_extension}"
    signed_url = ""

    try:
        # Ensure bucket exists
        try:
            supabase_admin.storage.create_bucket(BUCKET_NAME, options={"public": True})
        except Exception:
            pass

        storage_res = supabase_admin.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": mime_type}
        )

        if hasattr(storage_res, 'error') and storage_res.error:
            print(f"[Storage Upload Error]: {storage_res.error}")

        # Generate 1-hour signed URL
        signed_url_res = supabase_admin.storage.from_(BUCKET_NAME).create_signed_url(file_path, 3600)
        signed_url = (
            signed_url_res.get("signedUrl") 
            if isinstance(signed_url_res, dict) 
            else getattr(signed_url_res, "signed_url", "")
        ) or ""
    except Exception as e:
        print(f"[Storage Warning]: {e}")

    # 2. Record Document Metadata in DB
    doc_type = "receipt" if mime_type in SUPPORTED_IMAGE_TYPES else "statement"
    doc_data = {
        "user_id": user_id,
        "file_url": file_path,
        "document_type": doc_type
    }
    
    doc_id = str(uuid.uuid4())
    try:
        doc_res = supabase_admin.table("documents").insert(doc_data).execute()
        if doc_res.data:
            doc_id = doc_res.data[0]["id"]
    except Exception as e:
        print(f"[DB Warning - documents insert]: {e}")

    # 3. AI Vision OCR Extraction (Extracts ALL transactions from receipts or multi-line statements)
    extracted_txs = []
    extracted_data = None
    stored_count = 0
    try:
        extracted_txs = extract_transactions_from_document(file_bytes, mime_type)
        if extracted_txs:
            payloads = []
            for tx in extracted_txs:
                cat = (tx.category or "Other").strip()
                merchant_name = str(tx.merchant or "Unknown").strip()
                
                # Check for income keywords in merchant name or category
                m_lower = merchant_name.lower()
                c_lower = cat.lower()
                if any(kw in m_lower or kw in c_lower for kw in ["deposit", "deposite", "transfer in", "credit", "income", "salary"]):
                    cat = "Income"
                
                # Normalize date to YYYY-MM-DD format
                tx_date = str(tx.date or "").strip()
                if not tx_date:
                    import datetime
                    tx_date = datetime.date.today().isoformat()

                payloads.append({
                    "user_id": user_id,
                    "amount": float(tx.amount or 0.0),
                    "merchant": merchant_name,
                    "category": cat,
                    "date": tx_date,
                    "source": "ocr_upload"
                })
            
            # Batch insert transactions into DB
            res = supabase_admin.table("transactions").insert(payloads).execute()
            if res.data:
                stored_count = len(res.data)
                # Clear user Redis/memory cache so transactions appear instantly on frontend
                invalidate_user_caches(user_id)
                extracted_data = extracted_txs[0]
            else:
                print(f"[OCR Insert Notice]: Database insert returned empty result for {len(payloads)} payloads.")
    except Exception as err:
        print(f"[OCR DB Insert Exception]: {err}")

    msg = (
        f"Document processed! Stored {stored_count} transactions in database successfully."
        if stored_count > 0
        else "Document uploaded, but failed to store extracted transactions." if extracted_txs
        else "Document uploaded successfully!"
    )

    return DocumentUploadResponse(
        document_id=doc_id,
        file_url=file_path,
        signed_url=signed_url,
        extracted_data=extracted_data,
        message=msg
    )


@router.get("", response_model=list[DocumentResponse])
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
        
        # Remove from DB enforcing user_id security filter
        supabase_admin.table("documents").delete().eq("id", document_id).eq("user_id", current_user["id"]).execute()
        
        return {"status": "success", "message": "Document deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))