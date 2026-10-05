import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.ports.email import EmailProviderPort
from app.utils.logger import logger


class SMTPEmailAdapter(EmailProviderPort):
    """Standard SMTP email adapter."""

    def __init__(
        self,
        server: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        from_email: str | None = None,
    ):
        self.server = server or settings.SMTP_SERVER
        self.port = port or settings.SMTP_PORT or 587
        self.username = username or settings.SMTP_USERNAME
        self.password = password or settings.SMTP_PASSWORD
        self.from_email = from_email or settings.EMAIL_FROM

    def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        if not self.server or not self.username or not self.password:
            logger.warning("[SMTP] SMTP credentials not fully configured.")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = to_email
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(self.server, self.port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.from_email, [to_email], msg.as_string())

            logger.info("[SMTP] Email sent to %s successfully.", to_email)
            return True
        except Exception as e:
            logger.error("[SMTP Error]: %s", e)
            return False
