import logging
import os
import sys


class ColoredFormatter(logging.Formatter):
    """Custom logging formatter that adds ANSI color coding based on log level."""

    # ANSI escape codes
    GREY = "\033[90m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD_RED = "\033[1;91m"
    RESET = "\033[0m"

    LEVEL_COLORS = {
        logging.DEBUG: CYAN,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED,
    }

    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        asctime = self.formatTime(record, "%Y-%m-%d %H:%M:%S")

        if self.use_color:
            color = self.LEVEL_COLORS.get(record.levelno, self.RESET)
            # Colored layout: dim timestamp, colored level, cyan caller location, clean message
            formatted_log = (
                f"{self.GREY}{asctime}{self.RESET} | "
                f"{color}{record.levelname:<8}{self.RESET} | "
                f"{self.BLUE}{record.name}:{record.funcName}:{record.lineno}{self.RESET} - "
                f"{record.getMessage()}"
            )
        else:
            # Standard plain layout for Azure Log Stream / Files
            formatted_log = (
                f"{asctime} | {record.levelname:<8} | "
                f"{record.name}:{record.funcName}:{record.lineno} - "
                f"{record.getMessage()}"
            )

        if record.exc_info:
            formatted_log += f"\n{self.formatException(record.exc_info)}"

        return formatted_log


def setup_logging():
    """Configures application logging.

    Streams colored logs in interactive terminals (PowerShell / Bash) and plain
    text logs when deployed to Azure App Service / container environments.
    """
    logger = logging.getLogger("ArthaAI")
    logger.setLevel(logging.INFO)

    # Clear existing handlers to prevent duplicate lines
    if logger.hasHandlers():
        logger.handlers.clear()

    # Detect Azure App Service or non-interactive stdout
    is_azure = bool(
        os.getenv("WEBSITE_SITE_NAME") or os.getenv("CONTAINER_APP_NAME")
    )
    is_terminal = (
        sys.stdout.isatty() if hasattr(sys.stdout, "isatty") else False
    )

    # Enable color only in a local interactive terminal outside Azure
    use_color = is_terminal and not is_azure

    # On Windows PowerShell, enable ANSI virtual terminal processing if needed
    if os.name == "nt" and use_color:
        os.system("")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColoredFormatter(use_color=use_color))
    logger.addHandler(console_handler)

    return logger


# Initialize global logger instance
logger = setup_logging()