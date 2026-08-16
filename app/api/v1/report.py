
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.core.database import supabase_admin
from app.core.security import get_current_user
from app.services.email import generate_report_content, send_email_report

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.post("/send-email", status_code=status.HTTP_202_ACCEPTED)
async def send_monthly_report_email(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Fetches the user's financial metrics from Supabase and triggers an async task
    to generate and send an HTML summary email via Resend.
    """
    user_id = current_user["id"]
    user_email = current_user["email"]
    user_name = current_user.get("user_metadata", {}).get("full_name", "User")

    # Fetch user financial records
    tx_res = supabase_admin.table("transactions").select("*").eq("user_id", user_id).execute()
    goals_res = supabase_admin.table("goals").select("*").eq("user_id", user_id).execute()
    budgets_res = supabase_admin.table("budgets").select("*").eq("user_id", user_id).execute()

    financial_data = {
        "transactions": tx_res.data or [],
        "goals": goals_res.data or [],
        "budgets": budgets_res.data or [],
        "report_date": datetime.now().strftime("%B %Y")
    }

    def email_task():
        try:
            html_report = generate_report_content(user_name, financial_data)
            send_email_report(
                to_email=user_email,
                subject=f"📊 Your ARTHA AI Financial Summary - {financial_data['report_date']}",
                html_content=html_report
            )
        except Exception as e:
            print(f"[Email Report Error]: {e}")

    # Process email send asynchronously so HTTP response is instant
    background_tasks.add_task(email_task)

    return {
        "status": "success",
        "message": f"Report is being generated and sent to {user_email}."
    }