from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.dependencies import get_document_service
from app.core.rate_limiter import RateLimiter
from app.core.security import get_current_user
from app.modules.documents.schemas import DocumentResponse, DocumentUploadResponse
from app.modules.documents.service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])

MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "application/pdf",
}


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter(max_requests=10, window_seconds=60))],
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    doc_service: DocumentService = Depends(get_document_service),
):
    content_type = (file.content_type or "").lower()
    file_ext = (file.filename.split(".")[-1].lower() if "." in (file.filename or "") else "")
    
    if content_type not in ALLOWED_MIME_TYPES:
        if file_ext in ["jpg", "jpeg"]:
            content_type = "image/jpeg"
        elif file_ext == "png":
            content_type = "image/png"
        elif file_ext == "webp":
            content_type = "image/webp"
        elif file_ext == "heic":
            content_type = "image/heic"
        elif file_ext == "pdf":
            content_type = "application/pdf"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{content_type}'. Allowed types: JPEG, PNG, WEBP, HEIC, PDF.",
            )

    file_bytes = bytearray()
    chunk_size = 1024 * 1024
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        file_bytes.extend(chunk)
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE if hasattr(status, "HTTP_413_CONTENT_TOO_LARGE") else 413,
                detail="File size exceeds maximum allowed limit of 15MB.",
            )

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        user_id = current_user["id"]
        return await doc_service.upload_and_process_document(
            user_id=user_id,
            filename=file.filename or "receipt.jpg",
            file_bytes=bytes(file_bytes),
            content_type=content_type,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[DocumentResponse])
def get_user_documents(
    current_user: dict = Depends(get_current_user),
    doc_service: DocumentService = Depends(get_document_service),
):
    try:
        return doc_service.get_user_documents(current_user["id"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    doc_service: DocumentService = Depends(get_document_service),
):
    try:
        deleted = doc_service.delete_document(current_user["id"], document_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"status": "success", "message": "Document deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
