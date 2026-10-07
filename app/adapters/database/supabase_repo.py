from typing import Any

from postgrest.exceptions import APIError
from supabase import Client

from app.ports.database import (
    BudgetRepositoryPort,
    DocumentRepositoryPort,
    GoalRepositoryPort,
    TransactionRepositoryPort,
    UserRepositoryPort,
)
from app.utils.logger import logger


class SupabaseTransactionRepository(TransactionRepositoryPort):
    def __init__(self, client: Client):
        self.client = client

    def create_transaction(self, data: dict[str, Any]) -> dict[str, Any]:
        res = self.client.table("transactions").insert(data).execute()
        return res.data[0] if res.data else data

    def bulk_create_transactions(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not items:
            return []
        res = self.client.table("transactions").insert(items).execute()
        return res.data or []

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
        query = self.client.table("transactions").select("*").eq("user_id", user_id)

        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)

        if category and category.strip() and category.strip().lower() != "all":
            cat_clean = category.strip()
            cat_lower = cat_clean.lower()
            if "food" in cat_lower or "dining" in cat_lower:
                query = query.or_("category.ilike.%Food%,category.ilike.%Dining%,category.ilike.%Restaurant%")
            elif "shop" in cat_lower:
                query = query.or_("category.ilike.%Shop%,category.ilike.%Store%")
            elif "health" in cat_lower or "med" in cat_lower:
                query = query.or_("category.ilike.%Health%,category.ilike.%Med%")
            elif "utilit" in cat_lower or "bill" in cat_lower:
                query = query.or_("category.ilike.%Utilit%,category.ilike.%Bill%")
            elif "transport" in cat_lower or "travel" in cat_lower:
                query = query.or_("category.ilike.%Transport%,category.ilike.%Travel%")
            elif "subscript" in cat_lower:
                query = query.or_("category.ilike.%Subscript%")
            elif "entertain" in cat_lower:
                query = query.or_("category.ilike.%Entertain%")
            elif "educat" in cat_lower:
                query = query.or_("category.ilike.%Educat%")
            else:
                query = query.ilike("category", f"%{cat_clean}%")

        if search and search.strip():
            s_clean = search.strip()
            query = query.or_(f"merchant.ilike.%{s_clean}%,category.ilike.%{s_clean}%")

        if type and type.strip():
            t_clean = type.strip().lower()
            if t_clean == "income":
                query = query.ilike("category", "income")
            elif t_clean == "expense":
                query = query.not_.ilike("category", "income")

        query = query.order("date", desc=True)
        if limit:
            query = query.limit(limit)
        if skip:
            query = query.offset(skip)

        res = query.execute()
        return res.data or []

    def get_raw_transactions_in_range(
        self,
        user_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        query = self.client.table("transactions").select("*").eq("user_id", user_id)
        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)
        res = query.execute()
        return res.data or []

    def update_transaction(self, user_id: str, tx_id: str, update_data: dict[str, Any]) -> dict[str, Any] | None:
        clean_id = str(tx_id).strip()
        res = self.client.table("transactions").update(update_data).eq("id", clean_id).eq("user_id", user_id).execute()
        return res.data[0] if res.data else None

    def delete_transaction(self, user_id: str, tx_id: str) -> bool:
        clean_id = str(tx_id).strip()
        try:
            self.client.table("transactions").delete().eq("id", clean_id).eq("user_id", user_id).execute()
            return True
        except (APIError, Exception) as e:
            logger.warning("[Supabase Delete Transaction Error]: %s", e)
            return False


class SupabaseBudgetRepository(BudgetRepositoryPort):
    def __init__(self, client: Client):
        self.client = client

    def create_budget(self, data: dict[str, Any]) -> dict[str, Any]:
        res = self.client.table("budgets").insert(data).execute()
        return res.data[0] if res.data else data

    def get_budgets(self, user_id: str, month: str | None = None) -> list[dict[str, Any]]:
        query = self.client.table("budgets").select("*").eq("user_id", user_id)
        if month and month.strip() and month.strip() != "ALL":
            query = query.eq("month", month.strip())
        res = query.execute()
        return res.data or []

    def delete_budget(self, user_id: str, budget_id: str) -> bool:
        clean_id = str(budget_id).strip()
        try:
            self.client.table("budgets").delete().eq("id", clean_id).eq("user_id", user_id).execute()
            return True
        except (APIError, Exception) as e:
            logger.warning("[Supabase Delete Budget Error]: %s", e)
            return False


class SupabaseGoalRepository(GoalRepositoryPort):
    def __init__(self, client: Client):
        self.client = client

    def create_goal(self, data: dict[str, Any]) -> dict[str, Any]:
        res = self.client.table("goals").insert(data).execute()
        return res.data[0] if res.data else data

    def get_goals(self, user_id: str) -> list[dict[str, Any]]:
        res = self.client.table("goals").select("*").eq("user_id", user_id).execute()
        return res.data or []

    def update_goal(self, user_id: str, goal_id: str, update_data: dict[str, Any]) -> dict[str, Any] | None:
        clean_id = str(goal_id).strip()
        res = self.client.table("goals").update(update_data).eq("id", clean_id).eq("user_id", user_id).execute()
        return res.data[0] if res.data else None

    def delete_goal(self, user_id: str, goal_id: str) -> bool:
        clean_id = str(goal_id).strip()
        try:
            self.client.table("goals").delete().eq("id", clean_id).eq("user_id", user_id).execute()
            return True
        except (APIError, Exception) as e:
            logger.warning("[Supabase Delete Goal Error]: %s", e)
            return False


class SupabaseUserRepository(UserRepositoryPort):
    def __init__(self, client: Client):
        self.client = client

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        res = self.client.table("users").select("id, email, full_name, telegram_chat_id, created_at").eq("id", user_id).execute()
        return res.data[0] if res.data else None

    def get_user_by_telegram_id(self, chat_id: str | int) -> dict[str, Any] | None:
        res = self.client.table("users").select("id, email, full_name, telegram_chat_id, created_at").eq("telegram_chat_id", str(chat_id)).execute()
        return res.data[0] if res.data else None

    def get_user_by_link_code(self, link_code: str) -> dict[str, Any] | None:
        """Direct database lookup by link code, eliminating linear full-table scans."""
        res = (
            self.client.table("users")
            .select("id, telegram_link_code_encrypted, telegram_link_code_expires_at")
            .eq("telegram_link_code_encrypted", link_code.strip().upper())
            .execute()
        )
        return res.data[0] if res.data else None

    def upsert_user(self, user_id: str, email: str, full_name: str) -> dict[str, Any]:
        data = {"id": user_id, "email": email, "full_name": full_name}
        res = self.client.table("users").upsert(data).execute()
        return res.data[0] if res.data else data

    def set_telegram_link_code(self, user_id: str, code: str, expires_at_iso: str) -> bool:
        res = self.client.table("users").update({
            "telegram_link_code_encrypted": code,
            "telegram_link_code_expires_at": expires_at_iso,
        }).eq("id", user_id).execute()
        return bool(res.data)

    def bind_telegram_chat(self, user_id: str, chat_id: str) -> bool:
        res = self.client.table("users").update({"telegram_chat_id": str(chat_id)}).eq("id", user_id).execute()
        return bool(res.data)

    def clear_telegram_link_code(self, user_id: str) -> bool:
        res = self.client.table("users").update({
            "telegram_link_code_encrypted": None,
            "telegram_link_code_expires_at": None,
        }).eq("id", user_id).execute()
        return bool(res.data)


class SupabaseDocumentRepository(DocumentRepositoryPort):
    def __init__(self, client: Client):
        self.client = client

    def create_document(self, data: dict[str, Any]) -> dict[str, Any]:
        res = self.client.table("documents").insert(data).execute()
        return res.data[0] if res.data else data

    def get_documents(self, user_id: str) -> list[dict[str, Any]]:
        res = (
            self.client.table("documents")
            .select("*")
            .eq("user_id", user_id)
            .order("uploaded_date", desc=True)
            .execute()
        )
        return res.data or []

    def get_document_by_id(self, user_id: str, document_id: str) -> dict[str, Any] | None:
        res = (
            self.client.table("documents")
            .select("*")
            .eq("id", document_id)
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0] if res.data else None

    def delete_document(self, user_id: str, document_id: str) -> bool:
        try:
            self.client.table("documents").delete().eq("id", document_id).eq("user_id", user_id).execute()
            return True
        except Exception as e:
            logger.warning("[Supabase Delete Document Error]: %s", e)
            return False
