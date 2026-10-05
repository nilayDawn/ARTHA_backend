from abc import ABC, abstractmethod
from typing import Any


class PaymentGatewayPort(ABC):
    """Port for billing, subscriptions, and payment processing."""

    @abstractmethod
    def create_checkout_session(
        self,
        user_id: str,
        user_email: str,
        plan_id: str,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        """Creates a checkout/payment session (e.g. Stripe checkout URL)."""
        pass

    @abstractmethod
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature_header: str,
    ) -> dict[str, Any] | None:
        """Verifies cryptographic signature of incoming webhook and parses event."""
        pass

    @abstractmethod
    def get_subscription_status(self, customer_id: str) -> dict[str, Any] | None:
        """Retrieves subscription state for user."""
        pass
