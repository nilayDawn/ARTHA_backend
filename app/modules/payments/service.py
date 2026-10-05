from typing import Any

from app.modules.payments.schemas import (
    CheckoutSessionResponse,
    SubscriptionStatusResponse,
)
from app.ports.payment import PaymentGatewayPort
from app.utils.logger import logger


class PaymentService:
    """
    Domain service for subscriptions, billing, and Stripe payment gateway coordination.
    """

    def __init__(self, payment_gateway: PaymentGatewayPort):
        self.gateway = payment_gateway

    def create_checkout(
        self,
        user_id: str,
        user_email: str,
        plan_id: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSessionResponse:
        try:
            res = self.gateway.create_checkout_session(
                user_id=user_id,
                user_email=user_email,
                plan_id=plan_id,
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return CheckoutSessionResponse(
                session_id=res["session_id"],
                checkout_url=res["checkout_url"],
                status=res.get("status", "ready"),
                mock=res.get("mock", False),
            )
        except Exception as e:
            logger.error("[PaymentService Error]: %s", e)
            raise

    def handle_webhook(self, payload: bytes, signature_header: str) -> dict[str, Any]:
        event = self.gateway.verify_webhook_signature(payload, signature_header)
        if not event:
            return {"status": "unverified"}

        event_type = event.get("type", "")
        logger.info("[PaymentService] Processed verified webhook event: %s", event_type)
        return {"status": "processed", "event_type": event_type}

    def get_subscription_status(self, user_id: str) -> SubscriptionStatusResponse:
        sub = self.gateway.get_subscription_status(user_id) or {}
        return SubscriptionStatusResponse(
            user_id=user_id,
            plan=sub.get("plan", "free"),
            status=sub.get("status", "active"),
            features=[
                "Personal AI CFO Assistant",
                "Automated Receipt & Bank Statement OCR",
                "Telegram Multi-Modal Assistant",
                "Budget & Goals Analytics",
            ],
        )
