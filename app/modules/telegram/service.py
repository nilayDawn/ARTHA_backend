import datetime
import re
import secrets
from typing import Any

import httpx

from app.core.config import settings
from app.modules.agent.service import AIAgentService
from app.modules.documents.service import DocumentService
from app.modules.finance.service import TransactionService
from app.ports.cache import CachePort
from app.ports.database import UserRepositoryPort
from app.utils.logger import logger


class TelegramService:
    """
    Domain service for Telegram bot interactions.
    Fixes the full-table scan linking bug by using direct indexed code queries.
    Handles Telegram webhook processing, typing actions, OCR receipts, and PDF bank statements.
    """

    def __init__(
        self,
        user_repo: UserRepositoryPort,
        agent_service: AIAgentService,
        doc_service: DocumentService,
        tx_service: TransactionService,
        cache: CachePort,
    ):
        self.user_repo = user_repo
        self.agent_service = agent_service
        self.doc_service = doc_service
        self.tx_service = tx_service
        self.cache = cache
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""

    async def send_message(self, chat_id: int | str, text: str) -> bool:
        if not self.api_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(f"{self.api_url}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                })
                return res.status_code == 200
        except Exception as e:
            logger.warning("[Telegram Send Error]: %s", e)
            return False

    async def send_chat_action(self, chat_id: int | str, action: str = "typing") -> None:
        if not self.api_url:
            return
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(f"{self.api_url}/sendChatAction", json={
                    "chat_id": chat_id,
                    "action": action,
                })
        except Exception:
            pass

    def get_or_create_link_code(self, user_id: str, force_refresh: bool = False) -> dict[str, Any]:
        cache_key = f"telegram_link_code:{user_id}"
        if not force_refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # Generate single-use link code
        new_code = f"FP-{secrets.randbelow(9000) + 1000}"
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = now + datetime.timedelta(minutes=10)

        self.user_repo.set_telegram_link_code(user_id, new_code, expires_at.isoformat())
        result = {"code": new_code, "expires_in_seconds": 600}
        self.cache.set(cache_key, result, ttl_seconds=60)
        return result

    def verify_and_bind_code(self, code: str, chat_id: int | str) -> str | None:
        """Direct indexed code verification replacing linear table scan."""
        clean_code = code.strip().upper()
        user = self.user_repo.get_user_by_link_code(clean_code)
        if not user:
            return None

        exp_str = user.get("telegram_link_code_expires_at")
        if exp_str:
            try:
                exp_dt = datetime.datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                if exp_dt < datetime.datetime.now(datetime.timezone.utc):
                    return None
            except Exception:
                pass

        user_id = user["id"]
        self.user_repo.bind_telegram_chat(user_id, str(chat_id))
        self.user_repo.clear_telegram_link_code(user_id)
        self.cache.invalidate_user(user_id)
        return user_id

    async def handle_webhook_update(self, update_data: dict[str, Any], background_tasks) -> dict[str, str]:
        message = update_data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        photos = message.get("photo", [])
        document = message.get("document", {})

        if not chat_id:
            return {"status": "ignored"}

        # 1. Handle Link Code (FP-XXXX)
        code_match = re.search(r"\b(FP-\d{4})\b", text, re.IGNORECASE)
        if code_match:
            code = code_match.group(1).upper()
            user_id = self.verify_and_bind_code(code, chat_id)
            if user_id:
                background_tasks.add_task(
                    self.send_message,
                    chat_id,
                    "✅ *Account Linked Successfully!* You can now send expense notes, questions, or upload receipt photos directly here.",
                )
            else:
                existing = self.user_repo.get_user_by_telegram_id(chat_id)
                msg = (
                    "✅ *Account Already Connected!* Your Telegram is already linked to your ARTHA account."
                    if existing
                    else "❌ Invalid or expired code. Please click 'Connect Telegram' on your web dashboard to generate a fresh code."
                )
                background_tasks.add_task(self.send_message, chat_id, msg)
            return {"status": "ok"}

        # 2. Handle /start or /link
        if text.strip().startswith("/start") or text.strip().startswith("/link"):
            existing = self.user_repo.get_user_by_telegram_id(chat_id)
            msg = (
                "✅ *Welcome back to ARTHA AI!* Your account is connected. Ask any question or send an expense note!"
                if existing
                else "👋 Welcome to ARTHA AI!\nTo link your account, visit your web dashboard, click 'Connect Telegram', and send `/link FP-XXXX` here."
            )
            background_tasks.add_task(self.send_message, chat_id, msg)
            return {"status": "ok"}

        # Check linked account
        user = self.user_repo.get_user_by_telegram_id(chat_id)
        if not user:
            background_tasks.add_task(
                self.send_message,
                chat_id,
                "⚠️ Account not linked yet. Please send `/link FP-XXXX` with your dashboard code.",
            )
            return {"status": "ok"}

        user_id = user["id"]

        # 3. Handle PDF Bank Statement
        if document and document.get("mime_type") == "application/pdf":
            file_id = document.get("file_id")
            file_name = document.get("file_name", "statement.pdf")

            async def process_pdf_task():
                try:
                    await self.send_message(chat_id, f"⏳ Processing bank statement *{file_name}* with Gemini AI...")
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        f_res = await client.get(f"{self.api_url}/getFile?file_id={file_id}")
                        f_path = f_res.json()["result"]["file_path"]
                        pdf_res = await client.get(f"https://api.telegram.org/file/bot{self.bot_token}/{f_path}")
                        pdf_bytes = pdf_res.content

                    tx_list = self.doc_service.extract_transactions(pdf_bytes, "application/pdf")
                    if tx_list:
                        payloads = [{
                            "merchant": tx.merchant,
                            "amount": tx.amount,
                            "category": tx.category,
                            "date": tx.date,
                            "source": "telegram_statement_pdf",
                        } for tx in tx_list]
                        self.tx_service.bulk_create_transactions(user_id, payloads)
                        reply = (
                            f"📊 *Bank Statement Imported Successfully!*\n\n"
                            f"• *File:* `{file_name}`\n"
                            f"• *Total Transactions:* {len(tx_list)}\n\n"
                            "All transactions have been added to your dashboard!"
                        )
                    else:
                        reply = "❌ Couldn't parse transactions from that PDF. Please ensure it's a clear, unencrypted bank statement."
                    await self.send_message(chat_id, reply)
                except Exception as err:
                    logger.error("[Telegram PDF error]: %s", err)
                    await self.send_message(chat_id, f"⚠️ Error processing PDF statement: {err}")

            background_tasks.add_task(process_pdf_task)
            return {"status": "ok"}

        # 4. Handle Photo or Image Document Receipt
        is_image_doc = document and document.get("mime_type", "").startswith("image/")
        if photos or is_image_doc:
            file_id = photos[-1]["file_id"] if photos else document.get("file_id")
            mime_type = "image/jpeg" if photos else document.get("mime_type", "image/jpeg")

            async def process_photo_task():
                try:
                    await self.send_message(chat_id, "⏳ *Analyzing receipt image with Gemini AI...*")
                    async with httpx.AsyncClient(timeout=20.0) as client:
                        f_res = await client.get(f"{self.api_url}/getFile?file_id={file_id}")
                        f_path = f_res.json()["result"]["file_path"]
                        img_res = await client.get(f"https://api.telegram.org/file/bot{self.bot_token}/{f_path}")
                        img_bytes = img_res.content

                    txs = self.doc_service.extract_transactions(img_bytes, mime_type)
                    if txs:
                        tx = txs[0]
                        self.tx_service.create_transaction(user_id, {
                            "merchant": tx.merchant,
                            "amount": tx.amount,
                            "category": tx.category,
                            "date": tx.date,
                            "source": "telegram_ocr",
                        })
                        reply = (
                            f"🧾 *Receipt Processed & Logged!*\n\n"
                            f"• *Merchant:* {tx.merchant}\n"
                            f"• *Amount:* ₹{tx.amount}\n"
                            f"• *Category:* {tx.category}\n"
                            f"• *Date:* {tx.date}"
                        )
                    else:
                        reply = "❌ Couldn't parse financial details from that image. Please ensure it's a clear receipt photo."
                    await self.send_message(chat_id, reply)
                except Exception as err:
                    logger.error("[Telegram OCR error]: %s", err)
                    await self.send_message(chat_id, "⚠️ Error processing receipt image. Please try another clear photo.")

            background_tasks.add_task(process_photo_task)
            return {"status": "ok"}

        # 5. Handle Text Query (AI CFO Agent)
        if text:
            async def process_text_task():
                try:
                    await self.send_chat_action(chat_id, "typing")
                    await self.send_message(chat_id, "🤔 *Thinking...*")
                    res = self.agent_service.process_chat(user_id=user_id, message=text)
                    await self.send_message(chat_id, res["response"])
                except Exception as e:
                    logger.error("[Telegram Agent error]: %s", e)
                    await self.send_message(chat_id, "⚠️ Sorry, I encountered an issue processing your request. Please try again.")

            background_tasks.add_task(process_text_task)

        return {"status": "ok"}
