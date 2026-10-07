from abc import ABC, abstractmethod


class EmailProviderPort(ABC):
    """Port for sending transactional and reporting emails."""

    @abstractmethod
    def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Dispatches an email to the recipient with HTML content."""
