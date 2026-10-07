"""
ARTHA AI — Production Gunicorn Configuration
Supports dynamic auto-detection of CPU cores across local machines,
Docker containers, and Azure App Service (Azure Web Apps).
"""

import multiprocessing
import os

def calculate_workers() -> int:
    """
    Dynamically determines optimal worker count based on system environment.
    Priority:
    1. Explicit WEB_CONCURRENCY environment variable (standard on Azure, Render, Heroku).
    2. Explicit WORKERS environment variable.
    3. Auto-detected container CPU cores via sched_getaffinity (cgroups aware) or cpu_count.
       Formula: min(8, max(2, (2 * cores) + 1))
    """
    if os.getenv("WEB_CONCURRENCY"):
        try:
            return max(1, int(os.getenv("WEB_CONCURRENCY")))
        except ValueError:
            pass

    if os.getenv("WORKERS"):
        try:
            return max(1, int(os.getenv("WORKERS")))
        except ValueError:
            pass

    try:
        cores = len(os.sched_getaffinity(0))
    except (AttributeError, NotImplementedError):
        cores = multiprocessing.cpu_count() or 1

    # Standard ASGI formula: (2 * cores) + 1
    # Bounded between 2 (minimum high-availability) and 8 (to avoid RAM starvation on cloud tiers)
    calculated = (2 * cores) + 1
    return max(2, min(calculated, 8))


# Server Socket
bind = f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '8000')}"

# Worker Processes
workers = calculate_workers()
worker_class = "uvicorn.workers.UvicornWorker"

# Concurrency & Networking
backlog = 2048
keepalive = 65
timeout = 120
graceful_timeout = 30

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

print(f"[ARTHA GUNICORN] Initializing with {workers} Uvicorn workers on {bind}")
