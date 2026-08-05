from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.schemas.finance import (
    TransactionCreate, TransactionResponse,
    BudgetCreate, BudgetResponse,
    GoalCreate, GoalResponse
)
from app.core.database import supabase_admin
from app.core.security import get_current_user

router = APIRouter(tags=["Finance"])


# TRANSACTIONS
@router.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(transaction: TransactionCreate, current_user: dict = Depends(get_current_user)):
    data = transaction.model_dump()
    data["user_id"] = current_user["id"]
    # Convert date to string for JSON serialization
    data["date"] = data["date"].isoformat()
    
    try:
        res = supabase_admin.table("transactions").insert(data).execute()
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/transactions", response_model=List[TransactionResponse])
def get_transactions(current_user: dict = Depends(get_current_user)):
    try:
        res = supabase_admin.table("transactions").select("*").eq("user_id", current_user["id"]).order("date", desc=True).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# BUDGETS
@router.post("/budgets", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(budget: BudgetCreate, current_user: dict = Depends(get_current_user)):
    data = budget.model_dump()
    data["user_id"] = current_user["id"]
    
    try:
        res = supabase_admin.table("budgets").insert(data).execute()
        return res.data[0]
    except Exception as e:
        # Catch unique constraint violations (user_id, category, month)
        raise HTTPException(status_code=400, detail=f"Error creating budget: {str(e)}")

@router.get("/budgets", response_model=List[BudgetResponse])
def get_budgets(current_user: dict = Depends(get_current_user)):
    try:
        res = supabase_admin.table("budgets").select("*").eq("user_id", current_user["id"]).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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