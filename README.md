# FinPilot AI — Backend

Welcome to the **FinPilot AI** backend, the internal engine of a personal finance management platform. This document is a careful, detailed record of **all work completed so far**, including the architecture, every implemented file, every API endpoint, the schemas, and the current build status against the master plan.

---

## 🎯 Project Overview

**FinPilot AI** is a personal finance agent that combines:
- A **FastAPI backend** (this repo) that talks to **Supabase** (Postgres + Auth + Storage).
- A **frontend dashboard** (React + Vite) — see `frontend/`.
- An **AI brain** (LangGraph + Gemini 2.5 Flash + Qdrant vector memory) — implemented.
- A **Telegram integration** — planned for a future phase.

The goal is to let users track transactions, budgets, and savings goals, upload receipts/statements, and chat with an AI about their finances.

---

## 🛠 Tech Stack (Current)

| Layer | Technology |
|-------|------------|
| Language | Python `>=3.12` (`.python-version` = `3.12`) |
| Web Framework | FastAPI (`fastapi>=0.110.0`) |
| ASGI Server | uvicorn (`uvicorn[standard]>=0.28.0`) |
| Database / Auth / Storage | Supabase (`supabase>=2.3.0`) |
| Validation | Pydantic v2 (`pydantic>=2.6.0`, `pydantic-settings>=2.2.0`) |
| Env Management | `python-dotenv>=1.0.1` |
| File Uploads | `python-multipart>=0.0.9` |
| HTTP Client | `httpx>=0.27.0` |
| Email Validation | `pydantic[email]` |
| AI Agent Orchestration | LangGraph (`langgraph>=0.0.26`) + LangChain (`langchain-core>=0.1.30`) |
| LLM / Vision / Embeddings | Google GenAI (`google-genai>=0.1.1`) — Gemini 2.5 Flash + text-embedding-004 |
| Vector Memory | Qdrant (`qdrant-client>=1.8.0`) |

> Note: The `models/` and `utils/` packages are currently empty (only `__init__.py` placeholders). No ORM models are used — all database access is done via the Supabase client directly.

---

## 📁 Project Structure

```text
backend/
├── .gitignore              # Python, venv, .env, agent.md exclusions
├── .python-version         # 3.12
├── pyproject.toml          # Project metadata
├── requirements.txt        # Runtime dependencies
├── README.md               # This file
└── app/
    ├── main.py             # FastAPI app entrypoint (CORS + Qdrant init on startup)
    ├── api/
    │   └── v1/
    │       ├── router.py   # Aggregates all sub-routers
    │       ├── auth.py     # /auth endpoints
    │       ├── finance.py  # /transactions, /budgets, /goals
    │       ├── documents.py# /documents endpoints (upload w/ OCR)
    │       └── chat.py     # /chat endpoint (AI agent)
    ├── agent/
    │   ├── graph.py        # LangGraph workflow (3-node financial agent)
    │   ├── state.py        # AgentState TypedDict
    │   └── tools.py        # DB context + memory retrieval tools
    ├── core/
    │   ├── config.py       # Pydantic settings from env
    │   ├── database.py     # Supabase clients (public + admin)
    │   ├── security.py     # JWT bearer auth dependency
    │   └── vector_db.py    # Qdrant client init
    ├── models/             # (empty placeholder)
    ├── schemas/
    │   ├── auth.py         # Auth request/response models
    │   ├── finance.py      # Transaction/Budget/Goal models
    │   ├── document.py     # Document + Gemini extraction models
    │   └── chat.py         # Chat request/response models
    ├── services/
    │   ├── memory.py       # Qdrant memory save/search (embeddings)
    │   └── ocr.py          # Gemini 2.5 Flash Vision receipt extraction
    └── utils/              # (empty placeholder)
```

---

## 🏗 Architecture Details

### 1. Application Entrypoint — `app/main.py`

```python
app = FastAPI(title=settings.PROJECT_NAME)
# CORS enabled for frontend development
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
# initialize Qdrant collection on startup
@app.on_event("startup")
def startup_event():
    init_memory_collection()
app.include_router(api_router, prefix=settings.API_V1_STR)
```

- Creates the FastAPI app titled **"FinPilot AI"**.
- Enables CORS for the frontend dev server (all origins, all methods/headers).
- Initializes the Qdrant `user_memories` collection on startup.
- Mounts the aggregated `api_router` under the `/api/v1` prefix.
- **Root endpoint** `GET /` → returns `{"status": "online", "message": "FinPilot AI Backend API is running"}`.
- **Health check** `GET /health` → returns `{"status": "healthy"}` (also planned for use by CronJob.org to combat cold starts).

### 2. Configuration — `app/core/config.py`

Uses `pydantic-settings` `BaseSettings` to load environment variables from a `.env` file:

| Variable | Purpose |
|----------|---------|
| `PROJECT_NAME` | `"FinPilot AI"` (default) |
| `API_V1_STR` | `"/api/v1"` (default) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_PASSWORD` | Database password |
| `SUPABASE_ANON_KEY` | Public (anon) API key — used for user-scoped auth operations |
| `SUPABASE_SERVICE_ROLE_KEY` | Admin/service-role key — bypasses RLS for admin operations |
| `BUCKET_NAME` | Supabase Storage bucket for documents |
| `GEMINI_API_KEY` | Google AI Studio key — used for Gemini 2.5 Flash (LLM + Vision) and embeddings |
| `QDRANT_URL` | Qdrant cloud/self-hosted URL for vector memory |
| `QDRANT_API_KEY` | Qdrant API key |

All nullable (`str | None`) so the app boots even before `.env` is fully populated.

### 3. Database Clients — `app/core/database.py`

Creates **two** Supabase clients with extended timeouts (60s for PostgREST and Storage) to handle large file uploads:

- **`supabase`** (public/anonymous client using `SUPABASE_ANON_KEY`) — used for auth operations.
- **`supabase_admin`** (service-role client using `SUPABASE_SERVICE_ROLE_KEY`) — used for admin operations that bypass Row Level Security (RLS), e.g. reading/writing transactional data.

### 4. Vector DB Client — `app/core/vector_db.py`

- Instantiates a global `qdrant_client` from `QDRANT_URL` + `QDRANT_API_KEY`.
- If either setting is missing, `qdrant_client` stays `None` and vector features are gracefully skipped (services log warnings and return empty results).

### 5. Security / Auth Dependency — `app/core/security.py`

- Uses FastAPI's `HTTPBearer` security scheme.
- `get_current_user(credentials)` is a reusable dependency that:
  1. Reads the JWT from the `Authorization: Bearer <token>` header.
  2. Calls `supabase.auth.get_user(token)` to verify the token against Supabase Auth.
  3. Returns a dict `{id, email, user_metadata}` for the authenticated user.
  4. Raises `401` on invalid/expired tokens or any validation failure.

Every protected endpoint below depends on this function via `current_user: dict = Depends(get_current_user)`.

### 6. AI Agent Workflow — `app/agent/graph.py`

Builds a **LangGraph** state machine `financial_agent` with three sequential nodes:

```text
fetch_db_context ──▶ recall_memories ──▶ llm_reasoning ──▶ END
```

- **`fetch_db_context`** — calls `fetch_user_financial_context(user_id)` (from `tools.py`) to pull the user's recent 20 transactions, budgets, and goals from Supabase into `db_context`.
- **`recall_memories`** — extracts the last `HumanMessage`, then calls `fetch_relevant_memories(user_id, query)` to retrieve up to 5 matching long-term memories/preferences from Qdrant.
- **`llm_reasoning`** — builds a system prompt (with user ID, financial context, and memories) and calls Gemini 2.5 Flash (`gemini-2.5-flash`) to generate a grounded, conversational financial answer. Returns an `AIMessage` appended to the message state.

The shared state is defined in `app/agent/state.py` (`AgentState`):
- `messages` — LangChain message list (with `add_messages` reducer for history).
- `user_id` — the authenticated user.
- `memories` — retrieved Qdrant memories.
- `db_context` — financial rows from Supabase.

#### Agent Tools — `app/agent/tools.py`
- `fetch_user_financial_context(user_id)` → dict of `recent_transactions`, `budgets`, `goals` (with graceful error handling returning empty lists).
- `fetch_relevant_memories(user_id, query)` → wraps `search_user_memories` (limit 5).
- `remember_user_preference(user_id, memory_text, category="preference")` → wraps `save_user_memory` (available for future persistence of acknowledged preferences).

### 7. Memory Service — `app/services/memory.py`

Handles all Qdrant vector memory operations:

- **Collection:** `user_memories`, vector size `768` (dimensionality of `text-embedding-004`), cosine distance.
- **`init_memory_collection()`** — creates the collection if it doesn't exist (also called on app startup).
- **`_get_embedding(text)`** — generates a 768-dim vector via Gemini `text-embedding-004`.
- **`save_user_memory(user_id, memory_text, category)`** — embeds text and upserts a point with payload `{user_id, memory, category}`.
- **`search_user_memories(user_id, query, limit=5)`** — embeds the query, then searches Qdrant filtered strictly by `user_id`, returning the top matching memory strings.

### 8. OCR / Vision Service — `app/services/ocr.py`

- **`process_receipt_with_gemini(image_bytes, mime_type)`** — sends raw image bytes to Gemini 2.5 Flash with **structured JSON output** (schema = `ExtractedTransaction`), temperature `0.1`, to extract `merchant`, `amount`, `category`, `date`, and optional `description`.
- Returns an `ExtractedTransaction` instance or `None` if no API key / extraction fails.

---

## 🔌 API Endpoints (Implemented)

All routes are aggregated in `app/api/v1/router.py`:

```python
api_router.include_router(auth_router)        # /auth/*
api_router.include_router(finance_router)     # /transactions, /budgets, /goals
api_router.include_router(documents_router)   # /documents/*
api_router.include_router(chat_router)        # /chat
```

### A. Authentication — `app/api/v1/auth.py` (prefix `/auth`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/signup` | Register a new user (Email + Password). Returns an access token. (201) |
| `POST` | `/auth/login` | Log in with Email + Password. Returns an access token. |
| `GET` | `/auth/me` | Fetch the authenticated user's profile from `public.users`. |
| `POST` | `/auth/logout` | Sign out the current user. |

**Details:**
- **Signup** passes `full_name` into the user metadata. Relies on a Postgres trigger `on_auth_user_created` to create the matching row in `public.users`. Returns a 400 if no session (e.g., when email confirmation is required).
- **Login** uses `sign_in_with_password`. Returns `AuthTokenResponse` with `access_token`, `user_id`, `email`.
- **Me** queries `public.users` filtered by the authenticated user's `id`.
- **Logout** calls `supabase.auth.sign_out()`.

### B. Finance — `app/api/v1/finance.py` (no prefix)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/transactions` | Create a transaction. (201) |
| `GET` | `/transactions` | List the user's transactions (newest first by `date`). |
| `POST` | `/budgets` | Create a budget. (201) |
| `GET` | `/budgets` | List the user's budgets. |
| `POST` | `/goals` | Create a financial goal. (201) |
| `GET` | `/goals` | List the user's goals. |

All finance endpoints use `supabase_admin` (service-role) but scope queries by `current_user["id"]` → `user_id` to enforce per-user data separation in the application layer.

**Details:**
- **Transactions** — `date` is serialized to ISO format string before insert. Sorted by `date` descending.
- **Budgets** — handles a unique constraint on `(user_id, category, month)`; a violation produces a meaningful error message.
- **Goals** — `deadline` (if present) is serialized to ISO format. `saved_amount` defaults to `0.0`.

### C. Documents — `app/api/v1/documents.py` (prefix `/documents`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/documents/upload` | Upload a file (receipt/statement) to Supabase Storage, run Gemini OCR, and auto-create a transaction. (201) |
| `GET` | `/documents` | List the user's documents with transient signed URLs. |
| `DELETE` | `/documents/{document_id}` | Delete a document from Storage + DB. |

**Upload flow (`upload_document`):**
1. Reads the raw file bytes.
2. Derives the file extension from the filename.
3. Builds a unique storage path: `{user_id}/{uuid4()}.{extension}`.
4. Uploads to Supabase Storage bucket (`BUCKET_NAME`) using `supabase_admin` with the file's content type.
5. Inserts a row into the `documents` table (`user_id`, `file_url`, `document_type`). `document_type` is `"receipt"` for supported image types (`image/jpeg`, `image/png`, `image/webp`, `image/heic`), otherwise `"statement"`.
6. Generates a **1-hour signed URL** for secure access and attaches it.
7. **AI Vision OCR:** if the file is a supported image type, calls `process_receipt_with_gemini` to extract transaction data. If extraction succeeds, an entry is **auto-inserted into the `transactions` table** with `source="ocr_upload"`.
8. Returns a `DocumentUploadResponse` containing `document_id`, `file_url`, `signed_url`, optional `extracted_data`, and a message.

**List flow (`get_user_documents`):**
- Queries `documents` for the user (newest first by `uploaded_date`).
- For each document, generates a fresh **1-hour signed URL** using `supabase_admin.storage`. Handles both dict and object return shapes from the SDK.

**Delete flow (`delete_document`):**
- Verifies the document belongs to the current user (ownership check).
- Removes the file from Storage (`storage.remove([file_url])`).
- Deletes the row from the `documents` table.

### D. Chat & AI — `app/api/v1/chat.py` (prefix `/chat`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Run a conversational query through the LangGraph financial agent. |

**Flow (`chat_with_agent`):**
1. Takes a `ChatRequest` (`message` + optional `history`).
2. Reconstructs the LangChain message list from `history` (`user` → `HumanMessage`, `assistant` → `AIMessage`), then appends the current query as a `HumanMessage`.
3. Builds the agent's `initial_state` with `messages`, the authenticated `user_id`, empty `memories`, and empty `db_context`.
4. Invokes `financial_agent.invoke(initial_state)` (runs DB context → memory recall → Gemini reasoning).
5. Extracts the final `AIMessage` content as the response.
6. Returns `ChatResponse` with `response` text and `memories_used` (the Qdrant memories that grounded the answer).
7. On error, returns `500` with a descriptive message.

---

## 📄 Schemas (Pydantic Models)

### `app/schemas/auth.py`
- `UserSignUp` — `email` (EmailStr), `password`, optional `full_name`.
- `UserSignIn` — `email`, `password`.
- `AuthTokenResponse` — `access_token`, `token_type="bearer"`, `user_id`, `email`.
- `UserProfileResponse` — `id`, `email`, optional `full_name`, optional `telegram_chat_id`, `created_at`.

### `app/schemas/finance.py`
- **Transaction:** `TransactionCreate` (`amount`, optional `merchant="Unknown"`, `category`, `date`, optional `source="manual"`); `TransactionResponse` adds `id`, `user_id`, `created_at`.
- **Budget:** `BudgetCreate` (`category`, `monthly_limit`, `month` as `YYYY-MM`); `BudgetResponse` adds `id`, `user_id`, `created_at`.
- **Goal:** `GoalCreate` (`goal_name`, `target_amount`, optional `saved_amount=0.0`, optional `deadline`); `GoalResponse` adds `id`, `user_id`, `created_at`.

### `app/schemas/document.py`
- **`ExtractedTransaction`** — schema enforced on Gemini structured output: `merchant`, `amount` (float), `category` (Food/Groceries/Shopping/Transport/Bills/Entertainment/Healthcare/Education/Others), `date` (`YYYY-MM-DD`), optional `description`.
- **`DocumentUploadResponse`** — `document_id`, `file_url`, `signed_url`, optional `extracted_data` (`ExtractedTransaction`), `message`.
- **`DocumentResponse`** — `id`, `user_id`, `file_url`, optional `signed_url`, `document_type`, `uploaded_date`.

### `app/schemas/chat.py`
- **`ChatMessage`** — `role` (`"user"` or `"assistant"`), `content`.
- **`ChatRequest`** — `message`, optional `history` (list of `ChatMessage`, default `[]`).
- **`ChatResponse`** — `response`, `memories_used` (list of strings, default `[]`).

---

## 📦 Supabase & Qdrant Setup (Assumed/Required)

The backend assumes the following external service state (per the master TODO plan):

- **Auth:** Email/Password enabled.
- **Database schema (PostgreSQL):**
  - `users` (`id`, `email`, `name`, `created_at`, plus `telegram_chat_id` implied by the schema).
  - `transactions` (`id`, `user_id`, `amount`, `merchant`, `category`, `date`, `source`).
  - `budgets` (`id`, `user_id`, `category`, `limit`, `month`) — note the code uses `monthly_limit`; a unique constraint on `(user_id, category, month)` is referenced.
  - `goals` (`id`, `user_id`, `goal_name`, `target_amount`, `saved_amount`, `deadline`).
  - `documents` (`id`, `user_id`, `file_url`, `document_type`, `uploaded_date`).
- **Postgres trigger:** `on_auth_user_created` to auto-create `public.users` rows.
- **Storage bucket:** a private bucket named via `BUCKET_NAME` for receipt images and bank statements.
- **RLS:** policies so users can only access their own data (application layer also enforces `user_id` scoping via `supabase_admin`).

- **Qdrant:** a cloud/self-hosted instance with a `user_memories` collection (vector size `768`, cosine distance). The collection is auto-created on startup via `init_memory_collection()`.

> ⚠️ The `.env` file (with `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `BUCKET_NAME`, `GEMINI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`) is git-ignored and not committed.

---

## ⚙️ Configuration Files

### `requirements.txt`
```text
# dependencies
fastapi>=0.110.0
uvicorn[standard]>=0.28.0
