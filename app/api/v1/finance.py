from fastapi import APIRouter, Depends, HTTPException, Query, status
from postgrest.exceptions import APIError

from app.core.cache import get_cached_data, invalidate_user_caches, set_cached_data
from app.core.database import supabase_admin
from app.core.security import get_current_user
from app.schemas.finance import (
    BudgetCreate,
    BudgetResponse,
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)

router = APIRouter(tags=["Finance"])


# TRANSACTIONS
@router.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(transaction: TransactionCreate, current_user: dict = Depends(get_current_user)):
    data = transaction.model_dump()
    data["user_id"] = current_user["id"]
    data["date"] = data["date"].isoformat()
    
    try:
        res = supabase_admin.table("transactions").insert(data).execute()
        invalidate_user_caches(current_user["id"])
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/transactions", response_model=list[TransactionResponse])
def get_transactions(
    category: str | None = Query(None),
    type: str | None = Query(None),
    search: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    month: str | None = Query(None),
    limit: int | None = Query(100, ge=1, le=1000),
    skip: int | None = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    cache_key = f"transactions:{user_id}:{category}:{type}:{search}:{start_date}:{end_date}:{month}:{limit}:{skip}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    try:
        # Enforce user security isolation in database query
        query = supabase_admin.table("transactions").select("*").eq("user_id", user_id)

        # Month Filtering (YYYY-MM)
        if month and month.strip() and month.strip() != "ALL":
            m_clean = month.strip()
            if not start_date:
                start_date = f"{m_clean}-01"
            if not end_date:
                import calendar
                try:
                    yr, mn = map(int, m_clean.split("-"))
                    last_day = calendar.monthrange(yr, mn)[1]
                    end_date = f"{m_clean}-{last_day:02d}"
                except Exception:
                    pass

        # Date Filtering
        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)

        # Category Filtering
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

        # Search Filtering
        if search and search.strip():
            s_clean = search.strip()
            query = query.or_(f"merchant.ilike.%{s_clean}%,category.ilike.%{s_clean}%")

        # Type Filtering (income / expense)
        if type and type.strip():
            t_clean = type.strip().lower()
            if t_clean == "income":
                query = query.or_("category.ilike.income,type.ilike.income")
            elif t_clean == "expense":
                query = query.not_.or_("category.ilike.income,type.ilike.income")

        # Sorting & Pagination directly in backend database fetch
        query = query.order("date", desc=True)
        if limit:
            query = query.limit(limit)
        if skip:
            query = query.offset(skip)

        res = query.execute()
        result = res.data or []
        set_cached_data(cache_key, result, ttl_seconds=180)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/summary")
def get_financial_summary(
    month: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user["id"]
        query = supabase_admin.table("transactions").select("*").eq("user_id", user_id)

        if month and month.strip() and month.strip() != "ALL":
            m_clean = month.strip()
            if not start_date:
                start_date = f"{m_clean}-01"
            if not end_date:
                import calendar
                try:
                    yr, mn = map(int, m_clean.split("-"))
                    last_day = calendar.monthrange(yr, mn)[1]
                    end_date = f"{m_clean}-{last_day:02d}"
                except Exception:
                    pass

        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)

        res = query.execute()
        txs = res.data or []

        total_income = 0.0
        total_expenses = 0.0
        category_spending = {}

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

        return {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "savings": savings,
            "savings_rate": savings_rate,
            "count": len(txs),
            "category_spending": category_spending
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(transaction_id: str, tx_update: TransactionUpdate, current_user: dict = Depends(get_current_user)):
    update_data = {k: v for k, v in tx_update.model_dump().items() if v is not None}
    if update_data.get("date"):
        update_data["date"] = update_data["date"].isoformat()
    try:
        clean_id = str(transaction_id).strip()
        user_id = current_user["id"]
        # Secure database update scoped to authenticated user
        res = supabase_admin.table("transactions").update(update_data).eq("id", clean_id).eq("user_id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Transaction not found or unauthorized")
        invalidate_user_caches(user_id)
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_200_OK)
def delete_transaction(transaction_id: str, current_user: dict = Depends(get_current_user)):
    try:
        clean_id = str(transaction_id).strip()
        user_id = current_user["id"]
        # Secure database delete scoped to authenticated user
        supabase_admin.table("transactions").delete().eq("id", clean_id).eq("user_id", user_id).execute()
        invalidate_user_caches(user_id)
        return {"message": "Transaction deleted successfully"}
    except (APIError, Exception):
        invalidate_user_caches(current_user["id"])
        return {"message": "Transaction deleted successfully"}


# BUDGETS
@router.post("/budgets", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(budget: BudgetCreate, current_user: dict = Depends(get_current_user)):
    data = budget.model_dump()
    data["user_id"] = current_user["id"]
    
    try:
        res = supabase_admin.table("budgets").insert(data).execute()
        invalidate_user_caches(current_user["id"])
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating budget: {e!s}")

@router.get("/budgets", response_model=list[BudgetResponse])
def get_budgets(month: str | None = Query(None), current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    cache_key = f"budgets:{user_id}:{month}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    try:
        query = supabase_admin.table("budgets").select("*").eq("user_id", user_id)
        if month and month.strip() and month.strip() != "ALL":
            query = query.eq("month", month.strip())
        res = query.execute()
        result = res.data or []
        set_cached_data(cache_key, result, ttl_seconds=180)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/budgets/{budget_id}", status_code=status.HTTP_200_OK)
def delete_budget(budget_id: str, current_user: dict = Depends(get_current_user)):
    try:
        clean_id = str(budget_id).strip()
        user_id = current_user["id"]
        # Secure database delete on budgets table scoped to authenticated user
        supabase_admin.table("budgets").delete().eq("id", clean_id).eq("user_id", user_id).execute()
        invalidate_user_caches(user_id)
        return {"message": "Budget deleted successfully"}
    except (APIError, Exception):
        invalidate_user_caches(current_user["id"])
        return {"message": "Budget deleted successfully"}


# GOALS
@router.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(goal: GoalCreate, current_user: dict = Depends(get_current_user)):
    data = goal.model_dump()
    data["user_id"] = current_user["id"]
    if data["deadline"]:
        data["deadline"] = data["deadline"].isoformat()
        
    try:
        res = supabase_admin.table("goals").insert(data).execute()
        invalidate_user_caches(current_user["id"])
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/goals", response_model=list[GoalResponse])
def get_goals(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    cache_key = f"goals:{user_id}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    try:
        res = supabase_admin.table("goals").select("*").eq("user_id", user_id).execute()
        result = res.data or []
        set_cached_data(cache_key, result, ttl_seconds=180)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/goals/{goal_id}", response_model=GoalResponse)
def update_goal(goal_id: str, goal_update: GoalUpdate, current_user: dict = Depends(get_current_user)):
    update_data = {k: v for k, v in goal_update.model_dump().items() if v is not None}
    if update_data.get("deadline"):
        update_data["deadline"] = update_data["deadline"].isoformat()
    try:
        clean_id = str(goal_id).strip()
        user_id = current_user["id"]
        # Secure database update scoped strictly to authenticated user
        res = supabase_admin.table("goals").update(update_data).eq("id", clean_id).eq("user_id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Goal not found or unauthorized")
        invalidate_user_caches(user_id)
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/goals/{goal_id}", status_code=status.HTTP_200_OK)
def delete_goal(goal_id: str, current_user: dict = Depends(get_current_user)):
    try:
        clean_id = str(goal_id).strip()
        user_id = current_user["id"]
        supabase_admin.table("goals").delete().eq("id", clean_id).eq("user_id", user_id).execute()
        invalidate_user_caches(user_id)
        return {"message": "Goal deleted successfully"}
    except (APIError, Exception):
        invalidate_user_caches(current_user["id"])
        return {"message": "Goal deleted successfully"}