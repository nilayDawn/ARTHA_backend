from functools import lru_cache

from fastapi import Depends

from app.adapters.cache.redis_cache import RedisCacheAdapter
from app.adapters.database.supabase_repo import (
    SupabaseBudgetRepository,
    SupabaseDocumentRepository,
    SupabaseGoalRepository,
    SupabaseTransactionRepository,
    SupabaseUserRepository,
)
from app.adapters.email.resend_adapter import ResendEmailAdapter
from app.adapters.llm.gemini_adapter import GeminiLLMAdapter
from app.adapters.payment.mock_adapter import MockPaymentAdapter
from app.adapters.payment.stripe_adapter import StripePaymentAdapter
from app.adapters.storage.supabase_storage import SupabaseStorageAdapter
from app.adapters.vector.qdrant_adapter import QdrantVectorAdapter
from app.core.config import settings
from app.core.database import supabase_admin
from app.ports.cache import CachePort
from app.ports.database import (
    BudgetRepositoryPort,
    DocumentRepositoryPort,
    GoalRepositoryPort,
    TransactionRepositoryPort,
    UserRepositoryPort,
)
from app.ports.email import EmailProviderPort
from app.ports.llm import LLMProviderPort
from app.ports.payment import PaymentGatewayPort
from app.ports.storage import StorageProviderPort
from app.ports.vector_store import VectorStorePort
from app.modules.agent.service import AIAgentService, MemoryService
from app.modules.auth.service import AuthService
from app.modules.catalogue.service import CatalogueService
from app.modules.documents.service import DocumentService
from app.modules.finance.service import (
    BudgetService,
    GoalService,
    TransactionService,
)
from app.modules.payments.service import PaymentService
from app.modules.reports.service import NotificationService
from app.modules.telegram.service import TelegramService

# --- ADAPTER FACTORIES (Singletons) ---

@lru_cache
def get_cache_adapter() -> CachePort:
    return RedisCacheAdapter(redis_url=settings.REDIS_URL)


@lru_cache
def get_transaction_repo() -> TransactionRepositoryPort:
    return SupabaseTransactionRepository(client=supabase_admin)


@lru_cache
def get_budget_repo() -> BudgetRepositoryPort:
    return SupabaseBudgetRepository(client=supabase_admin)


@lru_cache
def get_goal_repo() -> GoalRepositoryPort:
    return SupabaseGoalRepository(client=supabase_admin)


@lru_cache
def get_user_repo() -> UserRepositoryPort:
    return SupabaseUserRepository(client=supabase_admin)


@lru_cache
def get_document_repo() -> DocumentRepositoryPort:
    return SupabaseDocumentRepository(client=supabase_admin)


@lru_cache
def get_storage_adapter() -> StorageProviderPort:
    return SupabaseStorageAdapter(client=supabase_admin, bucket_name=settings.BUCKET_NAME)


@lru_cache
def get_llm_adapter() -> LLMProviderPort:
    return GeminiLLMAdapter()


@lru_cache
def get_vector_adapter() -> VectorStorePort:
    return QdrantVectorAdapter(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        collection_name=settings.COLLECTION_NAME,
        vector_size=settings.VECTOR_SIZE or 3072,
    )


@lru_cache
def get_email_adapter() -> EmailProviderPort:
    return ResendEmailAdapter()


@lru_cache
def get_payment_adapter() -> PaymentGatewayPort:
    if settings.STRIPE_SECRET_KEY or settings.STRIPE_API_KEY:
        return StripePaymentAdapter(
            api_key=settings.STRIPE_SECRET_KEY or settings.STRIPE_API_KEY,
            webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    return MockPaymentAdapter()


# --- DOMAIN SERVICES FACTORIES ---

@lru_cache
def get_auth_service(
    user_repo: UserRepositoryPort = Depends(get_user_repo),
    cache: CachePort = Depends(get_cache_adapter),
) -> AuthService:
    return AuthService(user_repo=user_repo, cache=cache)


@lru_cache
def get_transaction_service(
    tx_repo: TransactionRepositoryPort = Depends(get_transaction_repo),
    cache: CachePort = Depends(get_cache_adapter),
) -> TransactionService:
    return TransactionService(tx_repo=tx_repo, cache=cache)


@lru_cache
def get_budget_service(
    budget_repo: BudgetRepositoryPort = Depends(get_budget_repo),
    cache: CachePort = Depends(get_cache_adapter),
) -> BudgetService:
    return BudgetService(budget_repo=budget_repo, cache=cache)


@lru_cache
def get_goal_service(
    goal_repo: GoalRepositoryPort = Depends(get_goal_repo),
    cache: CachePort = Depends(get_cache_adapter),
) -> GoalService:
    return GoalService(goal_repo=goal_repo, cache=cache)


@lru_cache
def get_document_service(
    doc_repo: DocumentRepositoryPort = Depends(get_document_repo),
    storage: StorageProviderPort = Depends(get_storage_adapter),
    llm: LLMProviderPort = Depends(get_llm_adapter),
    tx_service: TransactionService = Depends(get_transaction_service),
) -> DocumentService:
    return DocumentService(doc_repo=doc_repo, storage_provider=storage, llm_provider=llm, tx_service=tx_service)


@lru_cache
def get_memory_service(
    vector_store: VectorStorePort = Depends(get_vector_adapter),
    llm: LLMProviderPort = Depends(get_llm_adapter),
) -> MemoryService:
    return MemoryService(vector_store=vector_store, llm_provider=llm)


@lru_cache
def get_ai_agent_service(
    llm: LLMProviderPort = Depends(get_llm_adapter),
    memory_service: MemoryService = Depends(get_memory_service),
    tx_service: TransactionService = Depends(get_transaction_service),
    budget_service: BudgetService = Depends(get_budget_service),
    goal_service: GoalService = Depends(get_goal_service),
    tx_repo: TransactionRepositoryPort = Depends(get_transaction_repo),
    budget_repo: BudgetRepositoryPort = Depends(get_budget_repo),
    goal_repo: GoalRepositoryPort = Depends(get_goal_repo),
    cache: CachePort = Depends(get_cache_adapter),
) -> AIAgentService:
    return AIAgentService(
        llm=llm,
        memory_service=memory_service,
        tx_service=tx_service,
        budget_service=budget_service,
        goal_service=goal_service,
        tx_repo=tx_repo,
        budget_repo=budget_repo,
        goal_repo=goal_repo,
        cache=cache,
    )


@lru_cache
def get_telegram_service(
    user_repo: UserRepositoryPort = Depends(get_user_repo),
    agent_service: AIAgentService = Depends(get_ai_agent_service),
    doc_service: DocumentService = Depends(get_document_service),
    tx_service: TransactionService = Depends(get_transaction_service),
    cache: CachePort = Depends(get_cache_adapter),
) -> TelegramService:
    return TelegramService(
        user_repo=user_repo,
        agent_service=agent_service,
        doc_service=doc_service,
        tx_service=tx_service,
        cache=cache,
    )


@lru_cache
def get_notification_service(
    email: EmailProviderPort = Depends(get_email_adapter),
    tx_repo: TransactionRepositoryPort = Depends(get_transaction_repo),
    budget_repo: BudgetRepositoryPort = Depends(get_budget_repo),
    goal_repo: GoalRepositoryPort = Depends(get_goal_repo),
) -> NotificationService:
    return NotificationService(
        email_provider=email,
        tx_repo=tx_repo,
        budget_repo=budget_repo,
        goal_repo=goal_repo,
    )


@lru_cache
def get_payment_service(
    gateway: PaymentGatewayPort = Depends(get_payment_adapter),
) -> PaymentService:
    return PaymentService(payment_gateway=gateway)


@lru_cache
def get_catalogue_service() -> CatalogueService:
    return CatalogueService()
