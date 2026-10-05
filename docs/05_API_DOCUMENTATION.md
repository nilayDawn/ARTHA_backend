# 📡 05. REST API Specification & Endpoint Contracts

<p align="center">
  <img src="https://img.shields.io/badge/OpenAPI-3.1.0-green?style=for-the-badge&logo=openapi-initiative" alt="OpenAPI" />
  <img src="https://img.shields.io/badge/FastAPI-Async%20REST-009688?style=for-the-badge&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Auth-Supabase%20JWT%20Bearer-3ECF8E?style=for-the-badge&logo=supabase" alt="Supabase Auth" />
  <img src="https://img.shields.io/badge/Billing-Stripe%20Checkout-635BFF?style=for-the-badge&logo=stripe" alt="Stripe" />
</p>

---

## 🔐 Authentication & Request Headers

### 1. Supabase Bearer Authentication
All protected routes require an active JWT session token issued by Supabase Auth:
```http
Authorization: Bearer <SUPABASE_ACCESS_TOKEN>
```

### 2. Custom User LLM API Key (Per-Request Override)
Users can provide their own Google Gemini API key. When present, the server routes all LLM queries, vision OCR tasks, and embedding calculations to the user's isolated quota:
```http
X-User-LLM-Key: AIzaSy...
```

### 3. Rate Limiting Response Headers
Every endpoint is protected by an in-memory or Redis-backed sliding-window rate limiter:
```http
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 19
X-RateLimit-Reset: 1712000060
```
*When rate limits are exceeded, the API returns `HTTP 429 Too Many Requests` with a JSON payload: `{"detail": "Rate limit exceeded. Try again in 45s."}`.*

---

## 🛡️ Input Validation & Safety Bounds

All incoming request bodies are strictly bound by Pydantic v2 schemas:
- **Financial Amounts**: Must be strictly positive numbers (`gt=0`, `le=1,000,000,000`).
- **Dates**: Must conform to ISO-8601 format (`YYYY-MM-DD`).
- **Text Descriptions & Notes**: Bounded between `1` and `500` characters to prevent payload injection and buffer bloating.
- **File Uploads**: Enforced at **15 MB streaming cap** with strict MIME type allowlisting (`image/jpeg`, `image/png`, `image/webp`, `application/pdf`).

---

## 📌 Complete Endpoint Matrix

| Domain | Method | Endpoint | Description | Rate Limit | Cache / Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Auth** | `POST` | `/api/v1/auth/signup` | Register user account | 10 / min | Creates Supabase auth record |
| **Auth** | `POST` | `/api/v1/auth/login` | Authenticate & retrieve JWT | 15 / min | Issues access/refresh tokens |
| **Auth** | `GET` | `/api/v1/auth/me` | Fetch active user profile | 60 / min | 300s TTL Cache |
| **Finance** | `GET` | `/api/v1/transactions` | Query recent transactions | 60 / min | 180s TTL Cache |
| **Finance** | `POST` | `/api/v1/transactions` | Create income/expense log | 30 / min | Invalidation Trigger |
| **Finance** | `GET` | `/api/v1/transactions/summary`| Aggregated monthly KPI metrics | 60 / min | 180s TTL Cache |
| **Finance** | `GET` | `/api/v1/budgets` | Fetch monthly category budgets | 60 / min | 180s TTL Cache |
| **Finance** | `POST` | `/api/v1/budgets` | Set or update monthly budget | 30 / min | Invalidation Trigger |
| **Finance** | `GET` | `/api/v1/goals` | Fetch active savings targets | 60 / min | 180s TTL Cache |
| **Finance** | `POST` | `/api/v1/goals` | Create a new savings target | 30 / min | Invalidation Trigger |
| **Agent** | `POST` | `/api/v1/chat` | Conversational financial agent | 20 / min | LangGraph state machine |
| **Agent** | `POST` | `/api/v1/chat/validate-key`| Test user Gemini key validity | 10 / min | Live model connection ping |
| **OCR** | `POST` | `/api/v1/documents/upload`| Receipt & statement OCR parse | 10 / min | Gemini 2.5/3.6 Vision |
| **Telegram**| `POST` | `/api/v1/telegram/link-code`| Generate 10-min `FP-XXXX` token| 5 / min | Ephemeral single-use code |
| **Telegram**| `POST` | `/api/v1/telegram/webhook` | Telegram Bot update handler | 120 / min | Immediate typing feedback |
| **Payments**| `POST` | `/api/v1/payments/checkout` | Create Stripe checkout session | 15 / min | Stripe Hosted Checkout URL |
| **Payments**| `GET` | `/api/v1/payments/subscription`| Check active subscription tier | 60 / min | Mock / Live Stripe Status |
| **Payments**| `POST` | `/api/v1/payments/webhook` | Stripe async billing webhook | 120 / min | Cryptographic signature verified |
| **Catalogue**|`GET` | `/api/v1/catalogue/categories` | Standard categories catalog | 60 / min | Static cached registry |
| **Catalogue**|`GET` | `/api/v1/catalogue/merchants` | Auto-categorization keyword map| 60 / min | Static cached registry |
| **Catalogue**|`GET` | `/api/v1/catalogue/budget-templates`| 50/30/20 & Zero-Based templates| 60 / min | Static cached registry |
| **Reports** | `POST` | `/api/v1/reports/send-email`| Send HTML monthly digest email | 5 / min | Resend transactional email |

---

## 📝 Request & Response Contracts

### 1. AI Chat Agent (`POST /api/v1/chat`)

**Headers:**
```http
Authorization: Bearer <JWT_TOKEN>
X-User-LLM-Key: <OPTIONAL_GEMINI_KEY>
Content-Type: application/json
```

**Request Body:**
```json
{
  "message": "Logged 450 for grocery shopping at Zepto today",
  "history": [
    {"role": "user", "content": "Hi ARTHA"},
    {"role": "assistant", "content": "Hello! How can I assist with your finances today?"}
  ]
}
```

**Response Body (`200 OK`):**
```json
{
  "response": "I've recorded your expense of ₹450 under Groceries for today! Your remaining monthly grocery budget is ₹4,550.",
  "memories_used": [
    "User prefers shopping at Zepto for quick pantry items"
  ],
  "user_preferences": [
    "grocery shopping at Zepto"
  ]
}
```

---

### 2. Stripe Checkout Session (`POST /api/v1/payments/checkout`)

**Request Body:**
```json
{
  "plan_id": "pro_monthly",
  "success_url": "https://artha.app/settings?session_id={CHECKOUT_SESSION_ID}",
  "cancel_url": "https://artha.app/settings?cancelled=true"
}
```

**Response Body (`200 OK`):**
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_live_a1b2c3d4...",
  "session_id": "cs_live_a1b2c3d4e5f6g7h8"
}
```

---

### 3. Document OCR Upload (`POST /api/v1/documents/upload`)

**Content-Type:** `multipart/form-data`  
**Max File Size:** `15 MB` (Streaming chunk evaluation)  
**Accepted MIME Types:** `image/jpeg`, `image/png`, `image/webp`, `application/pdf`

**Response Body (`200 OK`):**
```json
{
  "extracted": {
    "merchant": "STARBUCKS COFFEE",
    "amount": 340.0,
    "category": "Food & Dining",
    "date": "2026-04-12"
  },
  "message": "Receipt parsed successfully"
}
```

---

### 4. Catalogue Categories & Budget Templates (`GET /api/v1/catalogue/budget-templates`)

**Response Body (`200 OK`):**
```json
[
  {
    "id": "50_30_20",
    "name": "50/30/20 Rule",
    "description": "50% Needs, 30% Wants, 20% Savings & Debt Repayment",
    "allocations": {
      "Needs": 0.50,
      "Wants": 0.30,
      "Savings": 0.20
    }
  },
  {
    "id": "zero_based",
    "name": "Zero-Based Budget",
    "description": "Allocate every single rupee of income to expenses or savings",
    "allocations": {
      "Fixed Expenses": 0.40,
      "Variable Living": 0.30,
      "Emergency Fund": 0.15,
      "Investments": 0.15
    }
  }
]
```

---

### 5. Telegram Link Code Generation (`POST /api/v1/telegram/link-code`)

**Response Body (`200 OK`):**
```json
{
  "code": "FP-8492",
  "expires_in_seconds": 600,
  "instructions": "Open @ArthaFinanceBot on Telegram and type: /link FP-8492"
}
```

---

## 🚦 Error Handling & Status Codes

All errors adhere to standard RFC-7807 problem details:

| Status Code | Description | Meaning |
| :--- | :--- | :--- |
| `400 Bad Request` | Validation Error | Request body bounds violated or unverified signature |
| `401 Unauthorized` | Missing / Invalid Token | Missing Bearer token or invalid Supabase session |
| `403 Forbidden` | Access Denied | Inactive subscription or forbidden resource |
| `413 Payload Too Large` | Size Limit Exceeded | File exceeds 15 MB streaming upload cap |
| `415 Unsupported Media` | Invalid MIME Type | Uploaded file is not JPEG, PNG, WEBP, or PDF |
| `429 Too Many Requests` | Rate Limited | Sliding window request quota exhausted |
| `500 Server Error` | Internal Failure | Adapter exception with automated diagnostic logging |
