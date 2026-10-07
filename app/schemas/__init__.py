"""
Unified Domain Schemas (Re-exported from app.modules for backward compatibility).
Each domain maintains its authoritative Pydantic models in app.modules.<domain>.schemas.
"""

from app.modules.agent.schemas import (
    ApiKeyValidationRequest,
    ApiKeyValidationResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
)
from app.modules.auth.schemas import (
    AuthTokenResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    UserProfileResponse,
    UserSignIn,
    UserSignUp,
)
from app.modules.catalogue.schemas import (
    BudgetTemplate,
    MerchantMapping,
    SpendingCategory,
)
from app.modules.documents.schemas import (
    BankStatementExtraction,
    DocumentResponse,
    DocumentUploadResponse,
    ExtractedTransaction,
)
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

__all__ = [
    # Auth
    "AuthTokenResponse",
    "PasswordResetConfirm",
    "PasswordResetRequest",
    "UserProfileResponse",
    "UserSignIn",
    "UserSignUp",
    # Finance
    "BudgetCreate",
    "BudgetResponse",
    "GoalCreate",
    "GoalResponse",
    "GoalUpdate",
    "TransactionCreate",
    "TransactionResponse",
    "TransactionUpdate",
    # Documents
    "BankStatementExtraction",
    "DocumentResponse",
    "DocumentUploadResponse",
    "ExtractedTransaction",
    # Agent
    "ApiKeyValidationRequest",
    "ApiKeyValidationResponse",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    # Catalogue
    "BudgetTemplate",
    "MerchantMapping",
    "SpendingCategory",
]
