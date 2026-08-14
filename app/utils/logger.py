import logging
import sys
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# Define the root Logs directory path
LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "Logs"
LOGS_DIR.mkdir(exist_ok=True, parents=True)

# Generate log filename based on current date (e.g., Logs/logs_2026-06-07.log)
current_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")  # noqa: UP017
LOG_FILE_PATH = LOGS_DIR / f"logs_{current_date_str}.log"


def setup_logging():
    """Configures root application logging to both console and daily file rotation."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers if setup is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Define log format
    log_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )

    # 1. Console Handler (Streams to Terminal)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # 2. File Handler (Streams to root Logs/ directory with daily rotation)
    # backupCount=100 keeps the last 100 days of logs
    file_handler = TimedRotatingFileHandler(
        filename=LOG_FILE_PATH,
        when="midnight",
        interval=1,
        backupCount=100,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)

    # Optional: Silence overly chatty external loggers if needed
    logging.getLogger("uvicorn.access").handlers = logger.handlers
    logging.getLogger("uvicorn.error").handlers = logger.handlers

    return logger


# Initialize global logger instance
logger = setup_logging()