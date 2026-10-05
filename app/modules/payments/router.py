from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.dependencies import get_payment_service
from app.core.security import get_current_user
from app.modules.payments.schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    SubscriptionStatusResponse,
)
from app.modules.payments.service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments & Billing"])


@router.post("/checkout", response_model=CheckoutSessionResponse, status_code=status.HTTP_200_OK)
def create_checkout_session(
    payload: CheckoutSessionRequest,
    current_user: dict = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
):
    try:
        return payment_service.create_checkout(
            user_id=current_user["id"],
            user_email=current_user.get("email", ""),
            plan_id=payload.plan_id,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/subscription", response_model=SubscriptionStatusResponse)
def get_user_subscription(
    current_user: dict = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
):
    return payment_service.get_subscription_status(current_user["id"])


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
    payment_service: PaymentService = Depends(get_payment_service),
):
    payload = await request.body()
    res = payment_service.handle_webhook(payload, stripe_signature or "")
    if res.get("status") == "unverified":
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    return res
