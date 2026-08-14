
import httpx

from app.core.config import settings


def generate_report_content(user_name: str, financial_data: dict) -> str:
    """Compiles raw financial data into a clean, modern inline-styled HTML email."""
    
    transactions = financial_data.get("transactions", [])
    goals = financial_data.get("goals", [])
    budgets = financial_data.get("budgets", [])
    report_date = financial_data.get("report_date", "")

    # Calculate financial summary metrics
    total_income = sum(tx["amount"] for tx in transactions if tx.get("amount", 0) > 0)
    total_expenses = sum(abs(tx["amount"]) for tx in transactions if tx.get("amount", 0) < 0)
    net_savings = total_income - total_expenses
    savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0

    # Goals Section HTML
    goals_html = ""
    if goals:
        for g in goals:
            target = g.get("target_amount", 1)
            saved = g.get("saved_amount", 0)
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
        goals_html = "<p style='color: #94a3b8; font-size: 14px;'>No active savings goals found for this month.</p>"

    # Recent Transactions Section HTML (Top 5)
    recent_tx_html = ""
    if transactions:
        for tx in transactions[:5]:
            amt = tx.get("amount", 0)
            color = "#16a34a" if amt > 0 else "#dc2626"
            prefix = "+" if amt > 0 else ""
            recent_tx_html += f"""
            <tr style="border-bottom: 1px solid #f1f5f9;">
                <td style="padding: 10px 0; font-size: 14px; color: #334155;">{tx.get('merchant', 'Unknown')}</td>
                <td style="padding: 10px 0; font-size: 14px; color: #64748b;">{tx.get('category', 'General')}</td>
                <td style="padding: 10px 0; font-size: 14px; text-align: right; font-weight: 600; color: {color};">
                    {prefix}₹{abs(amt):,.2f}
                </td>
            </tr>
            """
    else:
        recent_tx_html = "<tr><td colspan='3' style='padding: 10px 0; color: #94a3b8; font-size: 14px;'>No transactions recorded this month.</td></tr>"

    # Full HTML Body
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
            
            <div style="background-color: #4f46e5; padding: 24px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 22px;">📊 Monthly Financial Report</h1>
                <p style="color: #c7d2fe; margin: 6px 0 0 0; font-size: 14px;">{report_date} • Prepared for {user_name}</p>
            </div>

            <div style="padding: 24px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px;">
                    <div style="background-color: #f1f5f9; padding: 16px; border-radius: 8px;">
                        <span style="font-size: 12px; color: #64748b; text-transform: uppercase; font-weight: 600;">Total Income</span>
                        <div style="font-size: 20px; font-weight: 700; color: #16a34a; margin-top: 4px;">₹{total_income:,.2f}</div>
                    </div>
                    <div style="background-color: #f1f5f9; padding: 16px; border-radius: 8px;">
                        <span style="font-size: 12px; color: #64748b; text-transform: uppercase; font-weight: 600;">Total Expenses</span>
                        <div style="font-size: 20px; font-weight: 700; color: #dc2626; margin-top: 4px;">₹{total_expenses:,.2f}</div>
                    </div>
                    <div style="background-color: #f1f5f9; padding: 16px; border-radius: 8px;">
                        <span style="font-size: 12px; color: #64748b; text-transform: uppercase; font-weight: 600;">Net Savings</span>
                        <div style="font-size: 20px; font-weight: 700; color: #2563eb; margin-top: 4px;">₹{net_savings:,.2f}</div>
                    </div>
                    <div style="background-color: #f1f5f9; padding: 16px; border-radius: 8px;">
                        <span style="font-size: 12px; color: #64748b; text-transform: uppercase; font-weight: 600;">Savings Rate</span>
                        <div style="font-size: 20px; font-weight: 700; color: #4f46e5; margin-top: 4px;">{savings_rate:.1f}%</div>
                    </div>
                </div>

                <h3 style="color: #1e293b; font-size: 16px; margin-top: 0; border-bottom: 2px solid #f1f5f9; padding-bottom: 8px;">🎯 Financial Goals</h3>
                {goals_html}

                <h3 style="color: #1e293b; font-size: 16px; margin-top: 24px; border-bottom: 2px solid #f1f5f9; padding-bottom: 8px;">💳 Recent Transactions</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="text-align: left; font-size: 12px; color: #94a3b8; text-transform: uppercase;">
                            <th style="padding-bottom: 8px;">Merchant</th>
                            <th style="padding-bottom: 8px;">Category</th>
                            <th style="padding-bottom: 8px; text-align: right;">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        {recent_tx_html}
                    </tbody>
                </table>
            </div>

            <div style="background-color: #f8fafc; padding: 16px; text-align: center; border-top: 1px solid #e2e8f0;">
                <p style="color: #94a3b8; font-size: 12px; margin: 0;">Sent via FinPilot AI Assistant • Managing your money smarter</p>
            </div>
        </div>
    </body>
    </html>
    """

def send_email_report(to_email: str, subject: str, html_content: str):
    """Dispatches the HTML report using Resend REST API."""
    if not settings.RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY is missing in backend environment variables.")

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "from": settings.EMAIL_FROM,
        "to": [to_email],
        "subject": subject,
        "html": html_content
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, headers=headers, json=payload)
        
        if response.status_code not in (200, 201):
            print(f"[Resend API Error]: {response.status_code} - {response.text}")
            raise Exception(f"Failed to send email via Resend: {response.text}")