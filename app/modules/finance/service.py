import calendar
import datetime
import re
from typing import Any

from app.ports.cache import CachePort
from app.ports.database import (
    BudgetRepositoryPort,
    GoalRepositoryPort,
    TransactionRepositoryPort,
)


class TransactionService:
    """
    Core Domain Service for financial ledger management.
    Includes relative date normalization, auto-income categorization,
    cached multi-parameter queries, and summary aggregations.
    """

    def __init__(self, tx_repo: TransactionRepositoryPort, cache: CachePort):
        self.tx_repo = tx_repo
        self.cache = cache

    @staticmethod
    def normalize_date(date_str: str | None) -> str:
        today = datetime.date.today()
        if not date_str or not str(date_str).strip():
            return today.isoformat()

        clean = str(date_str).strip().lower()
        if clean in ("yesterday", "prev day", "previous day"):
            return (today - datetime.timedelta(days=1)).isoformat()
        if clean in ("today", "now"):
            return today.isoformat()
        if clean in ("tomorrow", "next day"):
            return (today + datetime.timedelta(days=1)).isoformat()

        match = re.search(r"(\d+)\s*days?\s*ago", clean)
        if match:
            days_ago = int(match.group(1))
            return (today - datetime.timedelta(days=days_ago)).isoformat()

        try:
            dt = datetime.datetime.strptime(clean[:10], "%Y-%m-%d")
            return dt.date().isoformat()
        except Exception:
            pass

        return today.isoformat()

    @staticmethod
    def auto_tag_income(merchant: str, category: str) -> str:
        m_lower = str(merchant or "").lower()
        c_lower = str(category or "").lower()
        income_kws = ["deposit", "deposite", "transfer in", "credit", "income", "salary", "paycheck", "bonus"]
        if any(kw in m_lower or kw in c_lower for kw in income_kws):
            return "Income"
        return category

    @staticmethod
    def resolve_month_bounds(
        month: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[str | None, str | None]:
        """Resolves effective start and end dates from a YYYY-MM month parameter."""
        eff_start = start_date
        eff_end = end_date
        if month and month.strip() and month.strip() != "ALL":
            m_clean = month.strip()
            if not eff_start:
                eff_start = f"{m_clean}-01"
            if not eff_end:
                try:
                    yr, mn = map(int, m_clean.split("-"))
                    last_day = calendar.monthrange(yr, mn)[1]
                    eff_end = f"{m_clean}-{last_day:02d}"
                except Exception:
                    pass
        return eff_start, eff_end

    def _prepare_transaction(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Normalizes and prepares a transaction dictionary for repository storage."""
        row = dict(data)
        row["user_id"] = user_id
        row["date"] = self.normalize_date(str(row.get("date", "")))
        row["category"] = self.auto_tag_income(
            row.get("merchant", ""),
            row.get("category", "General"),
        )
        if "amount" in row:
            row["amount"] = float(row["amount"])
        return row

    def create_transaction(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        tx_data = self._prepare_transaction(user_id, data)
        created = self.tx_repo.create_transaction(tx_data)
        self.cache.invalidate_user(user_id, prefix=f"transactions:{user_id}")
        self.cache.invalidate_user(user_id, prefix=f"summary:{user_id}")
        return created

    def bulk_create_transactions(self, user_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not items:
            return []
        prepared = [self._prepare_transaction(user_id, it) for it in items]
        created = self.tx_repo.bulk_create_transactions(prepared)
        self.cache.invalidate_user(user_id, prefix=f"transactions:{user_id}")
        self.cache.invalidate_user(user_id, prefix=f"summary:{user_id}")
        return created

    def get_transactions(
        self,
        user_id: str,
        category: str | None = None,
        type: str | None = None,
        search: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        month: str | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        cache_key = f"transactions:{user_id}:{category}:{type}:{search}:{start_date}:{end_date}:{month}:{limit}:{skip}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        eff_start, eff_end = self.resolve_month_bounds(month, start_date, end_date)

        results = self.tx_repo.get_transactions(
            user_id=user_id,
            category=category,
            type=type,
            search=search,
            start_date=eff_start,
            end_date=eff_end,
            limit=limit,
            skip=skip,
        )
        self.cache.set(cache_key, results, ttl_seconds=180)
        return results

    def get_summary(
        self,
        user_id: str,
        month: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        eff_start, eff_end = self.resolve_month_bounds(month, start_date, end_date)

        cache_key = f"summary:{user_id}:{month}:{eff_start}:{eff_end}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        txs = self.tx_repo.get_raw_transactions_in_range(user_id, eff_start, eff_end)

        total_income = 0.0
        total_expenses = 0.0
        category_spending: dict[str, float] = {}

        for tx in txs:
            amt = float(tx.get("amount") or 0.0)
            cat = str(tx.get("category") or "").strip()
            tx_type = str(tx.get("type") or "").strip().lower()

            if cat.lower() == "income" or tx_type == "income":
                total_income += amt
            else:
                total_expenses += amt
                c_key = cat if cat else "Other"
                category_spending[c_key] = category_spending.get(c_key, 0.0) + amt

        savings = max(0.0, total_income - total_expenses)
        savings_rate = round((savings / total_income) * 100, 1) if total_income > 0 else 0.0

        result = {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "savings": savings,
            "savings_rate": savings_rate,
            "count": len(txs),
            "category_spending": category_spending,
        }
        self.cache.set(cache_key, result, ttl_seconds=180)
        return result

    def update_transaction(self, user_id: str, tx_id: str, update_data: dict[str, Any]) -> dict[str, Any] | None:
        data = dict(update_data)
        if data.get("date"):
            data["date"] = self.normalize_date(str(data["date"]))
        res = self.tx_repo.update_transaction(user_id, tx_id, data)
        if res:
            self.cache.invalidate_user(user_id, prefix=f"transactions:{user_id}")
            self.cache.invalidate_user(user_id, prefix=f"summary:{user_id}")
        return res

    def delete_transaction(self, user_id: str, tx_id: str) -> bool:
        success = self.tx_repo.delete_transaction(user_id, tx_id)
        if success:
            self.cache.invalidate_user(user_id, prefix=f"transactions:{user_id}")
            self.cache.invalidate_user(user_id, prefix=f"summary:{user_id}")
        return success


class BudgetService:
    """Domain Service for category monthly budgets."""

    def __init__(self, budget_repo: BudgetRepositoryPort, cache: CachePort):
        self.budget_repo = budget_repo
        self.cache = cache

    def create_budget(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        budget_data = dict(data)
        budget_data["user_id"] = user_id
        res = self.budget_repo.create_budget(budget_data)
        self.cache.invalidate_user(user_id, prefix=f"budgets:{user_id}")
        return res

    def get_budgets(self, user_id: str, month: str | None = None) -> list[dict[str, Any]]:
        cache_key = f"budgets:{user_id}:{month}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        res = self.budget_repo.get_budgets(user_id, month)
        self.cache.set(cache_key, res, ttl_seconds=180)
        return res

    def delete_budget(self, user_id: str, budget_id: str) -> bool:
        success = self.budget_repo.delete_budget(user_id, budget_id)
        if success:
            self.cache.invalidate_user(user_id, prefix=f"budgets:{user_id}")
        return success


class GoalService:
    """Domain Service for financial savings goals."""

    def __init__(self, goal_repo: GoalRepositoryPort, cache: CachePort):
        self.goal_repo = goal_repo
        self.cache = cache

    def create_goal(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        goal_data = dict(data)
        goal_data["user_id"] = user_id
        if goal_data.get("deadline") and hasattr(goal_data["deadline"], "isoformat"):
            goal_data["deadline"] = goal_data["deadline"].isoformat()
        res = self.goal_repo.create_goal(goal_data)
        self.cache.invalidate_user(user_id, prefix=f"goals:{user_id}")
        return res

    def get_goals(self, user_id: str) -> list[dict[str, Any]]:
        cache_key = f"goals:{user_id}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        res = self.goal_repo.get_goals(user_id)
        self.cache.set(cache_key, res, ttl_seconds=180)
        return res

    def update_goal(self, user_id: str, goal_id: str, update_data: dict[str, Any]) -> dict[str, Any] | None:
        data = dict(update_data)
        if data.get("deadline") and hasattr(data["deadline"], "isoformat"):
            data["deadline"] = data["deadline"].isoformat()
        res = self.goal_repo.update_goal(user_id, goal_id, data)
        if res:
            self.cache.invalidate_user(user_id, prefix=f"goals:{user_id}")
        return res

    def delete_goal(self, user_id: str, goal_id: str) -> bool:
        success = self.goal_repo.delete_goal(user_id, goal_id)
        if success:
            self.cache.invalidate_user(user_id, prefix=f"goals:{user_id}")
        return success
