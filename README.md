# FinPilot AI — Backend

Welcome to the **FinPilot AI** backend, the internal engine of a personal finance management platform. This document is a careful, detailed record of **all work completed so far**, including the architecture, every implemented file, every API endpoint, the schemas, and the current build status against the master plan.

---

## 🎯 Project Overview

**FinPilot AI** is a personal finance agent that combines:
- A **FastAPI backend** (this repo) that talks to **Supabase** (Postgres + Auth + Storage).
- A **frontend dashboard** (React + Vite) — planned but not yet implemented (see [Status](#status)).
- A future **AI brain** (LangGraph + Gemini) and **Telegram integration** — not started.

The goal is to let users track transactions, budgets, and savings goals, upload receipts/statements, and eventually chat with an AI about their finances.

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

> Note: The `models/`, `services/`, and `utils/` packages are currently empty (only `__init__.py` placeholders). No ORM models are used — all database access is done via the Supabase client directly.

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
    ├── main.py             # FastAPI app entrypoint
    ├── api/
    │   └── v1/
    │       ├── router.py   # Aggregates all sub-routers
    │       ├── auth.py     # /auth endpoints
    │       ├── finance.py  # /transactions, /budgets, /goals
    │       └── documents.py# /documents endpoints
    ├── core/
    │   ├── config.py       # Pydantic settings from env
    │   ├── database.py     # Supabase clients (public + admin)
    │   └── security.py     # JWT bearer auth dependency
    ├── models/             # (empty placeholder)
    ├── schemas/
    │   ├── auth.py         # Auth request/response models
    │   ├── finance.py      # Transaction/Budget/Goal models
    │   └── document.py     # Document response model
    ├── services/           # (empty placeholder)
    └── utils/              # (empty placeholder)
```

---

## 🏗 Architecture Details

### 1. Application Entrypoint — `app/main.py`

```python
app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(api_router, prefix=settings.API_V1_STR)
```

- Creates the FastAPI app titled **"FinPilot AI"**.
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

All nullable (`str | None`) so the app boots even before `.env` is fully populated.

### 3. Database Clients — `app/core/database.py`

Creates **two** Supabase clients with extended timeouts (60s for PostgREST and Storage) to handle large file uploads:

- **`supabase`** (public/anonymous client using `SUPABASE_ANON_KEY`) — used for auth operations.
- **`supabase_admin`** (service-role client using `SUPABASE_SERVICE_ROLE_KEY`) — used for admin operations that bypass Row Level Security (RLS), e.g. reading/writing transactional data.

### 4. Security / Auth Dependency — `app/core/security.py`

- Uses FastAPI's `HTTPBearer` security scheme.
- `get_current_user(credentials)` is a reusable dependency that:
  1. Reads the JWT from the `Authorization: Bearer <token>` header.
  2. Calls `supabase.auth.get_user(token)` to verify the token against Supabase Auth.
  3. Returns a dict `{id, email, user_metadata}` for the authenticated user.
  4. Raises `401` on invalid/expired tokens or any validation failure.

Every protected endpoint below depends on this function via `current_user: dict = Depends(get_current_user)`.

---

## 🔌 API Endpoints (Implemented)

All routes are aggregated in `app/api/v1/router.py`:

```python
api_router.include_router(auth_router)        # /auth/*
api_router.include_router(finance_router)     # /transactions, /budgets, /goals
api_router.include_router(documents_router)   # /documents/*
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
| `POST` | `/documents/upload` | Upload a file (receipt/statement) to Supabase Storage + record metadata. (201) |
| `GET` | `/documents` | List the user's documents with transient signed URLs. |
| `DELETE` | `/documents/{document_id}` | Delete a document from Storage + DB. |

**Upload flow (`upload_document`):**
1. Reads the raw file bytes.
2. Derives the file extension from the filename.
3. Builds a unique storage path: `{user_id}/{uuid4()}.{extension}`.
4. Uploads to Supabase Storage bucket (`BUCKET_NAME`) using `supabase_admin` with the file's content type.
5. Inserts a row into the `documents` table (`user_id`, `file_url`, `document_type`).
6. Generates a **1-hour signed URL** for secure access and attaches it as `signed_url`.

**List flow (`get_user_documents`):**
- Queries `documents` for the user (newest first by `uploaded_date`).
- For each document, generates a fresh **1-hour signed URL** using `supabase_admin.storage`. Handles both dict and object return shapes from the SDK.

**Delete flow (`delete_document`):**
- Verifies the document belongs to the current user (ownership check).
- Removes the file from Storage (`storage.remove([file_url])`).
- Deletes the row from the `documents` table.

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
- `DocumentResponse` — `id`, `user_id`, `file_url`, optional `signed_url`, `document_type`, `uploaded_date`.

---

## 📦 Supabase Setup (Assumed/Required)

The backend assumes the following Supabase project state (per the master TODO plan):

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

> ⚠️ The `.env` file (with `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `BUCKET_NAME`) is git-ignored and not committed.

---

## ⚙️ Configuration Files

### `requirements.txt`
```text
fastapi>=0.110.0
uvicorn[standard]>=0.28.0
supabase>=2.3.0
pydantic>=2.6.0
pydantic-settings>=2.2.0
python-dotenv>=1.0.1
python-multipart>=0.0.9
httpx>=0.27.0
pydantic[email]
```

### `pyproject.toml`
- `name = "backend"`, `version = "0.1.0"`, `requires-python = ">=3.12"`.
- `dependencies = []` (dependencies live in `requirements.txt` for now).

### `.gitignore`
- Ignores Python artifacts (`__pycache__`, `*.pyc`, `build/`, `dist/`, `*.egg-info`), virtualenvs (`.venv`), `.env`, and `agent.md`.

### `.python-version`
- Pins Python to `3.12`.

---

## 📊 Status

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Foundation (Supabase DB + Auth + RLS + Storage) | ✅ Assumed set up (schema referenced by code) |
| **Phase 2** | Backend Core API (FastAPI) — auth, transactions, budgets, goals, documents | ✅ **Implemented** |
| **Phase 3** | Frontend Core (React + Vite) | ⏳ Only `frontend/agent.md` guidelines exist — **no code yet** |
| **Phase 4** | AI Brain (LangGraph + Gemini + Qdrant) | ❌ Not started |
| **Phase 5** | Frontend AI Features (chat UI, uploads) | ❌ Not started |
| **Phase 6** | Telegram Integration | ❌ Not started |
| **Phase 7** | Deployment & Polish | ❌ Not started |

### What is Fully Done
- ✅ FastAPI project scaffold with clean, layered structure (`core`, `api/v1`, `schemas`).
- ✅ Environment-based configuration via Pydantic Settings.
- ✅ Dual Supabase clients (public + admin) with extended timeouts.
- ✅ JWT bearer auth dependency (`get_current_user`).
- ✅ Complete **Auth** API (`signup`, `login`, `me`, `logout`).
- ✅ Complete **Finance** API (`transactions`, `budgets`, `goals` — create + list).
- ✅ Complete **Documents** API (`upload`, `list`, `delete` with signed URLs).
- ✅ All Pydantic request/response schemas.
- ✅ Frontend development guidelines documented in `frontend/agent.md`.
- ✅ Master build plan in `docs/TODO.md`.

### What is NOT Done Yet
- ❌ Actual frontend React/Vite application (auth pages, dashboard, charts, chat UI).
- ❌ AI brain: LangGraph agent workflow (Router/DB Tool/Memory Tool nodes).
- ❌ Gemini 2.5 Flash vision pipeline for receipt/statement extraction.
- ❌ Qdrant vector DB integration for user memory.
- ❌ `/api/v1/chat` endpoint.
- ❌ Telegram bot webhook (`/api/telegram/webhook`) and account linking (`/link FP-XXXX`).
- ❌ Deployment (Render for backend, Vercel for frontend) and cold-start mitigation via CronJob.org.

---

## 🚀 How to Run (Backend)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# create a .env with SUPABASE_URL, SUPABASE_ANON_KEY,
# SUPABASE_SERVICE_ROLE_KEY, SUPABASE_PASSWORD, BUCKET_NAME
uvicorn app.main:app --reload
```

The interactive API docs will be available at `http://localhost:8000/docs` (Swagger UI).
