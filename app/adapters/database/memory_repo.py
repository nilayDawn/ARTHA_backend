import uuid
from datetime import datetime, timezone
from typing import Any

from app.ports.database import (
    BudgetRepositoryPort,
    DocumentRepositoryPort,
    GoalRepositoryPort,
    TransactionRepositoryPort,
    UserRepositoryPort,
)


class InMemoryTransactionRepository(TransactionRepositoryPort):
    def __init__(self):
        self.transactions: list[dict[str, Any]] = []

    def create_transaction(self, data: dict[str, Any]) -> dict[str, Any]:
        item = dict(data)
        if "id" not in item:
            item["id"] = str(uuid.uuid4())
        if "created_at" not in item:
            item["created_at"] = datetime.now(timezone.utc).isoformat()
        self.transactions.append(item)
        return item

    def bulk_create_transactions(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        created = [self.create_transaction(i) for i in items]
        return created

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
        res = [t for t in self.transactions if t.get("user_id") == user_id]
        if start_date:
            res = [t for t in res if str(t.get("date")) >= start_date]
        if end_date:
            res = [t for t in res if str(t.get("date")) <= end_date]
        if category and category.lower() != "all":
            res = [t for t in res if category.lower() in str(t.get("category", "")).lower()]
        if search:
            res = [
                t for t in res
                if search.lower() in str(t.get("merchant", "")).lower()
                or search.lower() in str(t.get("category", "")).lower()
            ]
        if type:
            if type.lower() == "income":
                res = [t for t in res if str(t.get("category")).lower() == "income" or str(t.get("type")).lower() == "income"]
            else:
                res = [t for t in res if str(t.get("category")).lower() != "income" and str(t.get("type")).lower() != "income"]

        res.sort(key=lambda x: str(x.get("date", "")), reverse=True)
        return res[skip : skip + limit]

    def get_raw_transactions_in_range(
        self,
        user_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        res = [t for t in self.transactions if t.get("user_id") == user_id]
        if start_date:
            res = [t for t in res if str(t.get("date")) >= start_date]
        if end_date:
            res = [t for t in res if str(t.get("date")) <= end_date]
        return res

    def update_transaction(self, user_id: str, tx_id: str, update_data: dict[str, Any]) -> dict[str, Any] | None:
        for t in self.transactions:
            if t.get("id") == tx_id and t.get("user_id") == user_id:
                t.update(update_data)
                return t
        return None

    def delete_transaction(self, user_id: str, tx_id: str) -> bool:
        before_count = len(self.transactions)
        self.transactions = [t for t in self.transactions if not (t.get("id") == tx_id and t.get("user_id") == user_id)]
        return len(self.transactions) < before_count


class InMemoryBudgetRepository(BudgetRepositoryPort):
    def __init__(self):
        self.budgets: list[dict[str, Any]] = []

    def create_budget(self, data: dict[str, Any]) -> dict[str, Any]:
        item = dict(data)
        if "id" not in item:
            item["id"] = str(uuid.uuid4())
        self.budgets.append(item)
        return item

    def get_budgets(self, user_id: str, month: str | None = None) -> list[dict[str, Any]]:
        res = [b for b in self.budgets if b.get("user_id") == user_id]
        if month and month != "ALL":
            res = [b for b in res if b.get("month") == month]
        return res

    def delete_budget(self, user_id: str, budget_id: str) -> bool:
        before = len(self.budgets)
        self.budgets = [b for b in self.budgets if not (b.get("id") == budget_id and b.get("user_id") == user_id)]
        return len(self.budgets) < before


class InMemoryGoalRepository(GoalRepositoryPort):
    def __init__(self):
        self.goals: list[dict[str, Any]] = []

    def create_goal(self, data: dict[str, Any]) -> dict[str, Any]:
        item = dict(data)
        if "id" not in item:
            item["id"] = str(uuid.uuid4())
        self.goals.append(item)
        return item

    def get_goals(self, user_id: str) -> list[dict[str, Any]]:
        return [g for g in self.goals if g.get("user_id") == user_id]

    def update_goal(self, user_id: str, goal_id: str, update_data: dict[str, Any]) -> dict[str, Any] | None:
        for g in self.goals:
            if g.get("id") == goal_id and g.get("user_id") == user_id:
                g.update(update_data)
                return g
        return None

    def delete_goal(self, user_id: str, goal_id: str) -> bool:
        before = len(self.goals)
        self.goals = [g for g in self.goals if not (g.get("id") == goal_id and g.get("user_id") == user_id)]
        return len(self.goals) < before


class InMemoryUserRepository(UserRepositoryPort):
    def __init__(self):
        self.users: dict[str, dict[str, Any]] = {}

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self.users.get(user_id)

    def get_user_by_telegram_id(self, chat_id: str | int) -> dict[str, Any] | None:
        for u in self.users.values():
            if str(u.get("telegram_chat_id")) == str(chat_id):
                return u
        return None

    def get_user_by_link_code(self, link_code: str) -> dict[str, Any] | None:
        code_clean = link_code.strip().upper()
        for u in self.users.values():
            if str(u.get("telegram_link_code_encrypted", "")).strip().upper() == code_clean:
                return u
        return None

    def upsert_user(self, user_id: str, email: str, full_name: str) -> dict[str, Any]:
        u = self.users.get(user_id, {})
        u.update({"id": user_id, "email": email, "full_name": full_name})
        self.users[user_id] = u
        return u

    def set_telegram_link_code(self, user_id: str, code: str, expires_at_iso: str) -> bool:
        if user_id in self.users:
            self.users[user_id]["telegram_link_code_encrypted"] = code
            self.users[user_id]["telegram_link_code_expires_at"] = expires_at_iso
            return True
        return False

    def bind_telegram_chat(self, user_id: str, chat_id: str) -> bool:
        if user_id in self.users:
            self.users[user_id]["telegram_chat_id"] = str(chat_id)
            return True
        return False

    def clear_telegram_link_code(self, user_id: str) -> bool:
        if user_id in self.users:
            self.users[user_id]["telegram_link_code_encrypted"] = None
            self.users[user_id]["telegram_link_code_expires_at"] = None
            return True
        return False


class InMemoryDocumentRepository(DocumentRepositoryPort):
    def __init__(self):
        self.documents: list[dict[str, Any]] = []

    def create_document(self, data: dict[str, Any]) -> dict[str, Any]:
        item = dict(data)
        if "id" not in item:
            item["id"] = str(uuid.uuid4())
        self.documents.append(item)
        return item

    def get_documents(self, user_id: str) -> list[dict[str, Any]]:
        return [d for d in self.documents if d.get("user_id") == user_id]

    def get_document_by_id(self, user_id: str, document_id: str) -> dict[str, Any] | None:
        for d in self.documents:
            if d.get("id") == document_id and d.get("user_id") == user_id:
                return d
        return None

    def delete_document(self, user_id: str, document_id: str) -> bool:
        before = len(self.documents)
        self.documents = [d for d in self.documents if not (d.get("id") == document_id and d.get("user_id") == user_id)]
        return len(self.documents) < before
