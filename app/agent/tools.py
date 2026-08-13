import datetime
from typing import Any

from app.core.database import supabase_admin
from app.services.memory import save_user_memory, search_user_memories


def fetch_user_financial_context(user_id: str) -> dict[str, Any]:
    """Retrieves recent transactions, active budgets, and savings goals for the user."""
    try:
        tx_res = (
            supabase_admin.table("transactions")
            .select("*")
            .eq("user_id", user_id)
            .order("date", desc=True)
            .limit(20)
            .execute()
        )
        budget_res = (
            supabase_admin.table("budgets")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        goals_res = (
            supabase_admin.table("goals")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )

        return {
            "recent_transactions": tx_res.data or [],
            "budgets": budget_res.data or [],
            "goals": goals_res.data or [],
        }
    except Exception as e:
        print(f"[DB Tool Error]: {e}")
        return {"recent_transactions": [], "budgets": [], "goals": []}


def fetch_relevant_memories(user_id: str, query: str) -> list[str]:
    """Retrieves relevant user habits and financial goals from Qdrant vector memory."""
    return search_user_memories(user_id, query, limit=5)


def remember_user_preference(user_id: str, memory_text: str, category: str = "preference") -> bool:
    """Stores a long-term preference or habit into Qdrant."""
    return save_user_memory(user_id, memory_text, category)


def create_user_goal_in_db(
    user_id: str,
    goal_name: str,
    target_amount: float,
    saved_amount: float = 0.0,
    deadline: str | None = None,
) -> dict[str, Any]:
    """Inserts a new financial goal into Supabase."""
    try:
        data = {
            "user_id": user_id,
            "goal_name": goal_name,
            "target_amount": float(target_amount),
            "saved_amount": float(saved_amount),
        }
        if deadline:
            data["deadline"] = deadline
        res = supabase_admin.table("goals").insert(data).execute()
        return {"success": True, "data": res.data[0] if res.data else data}
    except Exception as e:
        print(f"[DB Create Goal Error]: {e}")
        return {"success": False, "error": str(e)}


def create_user_transaction_in_db(
    user_id: str,
    amount: float,
    category: str,
    merchant: str = "Unknown",
    date: str | None = None,
) -> dict[str, Any]:
    """Inserts a new transaction into Supabase."""
    try:
        data = {
            "user_id": user_id,
            "amount": float(amount),
            "category": category,
            "merchant": merchant,
            "date": date or datetime.date.today().isoformat(),
            "source": "ai_agent",
        }
        res = supabase_admin.table("transactions").insert(data).execute()
        return {"success": True, "data": res.data[0] if res.data else data}
    except Exception as e:
        print(f"[DB Create Transaction Error]: {e}")
        return {"success": False, "error": str(e)}


def create_user_budget_in_db(
    user_id: str,
    category: str,
    monthly_limit: float,
    month: str | None = None,
) -> dict[str, Any]:
    """Inserts or updates a monthly budget in Supabase."""
    try:
        data = {
            "user_id": user_id,
            "category": category,
            "monthly_limit": float(monthly_limit),
            "month": month or datetime.date.today().strftime("%Y-%m"),
        }
        res = supabase_admin.table("budgets").insert(data).execute()
        return {"success": True, "data": res.data[0] if res.data else data}
    except Exception as e:
        print(f"[DB Create Budget Error]: {e}")
        return {"success": False, "error": str(e)}