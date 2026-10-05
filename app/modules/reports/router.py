from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.api.dependencies import get_notification_service
from app.core.security import get_current_user
from app.modules.reports.service import NotificationService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("/send-email", status_code=status.HTTP_202_ACCEPTED)
async def send_monthly_report_email(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
):
    """
    Fetches the user's financial metrics and triggers an async background task
    to generate and send an HTML summary email via the configured Email Provider (Resend / SMTP).
    """
    user_id = current_user["id"]
    user_email = current_user["email"]
    user_name = current_user.get("user_metadata", {}).get("full_name", "User")

    background_tasks.add_task(
        notification_service.send_user_report,
        user_id=user_id,
        user_email=user_email,
        user_name=user_name,
    )

    return {
        "status": "success",
        "message": f"Report is being generated and sent to {user_email}.",
    }
