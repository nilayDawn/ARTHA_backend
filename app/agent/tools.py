from typing import List, Dict, Any
from app.core.database import supabase_admin
from app.services.memory import search_user_memories, save_user_memory

def fetch_user_financial_context(user_id: str) -> Dict[str, Any]:
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


def fetch_relevant_memories(user_id: str, query: str) -> List[str]:
    """Retrieves relevant user habits and financial goals from Qdrant vector memory."""
    return search_user_memories(user_id, query, limit=5)


def remember_user_preference(user_id: str, memory_text: str, category: str = "preference") -> bool:
    """Stores a long-term preference or habit into Qdrant."""
    return save_user_memory(user_id, memory_text, category)