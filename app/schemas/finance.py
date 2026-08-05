from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

# --- Transactions ---
class TransactionCreate(BaseModel):
    amount: float
    merchant: Optional[str] = "Unknown"
    category: str
    date: date
    source: Optional[str] = "manual"

class TransactionResponse(TransactionCreate):
    id: str
    user_id: str
    created_at: datetime

# --- Budgets ---
class BudgetCreate(BaseModel):
    category: str
    monthly_limit: float
    month: str  # Format: YYYY-MM

class BudgetResponse(BudgetCreate):
    id: str
    user_id: str
    created_at: datetime

# --- Goals ---
class GoalCreate(BaseModel):
    goal_name: str
    target_amount: float
    saved_amount: Optional[float] = 0.0
    deadline: Optional[date] = None

class GoalResponse(GoalCreate):
    id: str
    user_id: str
    created_at: datetime