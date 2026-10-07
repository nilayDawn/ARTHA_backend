from abc import ABC, abstractmethod


class StorageProviderPort(ABC):
    """Port for file and document blob storage."""

    @abstractmethod
    def upload_file(self, path: str, file_bytes: bytes, content_type: str) -> str:
        """Uploads file bytes to storage bucket and returns key/path."""

    @abstractmethod
    def create_signed_url(self, path: str, expires_in_seconds: int = 3600) -> str:
        """Creates a secure temporary signed URL for private document download."""

    @abstractmethod
    def delete_file(self, path: str) -> bool:
        """Deletes a file from storage."""
