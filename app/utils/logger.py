import logging
import sys

def setup_logging():
    """
    Configures application logging for production and local environments.
    Streams directly to sys.stdout so Azure Log Stream and console can capture logs.
    """
    logger = logging.getLogger("FinPilotAI")
    logger.setLevel(logging.INFO)

    # Clear existing handlers to prevent duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    # Standard log format
    log_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )

    # Console / Stdout Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    return logger

# Initialize global logger instance
logger = setup_logging()