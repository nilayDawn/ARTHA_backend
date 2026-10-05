from typing import Any

from app.core.config import settings
from app.ports.payment import PaymentGatewayPort
from app.utils.logger import logger


class StripePaymentAdapter(PaymentGatewayPort):
    """Stripe Payment Gateway Adapter."""

    def __init__(
        self,
        api_key: str | None = None,
        webhook_secret: str | None = None,
    ):
        self.api_key = api_key or settings.STRIPE_SECRET_KEY or settings.STRIPE_API_KEY
        self.webhook_secret = webhook_secret or settings.STRIPE_WEBHOOK_SECRET

    def _ensure_stripe(self):
        if not self.api_key:
            raise ValueError("Stripe API key (STRIPE_SECRET_KEY or STRIPE_API_KEY) is not configured.")
        import stripe
        stripe.api_key = self.api_key
        return stripe

    def create_checkout_session(
        self,
        user_id: str,
        user_email: str,
        plan_id: str,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        stripe = self._ensure_stripe()

        # Pricing map for plans (e.g. Pro, Premium)
        plan_prices = {
            "pro_monthly": 49900,      # ₹499 in paise / cents
            "pro_yearly": 499900,     # ₹4999 in paise / cents
            "enterprise": 1999900,
        }
        amount = plan_prices.get(plan_id, 49900)

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            customer_email=user_email,
            client_reference_id=user_id,
            line_items=[{
                "price_data": {
                    "currency": "inr",
                    "product_data": {
                        "name": f"ARTHA AI Subscription ({plan_id.replace('_', ' ').title()})",
                        "description": "Unlimited AI CFO analysis, OCR parsing, and real-time Telegram alerts",
                    },
                    "unit_amount": amount,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": user_id, "plan_id": plan_id},
        )

        return {
            "session_id": session.id,
            "checkout_url": session.url,
            "status": "ready",
        }

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature_header: str,
    ) -> dict[str, Any] | None:
        if not self.webhook_secret:
            logger.warning("[Stripe Webhook] STRIPE_WEBHOOK_SECRET is not configured.")
            return None

        stripe = self._ensure_stripe()
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature_header,
                self.webhook_secret,
            )
            return event
        except Exception as e:
            logger.error("[Stripe Webhook Verification Error]: %s", e)
            return None

    def get_subscription_status(self, customer_id: str) -> dict[str, Any] | None:
        stripe = self._ensure_stripe()
        try:
            subs = stripe.Subscription.list(customer=customer_id, status="all", limit=1)
            if subs and subs.data:
                sub = subs.data[0]
                return {
                    "subscription_id": sub.id,
                    "status": sub.status,
                    "current_period_end": sub.current_period_end,
                }
            return {"status": "none"}
        except Exception as e:
            logger.warning("[Stripe Sub Error]: %s", e)
            return None
