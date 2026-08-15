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
| **Telegram**|`POST` | `/api/v1/telegram/link-code` | Fetch `FP-XXXX` token | 60s TTL Cache |
| **Reports** |`POST` | `/api/v1/reports/send-email` | Send email summary report | Resend Async |

---

## 📝 Request & Response Payload Examples

### 1. AI Chat Endpoint (`POST /api/v1/chat`)

**Request Payload:**
```json
{
  "message": "Add a new goal to save 50000 for iPhone by December",
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
  "response": "I have created a new savings goal for your iPhone with a target amount of ₹50,000!",
  "memories_used": [],
  "user_preferences": ["save 50000 for iPhone by December"]
}
```

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

**Request Payload:** `multipart/form-data` with key `file` containing receipt image (`JPEG, PNG, WEBP`).

**Response Payload:**
```json
{
  "extracted": {
    "merchant": "Starbucks Coffee",
    "amount": 450.0,
    "category": "Food & Dining",
    "date": "2026-08-14"
  },
  "message": "Receipt parsed successfully"
}
}
``````
