from abc import ABC, abstractmethod
from typing import Any


class TransactionRepositoryPort(ABC):
    """Port for transaction persistence operations."""

    @abstractmethod
    def create_transaction(self, data: dict[str, Any]) -> dict[str, Any]:
        pass

    @abstractmethod
    def bulk_create_transactions(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def get_transactions(
        self,
        user_id: str,
        category: str | None = None,
        type: str | None = None,
        search: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def get_raw_transactions_in_range(
        self,
        user_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def update_transaction(self, user_id: str, tx_id: str, update_data: dict[str, Any]) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def delete_transaction(self, user_id: str, tx_id: str) -> bool:
        pass


class BudgetRepositoryPort(ABC):
    """Port for budget persistence operations."""

    @abstractmethod
    def create_budget(self, data: dict[str, Any]) -> dict[str, Any]:
        pass

    @abstractmethod
    def get_budgets(self, user_id: str, month: str | None = None) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def delete_budget(self, user_id: str, budget_id: str) -> bool:
        pass


class GoalRepositoryPort(ABC):
    """Port for savings goals persistence operations."""

    @abstractmethod
    def create_goal(self, data: dict[str, Any]) -> dict[str, Any]:
        pass

    @abstractmethod
    def get_goals(self, user_id: str) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def update_goal(self, user_id: str, goal_id: str, update_data: dict[str, Any]) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def delete_goal(self, user_id: str, goal_id: str) -> bool:
        pass


class UserRepositoryPort(ABC):
    """Port for user profile, identity and Telegram link persistence."""

    @abstractmethod
    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def get_user_by_telegram_id(self, chat_id: str | int) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def get_user_by_link_code(self, link_code: str) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def upsert_user(self, user_id: str, email: str, full_name: str) -> dict[str, Any]:
        pass

    @abstractmethod
    def set_telegram_link_code(self, user_id: str, code: str, expires_at_iso: str) -> bool:
        pass

    @abstractmethod
    def bind_telegram_chat(self, user_id: str, chat_id: str) -> bool:
        pass

    @abstractmethod
    def clear_telegram_link_code(self, user_id: str) -> bool:
        pass


class DocumentRepositoryPort(ABC):
    """Port for uploaded document metadata persistence."""

    @abstractmethod
    def create_document(self, data: dict[str, Any]) -> dict[str, Any]:
        pass

    @abstractmethod
    def get_documents(self, user_id: str) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def get_document_by_id(self, user_id: str, document_id: str) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def delete_document(self, user_id: str, document_id: str) -> bool:
        pass
