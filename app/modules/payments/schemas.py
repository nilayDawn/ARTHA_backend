from typing import Any

from pydantic import BaseModel, Field


class CheckoutSessionRequest(BaseModel):
    plan_id: str = Field(..., description="Plan identifier: pro_monthly, pro_yearly, enterprise")
    success_url: str = Field(..., description="Redirect URL upon successful payment")
    cancel_url: str = Field(..., description="Redirect URL upon cancellation")


class CheckoutSessionResponse(BaseModel):
    session_id: str
    checkout_url: str
    status: str
    mock: bool | None = False


class SubscriptionStatusResponse(BaseModel):
    user_id: str
    plan: str
    status: str
    features: list[str] = []
