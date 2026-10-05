from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_auth_service,
    get_budget_service,
    get_catalogue_service,
    get_document_service,
    get_goal_service,
    get_notification_service,
    get_payment_service,
    get_telegram_service,
    get_transaction_service,
)
from app.core.security import get_current_user
from app.main import app
from app.modules.agent.schemas import ChatMessage, ChatRequest, ChatResponse
from app.modules.agent.service import AIAgentService, MemoryService
from app.modules.auth.schemas import UserSignIn, UserSignUp
from app.modules.auth.service import AuthService
from app.modules.catalogue.service import CatalogueService
from app.modules.documents.schemas import ExtractedTransaction
from app.modules.documents.service import DocumentService
from app.modules.finance.schemas import BudgetCreate, GoalCreate, TransactionCreate
from app.modules.finance.service import (
    BudgetService,
    GoalService,
    TransactionService,
)
from app.modules.payments.service import PaymentService
from app.modules.reports.service import NotificationService
from app.modules.telegram.service import TelegramService
from app.templates import render_email_template


def test_modules_service_instantiation():
    """Verify that all 8 domain microservices instantiate properly."""
    assert AuthService is not None
    assert TransactionService is not None
    assert BudgetService is not None
    assert GoalService is not None
    assert DocumentService is not None
    assert AIAgentService is not None
    assert MemoryService is not None
    assert TelegramService is not None
    assert CatalogueService is not None
    assert PaymentService is not None
    assert NotificationService is not None


def test_modules_schemas_validation():
    """Verify schema validation across modular domains."""
    user = UserSignUp(email="test@artha.ai", password="securepassword123", full_name="Nilay")
    assert user.email == "test@artha.ai"

    tx = TransactionCreate(amount=450.0, category="Food & Dining", merchant="Swiggy", date="2026-10-05")
    assert tx.amount == 450.0

    extracted = ExtractedTransaction(merchant="Blue Tokai", amount=280.0, category="Food & Dining", date="2026-10-05")
    assert extracted.merchant == "Blue Tokai"

    chat_req = ChatRequest(message="What is my monthly budget?", history=[ChatMessage(role="user", content="Hi")])
    assert len(chat_req.history) == 1


def test_email_templates_rendering():
    """Verify that email templates load and substitute variables properly."""
    welcome_html = render_email_template("welcome.html", {
        "user_name": "Nilay Dawn",
        "dashboard_url": "https://artha.ai/dashboard",
    })
    assert "Nilay Dawn" in welcome_html
    assert "https://artha.ai/dashboard" in welcome_html
    assert "Welcome to ARTHA AI" in welcome_html

    reset_html = render_email_template("password_reset.html", {
        "user_name": "Nilay Dawn",
        "user_email": "nilay@example.com",
        "reset_url": "https://artha.ai/reset-password?token=xyz123",
    })
    assert "Nilay Dawn" in reset_html
    assert "xyz123" in reset_html
    assert "Password Reset Request" in reset_html

    report_html = render_email_template("monthly_report.html", {
        "report_date": "October 2026",
        "user_name": "Nilay Dawn",
        "total_income": "1,50,000.00",
        "total_expenses": "45,000.00",
        "net_savings": "1,05,000.00",
        "savings_rate": "70.0",
        "budgets_html": "<p>Food: 15,000</p>",
        "goals_html": "<p>Emergency: 1,00,000</p>",
        "transactions_html": "<tr><td>Swiggy</td><td>Food</td><td>450</td></tr>",
    })
    assert "October 2026" in report_html
    assert "1,50,000.00" in report_html
    assert "45,000.00" in report_html
    assert "70.0%" in report_html


def test_modular_catalogue_endpoints():
    """Verify that catalogue domain endpoints respond with standard categories and rules."""
    client = TestClient(app)
    
    res = client.get("/api/v1/catalogue/categories")
    assert res.status_code == 200
    categories = res.json()
    assert len(categories) >= 8
    cat_names = [c["name"] for c in categories]
    assert "Food & Dining" in cat_names
    assert "Income" in cat_names

    res = client.get("/api/v1/catalogue/merchants")
    assert res.status_code == 200
    merchants = res.json()
    assert any(m["pattern"] == "swiggy" for m in merchants)

    res = client.get("/api/v1/catalogue/budget-templates")
    assert res.status_code == 200
    templates = res.json()
    assert any("50/30/20" in t["template_name"] for t in templates)


def test_modular_payments_endpoints():
    """Verify payments domain checkout creation and subscription status."""
    client = TestClient(app)

    fake_user = {"id": "user-pay-123", "email": "payuser@artha.ai"}
    app.dependency_overrides[get_current_user] = lambda: fake_user

    try:
        res = client.get("/api/v1/payments/subscription")
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == "user-pay-123"
        assert "features" in data

        checkout_res = client.post("/api/v1/payments/checkout", json={
            "plan_id": "pro_monthly",
            "success_url": "https://artha.ai/success",
            "cancel_url": "https://artha.ai/cancel",
        })
        assert checkout_res.status_code == 200
        checkout_data = checkout_res.json()
        assert "session_id" in checkout_data
        assert "checkout_url" in checkout_data
    finally:
        app.dependency_overrides.clear()
