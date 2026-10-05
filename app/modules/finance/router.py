from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import (
    get_budget_service,
    get_goal_service,
    get_transaction_service,
)
from app.core.security import get_current_user
from app.modules.finance.schemas import (
    BudgetCreate,
    BudgetResponse,
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)
from app.modules.finance.service import (
    BudgetService,
    GoalService,
    TransactionService,
)

router = APIRouter(tags=["Finance"])


# TRANSACTIONS
@router.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction: TransactionCreate,
    current_user: dict = Depends(get_current_user),
    tx_service: TransactionService = Depends(get_transaction_service),
):
    try:
        data = transaction.model_dump()
        return tx_service.create_transaction(current_user["id"], data)
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
    current_user: dict = Depends(get_current_user),
    tx_service: TransactionService = Depends(get_transaction_service),
):
    try:
        return tx_service.get_transactions(
            user_id=current_user["id"],
            category=category,
            type=type,
            search=search,
            start_date=start_date,
            end_date=end_date,
            month=month,
            limit=limit or 100,
            skip=skip or 0,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summary")
def get_financial_summary(
    month: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    tx_service: TransactionService = Depends(get_transaction_service),
):
    try:
        return tx_service.get_summary(
            user_id=current_user["id"],
            month=month,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: str,
    tx_update: TransactionUpdate,
    current_user: dict = Depends(get_current_user),
    tx_service: TransactionService = Depends(get_transaction_service),
):
    update_data = {k: v for k, v in tx_update.model_dump().items() if v is not None}
    res = tx_service.update_transaction(current_user["id"], transaction_id, update_data)
    if not res:
        raise HTTPException(status_code=404, detail="Transaction not found or unauthorized")
    return res


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_200_OK)
def delete_transaction(
    transaction_id: str,
    current_user: dict = Depends(get_current_user),
    tx_service: TransactionService = Depends(get_transaction_service),
):
    tx_service.delete_transaction(current_user["id"], transaction_id)
    return {"message": "Transaction deleted successfully"}


# BUDGETS
@router.post("/budgets", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    budget: BudgetCreate,
    current_user: dict = Depends(get_current_user),
    budget_service: BudgetService = Depends(get_budget_service),
):
    try:
        return budget_service.create_budget(current_user["id"], budget.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating budget: {e!s}")


@router.get("/budgets", response_model=list[BudgetResponse])
def get_budgets(
    month: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    budget_service: BudgetService = Depends(get_budget_service),
):
    try:
        return budget_service.get_budgets(current_user["id"], month)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_200_OK)
def delete_budget(
    budget_id: str,
    current_user: dict = Depends(get_current_user),
    budget_service: BudgetService = Depends(get_budget_service),
):
    budget_service.delete_budget(current_user["id"], budget_id)
    return {"message": "Budget deleted successfully"}


# GOALS
@router.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    goal: GoalCreate,
    current_user: dict = Depends(get_current_user),
    goal_service: GoalService = Depends(get_goal_service),
):
    try:
        return goal_service.create_goal(current_user["id"], goal.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/goals", response_model=list[GoalResponse])
def get_goals(
    current_user: dict = Depends(get_current_user),
    goal_service: GoalService = Depends(get_goal_service),
):
    try:
        return goal_service.get_goals(current_user["id"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/goals/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: str,
    goal_update: GoalUpdate,
    current_user: dict = Depends(get_current_user),
    goal_service: GoalService = Depends(get_goal_service),
):
    update_data = {k: v for k, v in goal_update.model_dump().items() if v is not None}
    res = goal_service.update_goal(current_user["id"], goal_id, update_data)
    if not res:
        raise HTTPException(status_code=404, detail="Goal not found or unauthorized")
    return res


@router.delete("/goals/{goal_id}", status_code=status.HTTP_200_OK)
def delete_goal(
    goal_id: str,
    current_user: dict = Depends(get_current_user),
    goal_service: GoalService = Depends(get_goal_service),
):
    goal_service.delete_goal(current_user["id"], goal_id)
    return {"message": "Goal deleted successfully"}
