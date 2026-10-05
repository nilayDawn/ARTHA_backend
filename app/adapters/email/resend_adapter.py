import httpx

from app.core.config import settings
from app.ports.email import EmailProviderPort
from app.utils.logger import logger


class ResendEmailAdapter(EmailProviderPort):
    """Email provider adapter for Resend HTTP API."""

    def __init__(self, api_key: str | None = None, from_email: str | None = None):
        self.api_key = api_key or settings.RESEND_API_KEY
        self.from_email = from_email or settings.EMAIL_FROM

    def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        if not self.api_key:
            logger.warning("[Resend] RESEND_API_KEY is not configured.")
            return False

        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": self.from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code in (200, 201):
                logger.info("[Resend] Email sent to %s successfully.", to_email)
                return True
            else:
                logger.error("[Resend Error]: %s - %s", response.status_code, response.text)
                return False
