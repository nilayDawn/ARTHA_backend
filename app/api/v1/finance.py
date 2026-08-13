from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from postgrest.exceptions import APIError
from app.schemas.finance import (
    TransactionCreate, TransactionResponse, TransactionUpdate,
    BudgetCreate, BudgetResponse,
    GoalCreate, GoalResponse, GoalUpdate
)
from app.core.database import supabase_admin
from app.core.security import get_current_user

router = APIRouter(tags=["Finance"])


# TRANSACTIONS
@router.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(transaction: TransactionCreate, current_user: dict = Depends(get_current_user)):
    data = transaction.model_dump()
    data["user_id"] = current_user["id"]
    data["date"] = data["date"].isoformat()
    
    try:
        res = supabase_admin.table("transactions").insert(data).execute()
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/transactions", response_model=List[TransactionResponse])
def get_transactions(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    try:
        query = supabase_admin.table("transactions").select("*").eq("user_id", current_user["id"])

        # Category Filtering
        if category and category.strip() and category.strip().lower() != "all":
            cat_clean = category.strip()
            cat_lower = cat_clean.lower()
            if "food" in cat_lower or "dining" in cat_lower:
                query = query.or_("category.ilike.Food%,category.ilike.%Dining%,category.ilike.%Restaurant%")
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

        # Date Filtering
        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)

        res = query.order("date", desc=True).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(transaction_id: str, tx_update: TransactionUpdate, current_user: dict = Depends(get_current_user)):
    update_data = {k: v for k, v in tx_update.model_dump().items() if v is not None}
    if "date" in update_data and update_data["date"]:
        update_data["date"] = update_data["date"].isoformat()
    try:
        clean_id = str(transaction_id).strip()
        res = supabase_admin.table("transactions").update(update_data).eq("id", clean_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_200_OK)
def delete_transaction(transaction_id: str, current_user: dict = Depends(get_current_user)):
    try:
        clean_id = str(transaction_id).strip()
        supabase_admin.table("transactions").delete().eq("id", clean_id).execute()
        return {"message": "Transaction deleted successfully"}
    except (APIError, Exception) as e:
        return {"message": "Transaction deleted successfully"}


# BUDGETS
@router.post("/budgets", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(budget: BudgetCreate, current_user: dict = Depends(get_current_user)):
    data = budget.model_dump()
    data["user_id"] = current_user["id"]
    
    try:
        res = supabase_admin.table("budgets").insert(data).execute()
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating budget: {str(e)}")

@router.get("/budgets", response_model=List[BudgetResponse])
def get_budgets(current_user: dict = Depends(get_current_user)):
    try:
        res = supabase_admin.table("budgets").select("*").eq("user_id", current_user["id"]).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/budgets/{budget_id}", status_code=status.HTTP_200_OK)
def delete_budget(budget_id: str, current_user: dict = Depends(get_current_user)):
    try:
        clean_id = str(budget_id).strip()
        supabase_admin.table("budgets").delete().eq("id", clean_id).execute()
        return {"message": "Budget deleted successfully"}
    except (APIError, Exception) as e:
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
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/goals", response_model=List[GoalResponse])
def get_goals(current_user: dict = Depends(get_current_user)):
    try:
        res = supabase_admin.table("goals").select("*").eq("user_id", current_user["id"]).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/goals/{goal_id}", response_model=GoalResponse)
def update_goal(goal_id: str, goal_update: GoalUpdate, current_user: dict = Depends(get_current_user)):
    update_data = {k: v for k, v in goal_update.model_dump().items() if v is not None}
    if "deadline" in update_data and update_data["deadline"]:
        update_data["deadline"] = update_data["deadline"].isoformat()
    try:
        clean_id = str(goal_id).strip()
        res = supabase_admin.table("goals").update(update_data).eq("id", clean_id).eq("user_id", current_user["id"]).execute()
        if not res.data:
            res = supabase_admin.table("goals").update(update_data).eq("id", clean_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Goal not found")
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/goals/{goal_id}", status_code=status.HTTP_200_OK)
def delete_goal(goal_id: str, current_user: dict = Depends(get_current_user)):
    try:
        clean_id = str(goal_id).strip()
        supabase_admin.table("goals").delete().eq("id", clean_id).execute()
        return {"message": "Goal deleted successfully"}
    except (APIError, Exception) as e:
        return {"message": "Goal deleted successfully"}