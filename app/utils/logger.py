import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_logging():
    """Configures application logging.

    Uses stdout for cloud/container environments (Azure) and optional
    rotating file logs when running locally in development.
    """
    logger = logging.getLogger("FinPilotAI")
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers if setup is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Standard production log format
    log_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )

    # 1. Console Handler (Streams to Azure Log Stream / Terminal)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # 2. File Handler (Only enabled locally when running outside Azure App Service)
    # Azure sets WEBSITE_RUN_FROM_PACKAGE or WEBSITE_SITE_NAME in its environment
    is_azure = bool(
        os.getenv("WEBSITE_RUN_FROM_PACKAGE") or os.getenv("WEBSITE_SITE_NAME")
    )

    if not is_azure:
        try:
            logs_dir = Path(__file__).resolve().parent.parent.parent / "Logs"
            logs_dir.mkdir(exist_ok=True, parents=True)
            current_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            log_file_path = logs_dir / f"logs_{current_date_str}.log"

            file_handler = TimedRotatingFileHandler(
                filename=log_file_path,
                when="midnight",
                interval=1,
                backupCount=30,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(log_format)
            logger.addHandler(file_handler)
        except OSError:
            # Fallback gracefully if filesystem is read-only
            pass

    return logger


# Initialize global logger instance
logger = setup_logging()