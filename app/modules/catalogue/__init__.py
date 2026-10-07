#This catalogue module provides a structured way to manage financial categories, merchant mappings, and budget templates. It defines data models for spending categories, merchant rules, and budget allocation strategies. The service class offers methods to retrieve default categories, merchant rules, and budget templates, facilitating the organization and categorization of financial transactions within the application.

from app.modules.catalogue.schemas import (
    BudgetTemplate,
    MerchantMapping,
    SpendingCategory,
)
from app.modules.catalogue.service import CatalogueService

__all__ = [
    "BudgetTemplate",
    "CatalogueService",
    "MerchantMapping",
    "SpendingCategory",
]
