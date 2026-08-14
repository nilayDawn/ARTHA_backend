import datetime
from typing import Any

from app.core.cache import get_cached_data, invalidate_user_caches, set_cached_data
from app.core.database import supabase_admin
from app.services.memory import save_user_memory, search_user_memories


def invalidate_user_context_cache(user_id: str):
    """Clears cached financial context for a user after any creation or mutation."""
    invalidate_user_caches(user_id)


def fetch_user_financial_context(user_id: str, force_fresh: bool = False) -> dict[str, Any]:
    """Retrieves recent transactions, active budgets, and savings goals with in-memory TTL caching."""
    cache_key = f"user_financial_context:{user_id}"
    if not force_fresh:
        cached = get_cached_data(cache_key)
        if cached is not None:
            return cached

    try:
        tx_res = (
            supabase_admin.table("transactions")
            .select("amount, category, merchant, date, source")
            .eq("user_id", user_id)
            .order("date", desc=True)
            .limit(15)
            .execute()
        )
        budget_res = (
            supabase_admin.table("budgets")
            .select("category, monthly_limit, month")
            .eq("user_id", user_id)
            .execute()
        )
        goals_res = (
            supabase_admin.table("goals")
            .select("goal_name, target_amount, saved_amount, deadline")
            .eq("user_id", user_id)
            .execute()
        )

        context = {
            "recent_transactions": tx_res.data or [],
            "budgets": budget_res.data or [],
            "goals": goals_res.data or [],
        }
        set_cached_data(cache_key, context, ttl_seconds=180)
        return context
    except Exception as e:
        print(f"[DB Tool Error]: {e}")
        return {"recent_transactions": [], "budgets": [], "goals": []}


def format_compact_financial_context(context: dict[str, Any]) -> str:
    """Formats raw database financial context into an ultra-compact, token-efficient string."""
    txs = context.get("recent_transactions", [])
    budgets = context.get("budgets", [])
    goals = context.get("goals", [])

    tx_summary = ", ".join([f"₹{t.get('amount')}({t.get('category')}/{t.get('merchant')},{t.get('date')})" for t in txs[:10]]) or "None"
    budget_summary = ", ".join([f"{b.get('category')}:₹{b.get('monthly_limit')}/mo" for b in budgets]) or "None"
    goal_summary = ", ".join([f"{g.get('goal_name')}:₹{g.get('saved_amount')}/₹{g.get('target_amount')}" for g in goals]) or "None"

    return f"Tx: [{tx_summary}] | Budgets: [{budget_summary}] | Goals: [{goal_summary}]"


def fetch_relevant_memories(user_id: str, query: str) -> list[str]:
    """Retrieves relevant user habits and financial goals from Qdrant vector memory."""
    return search_user_memories(user_id, query, limit=3)


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
        invalidate_user_context_cache(user_id)
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
        invalidate_user_context_cache(user_id)
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
        invalidate_user_context_cache(user_id)
        return {"success": True, "data": res.data[0] if res.data else data}
    except Exception as e:
        print(f"[DB Create Budget Error]: {e}")
        return {"success": False, "error": str(e)}