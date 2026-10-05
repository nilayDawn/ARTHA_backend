from datetime import date as dt
from datetime import datetime

from pydantic import BaseModel, Field


# --- Transactions ---
class TransactionCreate(BaseModel):
    amount: float = Field(..., gt=0, le=100_000_000, description="Positive transaction amount up to ₹100,000,000")
    merchant: str = Field(default="Unknown", min_length=1, max_length=120, description="Merchant or vendor name")
    category: str = Field(..., min_length=1, max_length=60, description="Expense or income category")
    date: dt = Field(..., description="Transaction date")
    source: str = Field(default="manual", max_length=50, description="Source of transaction")


class TransactionUpdate(BaseModel):
    category: str | None = Field(None, min_length=1, max_length=60)
    merchant: str | None = Field(None, min_length=1, max_length=120)
    amount: float | None = Field(None, gt=0, le=100_000_000)
    date: dt | None = None


class TransactionResponse(TransactionCreate):
    id: str
    user_id: str
    created_at: datetime


# --- Budgets ---
class BudgetCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=60, description="Category name")
    monthly_limit: float = Field(..., gt=0, le=100_000_000, description="Monthly spending limit")
    month: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Format: YYYY-MM")


class BudgetResponse(BudgetCreate):
    id: str
    user_id: str
    created_at: datetime


# --- Goals ---
class GoalCreate(BaseModel):
    goal_name: str = Field(..., min_length=1, max_length=100, description="Name of financial goal")
    target_amount: float = Field(..., gt=0, le=100_000_000, description="Target savings amount")
    saved_amount: float = Field(default=0.0, ge=0, le=100_000_000, description="Current amount saved")
    deadline: dt | None = Field(None, description="Optional target completion date")


class GoalResponse(GoalCreate):
    id: str
    user_id: str
    created_at: datetime


class GoalUpdate(BaseModel):
    goal_name: str | None = Field(None, min_length=1, max_length=100)
    target_amount: float | None = Field(None, gt=0, le=100_000_000)
    saved_amount: float | None = Field(None, ge=0, le=100_000_000)
    deadline: dt | None = None
