from datetime import datetime
from typing import Any

from app.ports.database import (
    BudgetRepositoryPort,
    GoalRepositoryPort,
    TransactionRepositoryPort,
)
from app.ports.email import EmailProviderPort
from app.templates import render_email_template
from app.utils.logger import logger


class NotificationService:
    """Domain service for generating financial report emails and notifications."""

    def __init__(
        self,
        email_provider: EmailProviderPort,
        tx_repo: TransactionRepositoryPort,
        budget_repo: BudgetRepositoryPort,
        goal_repo: GoalRepositoryPort,
    ):
        self.email_provider = email_provider
        self.tx_repo = tx_repo
        self.budget_repo = budget_repo
        self.goal_repo = goal_repo

    def generate_html_report(self, user_name: str, financial_data: dict[str, Any]) -> str:
        transactions = financial_data.get("transactions", [])
        goals = financial_data.get("goals", [])
        budgets = financial_data.get("budgets", [])
        report_date = financial_data.get("report_date", "")

        total_income = sum(
            tx.get("amount", 0) for tx in transactions
            if str(tx.get("category", "")).lower() == "income" or tx.get("amount", 0) > 0
        )
        total_expenses = sum(
            abs(tx.get("amount", 0)) for tx in transactions
            if str(tx.get("category", "")).lower() != "income" and tx.get("amount", 0) < 0
        )
        if total_expenses == 0:
            total_expenses = sum(
                tx.get("amount", 0) for tx in transactions
                if str(tx.get("category", "")).lower() != "income"
            )

        net_savings = max(0.0, total_income - total_expenses)
        savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0

        budgets_html = ""
        if budgets:
            for b in budgets:
                limit = b.get("monthly_limit") or 1.0
                budgets_html += f"""
                <div style="margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; font-size: 14px;">
                        <span style="font-weight: 600; color: #334155;">{b.get('category', 'Category')}</span>
                        <span style="color: #64748b;">₹{limit:,.2f}/mo</span>
                    </div>
                </div>
                """
        else:
            budgets_html = "<p style='color: #94a3b8; font-size: 14px;'>No active budget categories set for this month.</p>"

        goals_html = ""
        if goals:
            for g in goals:
                target = g.get("target_amount", 1.0)
                saved = g.get("saved_amount", 0.0)
                pct = min(int((saved / target) * 100), 100) if target > 0 else 0
                goals_html += f"""
                <div style="margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 4px;">
                        <span style="font-weight: 600; color: #334155;">{g.get('goal_name', 'Goal')}</span>
                        <span style="color: #64748b;">₹{saved:,.2f} / ₹{target:,.2f} ({pct}%)</span>
                    </div>
                    <div style="background-color: #e2e8f0; border-radius: 6px; height: 8px; overflow: hidden;">
                        <div style="background-color: #4f46e5; height: 100%; width: {pct}%;"></div>
                    </div>
                </div>
                """
        else:
            goals_html = "<p style='color: #94a3b8; font-size: 14px;'>No active savings goals found.</p>"

        recent_tx_html = ""
        if transactions:
            for tx in transactions[:5]:
                amt = tx.get("amount", 0)
                color = "#16a34a" if str(tx.get("category", "")).lower() == "income" else "#dc2626"
                recent_tx_html += f"""
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 10px 0; font-size: 14px; color: #334155;">{tx.get('merchant', 'Unknown')}</td>
                    <td style="padding: 10px 0; font-size: 14px; color: #64748b;">{tx.get('category', 'General')}</td>
                    <td style="padding: 10px 0; font-size: 14px; text-align: right; font-weight: 600; color: {color};">₹{amt:,.2f}</td>
                </tr>
                """
        else:
            recent_tx_html = "<tr><td colspan='3' style='padding: 10px 0; color: #94a3b8; font-size: 14px;'>No transactions recorded this month.</td></tr>"

        context = {
            "report_date": report_date,
            "user_name": user_name,
            "total_income": f"{total_income:,.2f}",
            "total_expenses": f"{total_expenses:,.2f}",
            "net_savings": f"{net_savings:,.2f}",
            "savings_rate": f"{savings_rate:.1f}",
            "budgets_html": budgets_html,
            "goals_html": goals_html,
            "transactions_html": recent_tx_html,
        }

        try:
            return render_email_template("monthly_report.html", context)
        except Exception as e:
            logger.warning("[NotificationService Template Fallback]: %s", e)
            # Safe inline fallback if template file is missing
            return f"""
            <html><body style="font-family: sans-serif; padding: 20px;">
                <h2>📊 Monthly Financial Report - {report_date}</h2>
                <p>Prepared for {user_name}</p>
                <p>Income: ₹{total_income:,.2f} | Expenses: ₹{total_expenses:,.2f} | Net Savings: ₹{net_savings:,.2f}</p>
                {budgets_html}
                {goals_html}
            </body></html>
            """

    def send_user_report(self, user_id: str, user_email: str, user_name: str) -> bool:
        txs = self.tx_repo.get_transactions(user_id=user_id, limit=30)
        goals = self.goal_repo.get_goals(user_id=user_id)
        budgets = self.budget_repo.get_budgets(user_id=user_id)
        report_date = datetime.now().strftime("%B %Y")

        html = self.generate_html_report(user_name, {
            "transactions": txs,
            "goals": goals,
            "budgets": budgets,
            "report_date": report_date,
        })

        return self.email_provider.send_email(
            to_email=user_email,
            subject=f"📊 Your ARTHA AI Financial Summary - {report_date}",
            html_content=html,
        )
