from datetime import date as dt
from datetime import datetime

from pydantic import BaseModel


# --- Transactions ---
class TransactionCreate(BaseModel):
    amount: float
    merchant: str | None = "Unknown"
    category: str
    date: dt
    source: str | None = "manual"

class TransactionUpdate(BaseModel):
    category: str | None = None
    merchant: str | None = None
    amount: float | None = None
    date: dt | None = None

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
    saved_amount: float | None = 0.0
    deadline: dt | None = None

class GoalResponse(GoalCreate):
    id: str
    user_id: str
    created_at: datetime

class GoalUpdate(BaseModel):
    goal_name: str | None = None
    target_amount: float | None = None
    saved_amount: float | None = None
    deadline: dt | None = None