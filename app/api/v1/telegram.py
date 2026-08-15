# This router receives incoming webhooks from Telegram, parses updates (text or photos), resolves the user via telegram_chat_id, and routes to either:

#     Text queries --> financial_agent (LangGraph state machine).
#     Photo receipts --> process_receipt_with_gemini (Gemini 2.5 Flash Vision OCR) + auto-insert transaction.



import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from langchain_core.messages import HumanMessage

from app.agent.graph import financial_agent
from app.core.config import settings
from app.core.database import supabase_admin
from app.core.security import get_current_user
from app.services.ocr import (
    process_bank_statement_pdf_with_gemini,
    process_receipt_with_gemini,
)
from app.services.telegram_auth import get_or_create_link_code, verify_link_code

router = APIRouter(prefix="/telegram", tags=["Telegram"])

TELEGRAM_API_URL = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

async def send_telegram_message(chat_id: int, text: str):
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        })

async def send_telegram_action(chat_id: int, action: str = "typing"):
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{TELEGRAM_API_URL}/sendChatAction", json={
                "chat_id": chat_id,
                "action": action
            })
    except Exception:
        pass

def get_user_by_telegram_id(chat_id: int) -> dict | None:
    res = supabase_admin.table("users").select("id, email, full_name, telegram_chat_id, created_at").eq("telegram_chat_id", str(chat_id)).execute()
    return res.data[0] if res.data else None

@router.post("/link-code")
def create_telegram_link_code(
    refresh: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """
    Fetches the active link code from Supabase DB or generates a new encrypted code.
    If refresh=true, forces generating a new link code.
    """
    return get_or_create_link_code(current_user["id"], force_refresh=refresh)

@router.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    photos = message.get("photo", [])
    document = message.get("document", {})

    if not chat_id:
        return {"status": "ignored"}

    # Handle code linking (e.g. /start FP-XXXX, /link FP-XXXX, or raw FP-XXXX)
    import re
    code_match = re.search(r"\b(FP-\d{4})\b", text, re.IGNORECASE)
    if code_match:
        code = code_match.group(1).upper()
        user_id = verify_link_code(code)
        if user_id:
            supabase_admin.table("users").update({"telegram_chat_id": str(chat_id)}).eq("id", user_id).execute()
            background_tasks.add_task(
                send_telegram_message,
                chat_id,
                "✅ *Account Linked Successfully!* You can now send expense notes, questions, or upload receipt photos directly here."
            )
            return {"status": "ok"}
        else:
            # Check if account is ALREADY linked to this chat_id
            existing_user = get_user_by_telegram_id(chat_id)
            if existing_user:
                background_tasks.add_task(
                    send_telegram_message,
                    chat_id,
                    "✅ *Account Already Connected!* Your Telegram is already linked to your ARTHA account. You can log expenses, ask questions, or upload receipts anytime."
                )
            else:
                background_tasks.add_task(
                    send_telegram_message,
                    chat_id,
                    "❌ Invalid or expired code. Please click 'Connect Telegram' on your web dashboard to generate a fresh code."
                )
            return {"status": "ok"}

    if text.strip().startswith("/start") or text.strip().startswith("/link"):
        existing_user = get_user_by_telegram_id(chat_id)
        if existing_user:
            background_tasks.add_task(
                send_telegram_message,
                chat_id,
                "✅ *Welcome back to ARTHA AI!* Your account is connected. Ask any question or send an expense note!"
            )
        else:
            background_tasks.add_task(
                send_telegram_message,
                chat_id,
                "👋 Welcome to ARTHA AI!\nTo link your account, visit your web dashboard, click 'Connect Telegram', and send `/link FP-XXXX` here."
            )
        return {"status": "ok"}

    # Fetch linked user
    user = get_user_by_telegram_id(chat_id)
    if not user:
        background_tasks.add_task(
            send_telegram_message,
            chat_id,
            "⚠️ Account not linked yet. Please send `/link FP-XXXX` with your dashboard code."
        )
        return {"status": "ok"}

    user_id = user["id"]

    # 📄 HANDLE PDF BANK STATEMENT UPLOADS
    if document and document.get("mime_type") == "application/pdf":
        file_id = document.get("file_id")
        file_name = document.get("file_name", "statement.pdf")

        async def process_pdf_task():
            try:
                await send_telegram_message(chat_id, f"⏳ Processing bank statement *{file_name}* with Gemini AI...")
                
                async with httpx.AsyncClient() as client:
                    f_res = await client.get(f"{TELEGRAM_API_URL}/getFile?file_id={file_id}")
                    file_path = f_res.json()["result"]["file_path"]
                    pdf_res = await client.get(f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}")
                    pdf_bytes = pdf_res.content

                # Extract multiple transactions
                tx_list = process_bank_statement_pdf_with_gemini(pdf_bytes)

                if tx_list:
                    # Prepare rows for bulk insertion into Supabase
                    db_rows = [
                        {
                            "user_id": user_id,
                            "merchant": tx.merchant,
                            "amount": tx.amount,
                            "category": tx.category,
                            "date": tx.date,
                            "source": "telegram_statement_pdf"
                        }
                        for tx in tx_list
                    ]
                    
                    # Bulk insert into Supabase transactions table
                    supabase_admin.table("transactions").insert(db_rows).execute()

                    reply = (
                        f"📊 *Bank Statement Imported Successfully!*\n\n"
                        f"• *File:* `{file_name}`\n"
                        f"• *Total Transactions:* {len(tx_list)}\n\n"
                        f"All transactions have been added to your dashboard!"
                    )
                else:
                    reply = "❌ Couldn't parse transactions from that PDF. Please ensure it's a clear, unencrypted bank statement."

                await send_telegram_message(chat_id, reply)
            except Exception as pdf_err:
                print(f"[Telegram PDF Error]: {pdf_err}")
                await send_telegram_message(chat_id, f"⚠️ Error processing PDF statement: {pdf_err}")

        background_tasks.add_task(process_pdf_task)
        return {"status": "ok"}

    # 🧾 1. ROUTE PHOTO OR IMAGE DOCUMENT (RECEIPT OCR)
    is_image_doc = document and document.get("mime_type", "").startswith("image/")
    if photos or is_image_doc:
        if photos:
            largest_photo = photos[-1]
            file_id = largest_photo["file_id"]
            mime_type = "image/jpeg"
        else:
            file_id = document.get("file_id")
            mime_type = document.get("mime_type", "image/jpeg")

        async def process_photo_task():
            try:
                await send_telegram_message(chat_id, "⏳ *Analyzing receipt image with Gemini AI...*")

                async with httpx.AsyncClient() as client:
                    f_res = await client.get(f"{TELEGRAM_API_URL}/getFile?file_id={file_id}")
                    f_json = f_res.json()
                    if not f_json.get("ok"):
                        await send_telegram_message(chat_id, "❌ Failed to download file from Telegram servers.")
                        return
                    
                    file_path = f_json["result"]["file_path"]
                    img_res = await client.get(f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}")
                    img_bytes = img_res.content

                extracted = process_receipt_with_gemini(img_bytes, mime_type=mime_type)
                if extracted:
                    tx_data = {
                        "user_id": user_id,
                        "merchant": extracted.merchant,
                        "amount": extracted.amount,
                        "category": extracted.category,
                        "date": extracted.date,
                        "source": "telegram_ocr"
                    }
                    supabase_admin.table("transactions").insert(tx_data).execute()
                    reply = (
                        f"🧾 *Receipt Processed & Logged!*\n\n"
                        f"• *Merchant:* {extracted.merchant}\n"
                        f"• *Amount:* ₹{extracted.amount}\n"
                        f"• *Category:* {extracted.category}\n"
                        f"• *Date:* {extracted.date}"
                    )
                else:
                    reply = "❌ Couldn't parse financial details from that image. Please ensure it's a clear receipt photo."
                
                await send_telegram_message(chat_id, reply)
            except Exception as ocr_err:
                print(f"[Telegram OCR Error]: {ocr_err}")
                await send_telegram_message(chat_id, "⚠️ Error processing receipt image. Please check your internet or try another clear photo.")

        background_tasks.add_task(process_photo_task)
        return {"status": "ok"}

    # 2. Route Text Query (LangGraph AI Agent)
    if text:
        async def process_text_task():
            try:
                await send_telegram_action(chat_id, "typing")
                await send_telegram_message(chat_id, "🤔 *Thinking...*")
                
                initial_state = {
                    "messages": [HumanMessage(content=text)],
                    "user_id": user_id,
                    "memories": [],
                    "db_context": {}
                }
                res = financial_agent.invoke(initial_state)
                ai_reply = res["messages"][-1].content
                await send_telegram_message(chat_id, ai_reply)
            except Exception as agent_err:
                print(f"[Telegram Agent Error]: {agent_err}")
                await send_telegram_message(chat_id, "⚠️ Sorry, I encountered an issue processing your request. Please try again.")

        background_tasks.add_task(process_text_task)

    return {"status": "ok"}