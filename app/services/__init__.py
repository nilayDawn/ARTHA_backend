"""
Domain Microservices Layer (Re-exported from app.modules for backward compatibility).
Each module is self-contained with its own schemas, domain service, and routes.
"""
from app.modules.agent.service import AIAgentService, MemoryService
from app.modules.auth.service import AuthService
from app.modules.catalogue.service import CatalogueService
from app.modules.documents.service import DocumentService
from app.modules.finance.service import (
    BudgetService,
    GoalService,
    TransactionService,
)
from app.modules.reports.service import NotificationService
from app.modules.telegram.service import TelegramService

__all__ = [
    "AIAgentService",
    "AuthService",
    "BudgetService",
    "CatalogueService",
    "DocumentService",
    "GoalService",
    "MemoryService",
    "NotificationService",
    "TelegramService",
    "TransactionService",
]
