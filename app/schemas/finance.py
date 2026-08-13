from datetime import date, datetime

from pydantic import BaseModel


# --- Transactions ---
class TransactionCreate(BaseModel):
    amount: float
    merchant: str | None = "Unknown"
    category: str
    date: date
    source: str | None = "manual"

class TransactionUpdate(BaseModel):
    category: str | None = None
    merchant: str | None = None
    amount: float | None = None
    date: date | None = None

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
    deadline: date | None = None

class GoalResponse(GoalCreate):
    id: str
    user_id: str
    created_at: datetime

class GoalUpdate(BaseModel):
    goal_name: str | None = None
    target_amount: float | None = None
    saved_amount: float | None = None
    deadline: date | None = None