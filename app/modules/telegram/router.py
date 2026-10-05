from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.api.dependencies import get_telegram_service
from app.core.rate_limiter import RateLimiter
from app.core.security import get_current_user
from app.modules.telegram.service import TelegramService

router = APIRouter(prefix="/telegram", tags=["Telegram"])


@router.post(
    "/link-code",
    dependencies=[Depends(RateLimiter(max_requests=5, window_seconds=60))],
)
def create_telegram_link_code(
    refresh: bool = False,
    current_user: dict = Depends(get_current_user),
    telegram_service: TelegramService = Depends(get_telegram_service),
):
    """
    Fetches the active link code or generates a fresh code directly.
    """
    return telegram_service.get_or_create_link_code(current_user["id"], force_refresh=refresh)


@router.post(
    "/webhook",
    dependencies=[Depends(RateLimiter(max_requests=60, window_seconds=60, by_ip=True))],
)
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    telegram_service: TelegramService = Depends(get_telegram_service),
):
    data = await request.json()
    return await telegram_service.handle_webhook_update(data, background_tasks)
