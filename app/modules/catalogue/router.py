from fastapi import APIRouter, Depends

from app.api.dependencies import get_catalogue_service
from app.modules.catalogue.schemas import (
    BudgetTemplate,
    MerchantMapping,
    SpendingCategory,
)
from app.modules.catalogue.service import CatalogueService

router = APIRouter(prefix="/catalogue", tags=["Catalogue & Categories"])


@router.get("/categories", response_model=list[SpendingCategory])
def get_categories(
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
):
    """Returns the list of standard supported expense & income categories."""
    return catalogue_service.get_categories()


@router.get("/merchants", response_model=list[MerchantMapping])
def get_merchant_rules(
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
):
    """Returns automated merchant-to-category keyword mapping rules."""
    return catalogue_service.get_merchant_rules()


@router.get("/budget-templates", response_model=list[BudgetTemplate])
def get_budget_templates(
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
):
    """Returns predefined budgeting strategies (e.g. 50/30/20 rule)."""
    return catalogue_service.get_budget_templates()
