# ARTHA - AI-Powered Personal Finance Assistant
# Copyright (C) 2026  Nilay Dawn <nilaydawn@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.llm.gemini_adapter import custom_api_key_ctx
from app.api.dependencies import get_vector_adapter
from app.api.v1.router import api_router
from app.core.config import settings
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    import anyio.to_thread

    # Scale AnyIO threadpool capacity for synchronous blocking database operations
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = settings.THREADPOOL_LIMIT
    logger.info(
        "Scaled AnyIO worker threadpool capacity to %d tokens for concurrent I/O.",
        settings.THREADPOOL_LIMIT,
    )

    logger.info("Initializing %s backend modular microservices...", settings.PROJECT_NAME)
    vector_adapter = get_vector_adapter()
    vector_adapter.initialize_store()
    logger.info("Vector store initialization check completed.")
    yield


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# Enable CORS for Frontend Development
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://gentle-grass-0ac410700.7.azurestaticapps.net",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def extract_custom_llm_key_middleware(request: Request, call_next):
    """
    Middleware to automatically extract custom user Gemini API Key 
    from 'X-User-LLM-Key' or 'X-Custom-Gemini-Key' header and set it in ContextVar.
    """
    user_key = request.headers.get("X-User-LLM-Key") or request.headers.get("X-Custom-Gemini-Key")
    token = None
    if user_key and user_key.strip():
        token = custom_api_key_ctx.set(user_key.strip())
    try:
        response = await call_next(request)
        return response
    finally:
        if token:
            custom_api_key_ctx.reset(token)


@app.middleware("http")
async def add_security_headers_middleware(request: Request, call_next):
    """
    Injects standard enterprise security headers into all responses.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response





app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def read_root():
    logger.info("Root endpoint / ping received.")
    return {"status": "online", "message": f"{settings.PROJECT_NAME} Backend API is running"}


@app.get("/health")
def health_check():
    logger.debug("Health check request received.")
    return {"status": "healthy"}
