from pydantic import BaseModel, Field


class SpendingCategory(BaseModel):
    id: str
    name: str
    icon: str
    color: str
    description: str | None = None


class MerchantMapping(BaseModel):
    pattern: str
    suggested_category: str
    confidence: float = 1.0


class BudgetTemplate(BaseModel):
    template_name: str
    description: str
    allocations: dict[str, float] = Field(..., description="Category name to percentage allocation (summing to 100%)")
