import uuid
from typing import Any

from app.ports.payment import PaymentGatewayPort
from app.utils.logger import logger


class MockPaymentAdapter(PaymentGatewayPort):
    """Mock Payment Adapter for testing environments."""

    def create_checkout_session(
        self,
        user_id: str,
        user_email: str,
        plan_id: str,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        mock_id = f"cs_test_{uuid.uuid4().hex[:16]}"
        logger.info("[Mock Payment] Created mock checkout session %s for user %s (%s)", mock_id, user_id, plan_id)
        return {
            "session_id": mock_id,
            "checkout_url": f"{success_url}?session_id={mock_id}",
            "status": "ready",
            "mock": True,
        }

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature_header: str,
    ) -> dict[str, Any] | None:
        return {"type": "checkout.session.completed", "mock": True}

    def get_subscription_status(self, customer_id: str) -> dict[str, Any] | None:
        return {"status": "active", "plan": "pro_monthly", "mock": True}
