from supabase import Client

from app.core.config import settings
from app.ports.storage import StorageProviderPort
from app.utils.logger import logger


class SupabaseStorageAdapter(StorageProviderPort):
    """Storage adapter utilizing Supabase Storage Buckets."""

    def __init__(self, client: Client, bucket_name: str | None = None):
        self.client = client
        self.bucket_name = bucket_name or settings.BUCKET_NAME or "financial_documents"
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            self.client.storage.create_bucket(self.bucket_name, options={"public": True})
        except Exception:
            pass

    def upload_file(self, path: str, file_bytes: bytes, content_type: str) -> str:
        self.client.storage.from_(self.bucket_name).upload(
            path=path,
            file=file_bytes,
            file_options={"content-type": content_type},
        )
        return path

    def create_signed_url(self, path: str, expires_in_seconds: int = 3600) -> str:
        try:
            signed = self.client.storage.from_(self.bucket_name).create_signed_url(path, expires_in_seconds)
            if isinstance(signed, dict):
                return signed.get("signedUrl") or ""
            elif hasattr(signed, "signed_url"):
                return signed.signed_url or ""
            return ""
        except Exception as e:
            logger.warning("[Supabase Storage signed URL error]: %s", e)
            return ""

    def delete_file(self, path: str) -> bool:
        try:
            self.client.storage.from_(self.bucket_name).remove([path])
            return True
        except Exception as e:
            logger.warning("[Supabase Storage remove error]: %s", e)
            return False
