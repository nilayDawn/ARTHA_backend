from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.finance.router import router as finance_router
from app.modules.documents.router import router as documents_router
from app.modules.agent.router import router as chat_router
from app.modules.telegram.router import router as telegram_router
from app.modules.reports.router import router as report_router
from app.modules.payments.router import router as payments_router
from app.modules.catalogue.router import router as catalogue_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(finance_router)
api_router.include_router(documents_router)
api_router.include_router(chat_router)
api_router.include_router(telegram_router)
api_router.include_router(report_router)
api_router.include_router(payments_router)
api_router.include_router(catalogue_router)