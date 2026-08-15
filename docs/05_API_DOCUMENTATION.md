# 📡 05. REST API Specification & Endpoint Reference

> **Complete OpenAPI Contract & Request/Response Examples**  
> *Detailed reference for Authentication, Financial Ledger, AI Agent Chat, OCR Receipts, Custom LLM API Key Management, Telegram Integration, and Email Summary Reports.*

---

## 🔐 Authentication & Custom LLM Header Requirements

All endpoints except public signup/login routes require a valid Supabase JWT Bearer token:
```http
Authorization: Bearer <YOUR_SUPABASE_JWT_ACCESS_TOKEN>
```

To supply a custom Google Gemini LLM API key per request, include the optional header:
```http
X-User-LLM-Key: <YOUR_CUSTOM_GEMINI_API_KEY>
```
*Note: If provided, the system prioritizes this key for LLM reasoning, OCR parsing, and embeddings, falling back to system-configured keys if inactive or invalid.*

---

## 📌 Endpoint Summary Table

| Category | Method | Endpoint | Description | Cache Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **Auth** | `POST` | `/api/v1/auth/signup` | Register new account | N/A |
| **Auth** | `POST` | `/api/v1/auth/login` | Authenticate user & get JWT | N/A |
| **Auth** | `GET` | `/api/v1/auth/me` | Retrieve profile data | 300s TTL Cache |
| **Finance**| `GET` | `/api/v1/transactions` | Query user transactions | 180s TTL Cache |
| **Finance**| `POST` | `/api/v1/transactions` | Log new transaction | Invalidation Trigger |
| **Finance**| `GET` | `/api/v1/budgets` | Fetch active budgets | 180s TTL Cache |
| **Finance**| `POST` | `/api/v1/budgets` | Set category budget | Invalidation Trigger |
| **Finance**| `GET` | `/api/v1/goals` | Fetch savings goals | 180s TTL Cache |
| **Finance**| `POST` | `/api/v1/goals` | Create savings goal | Invalidation Trigger |
| **Agent** | `POST` | `/api/v1/chat` | Send message to AI CFO | State Machine |
| **Agent** | `POST` | `/api/v1/chat/validate-key` | Validate custom Gemini API Key | Live Ping Test |
| **OCR** | `POST` | `/api/v1/documents/upload` | Upload receipt image for OCR | Gemini Vision |
| **Telegram**|`POST` | `/api/v1/telegram/link-code` | Fetch active or new `FP-XXXX` connection token | 60s TTL Cache / Single Use |
| **Telegram**|`POST` | `/api/v1/telegram/webhook` | Incoming Telegram Bot Updates (Text, Photos, Documents) | Direct Execution |
| **Reports** |`POST` | `/api/v1/reports/send-email` | Send email summary report | Resend Async |

---

## 📝 Request & Response Payload Examples

### 1. AI Chat Endpoint (`POST /api/v1/chat`)

**Request Payload:**
```json
{
  "message": "Spent 250 on lunch yesterday and got 50000 salary deposit today",
  "custom_api_key": "AIzaSy...",
  "history": [
    {"role": "user", "content": "Hi ARTHA"},
    {"role": "assistant", "content": "Hello! How can I assist with your finances today?"}
  ]
}
```

**Response Payload:**
```json
{
  "response": "I've logged your ₹250 lunch expense under Food & Dining for yesterday, and added your ₹50,000 salary deposit under Income!",
  "memories_used": [],
  "user_preferences": ["lunch expense", "salary deposit"]
}
```
*Note: Supports relative dates ("yesterday", "X days ago"), auto-income classification ("salary", "bonus", "deposit"), and executing multiple structured actions in a single conversation turn.*

---

### 2. Validate Custom Gemini API Key (`POST /api/v1/chat/validate-key`)

**Request Payload:**
```json
{
  "api_key": "AIzaSy..."
}
```

**Response Payload:**
```json
{
  "valid": true,
  "message": "Gemini API Key validated successfully!"
}
```

---

### 3. Receipt OCR Upload (`POST /api/v1/documents/upload`)

**Request Payload:** `multipart/form-data` with key `file` containing receipt image (`JPEG, PNG, WEBP, PDF`).

**Response Payload:**
```json
{
  "extracted": {
    "merchant": "AROMAS CAFE",
    "amount": 879.0,
    "category": "Food & Dining",
    "date": "2023-09-24"
  },
  "message": "Receipt parsed successfully"
}
```

---

### 4. Telegram Webhook & Integration (`POST /api/v1/telegram/webhook`)

**Endpoint Behavior:**
- **Authentication Linking:** Parses code matching `/link FP-XXXX`, `/start FP-XXXX`, or raw `FP-XXXX`. Connects Telegram `chat_id` to Supabase user account. Gracefully reports status if account is already linked.
- **Instant Interactive Feedback:** Triggers Telegram's `sendChatAction` (`typing`) and sends an initial `🤔 Thinking...` status message for text queries.
- **Receipt OCR & PDF Import:** Processes photo messages (`photo`) and image files (`document` with `image/*` MIME type) using Gemini Vision OCR, as well as multi-transaction PDF bank statements. Automatically inserts extracted transactions into Supabase.```
