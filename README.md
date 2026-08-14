# 🏛️ ARTHA AI — Backend Architecture & API Specification

> **Enterprise-Grade AI Personal Finance Backend**  
> *Engineered with FastAPI, LangGraph, Supabase (Postgres + Auth + Storage), Qdrant Vector Memory, Gemini 3.6 Flash, and Telegram Bot Webhooks.*

---

## 🎯 System Overview

**ARTHA AI** is a state-of-the-art AI personal financial agent that provides real-time financial tracking, receipt/invoice OCR processing, long-term habit memory, and automated conversational intelligence.

### Core Capabilities:
- **FastAPI REST API**: High-performance asynchronous REST endpoints with JWT Bearer authentication.
- **LangGraph AI Reasoning Engine**: Powered by **Gemini 3.6 Flash** with structured action block parsing (`json_action`) for automated database mutations.
- **Vector Memory Storage**: **Qdrant** integration paired with `gemini-embedding-001` (3072-dim) for selective memory storage of user habits and rules.
- **Centralized TTL Caching**: Thread-safe in-memory caching engine (`app.core.cache`) with event-driven invalidation across all financial endpoints and AI context retrieval.
- **Stateless Telegram Bot Integration**: Encrypted, Fernet AES-persisted single-use account linking tokens (`FP-XXXX`) with webhook OCR receipt and voice scanning.
- **Email Report Delivery**: Async background summary report generation and delivery powered by **Resend**.

---

## 📚 Technical Documentation Index

For technical recruiters, software architects, and engineering reviewers, detailed technical blueprints are available inside the [`docs/`](docs/) directory:

- 📑 **[00. Architectural & Engineering Rationale](docs/ENGINEERING_DECISIONS.md)**: Executive summary of core architectural choices, latency optimizations, and production readiness.
- 🏛️ **[01. System Architecture & High-Level Blueprint](docs/01_SYSTEM_ARCHITECTURE.md)**: Asynchronous FastAPI gateway, Supabase database schemas, and component interactions.
- ⚡ **[02. Token & Cache Optimization Strategy](docs/02_TOKEN_AND_CACHE_OPTIMIZATION.md)**: High-density prompt serialization (80% cost cut) and in-memory TTL cache with event-driven invalidation.
- 🛡️ **[03. AI Security Guardrails & Token Cryptography](docs/03_SECURITY_AND_GUARDRAILS.md)**: Multi-layer guardrails against prompt injection and Fernet AES symmetric token encryption.
- 🧠 **[04. LangGraph Agent Workflow & Vector Memory](docs/04_AGENT_WORKFLOW_AND_MEMORY.md)**: State graph machine, Qdrant semantic vector memory, and structured action block engine.
- 📡 **[05. REST API Specification & Endpoint Reference](docs/05_API_DOCUMENTATION.md)**: Full OpenAPI contracts, request/response JSON schemas, and auth requirements.

---

## 🛠 Tech Stack

| Layer | Technology | Version / Notes |
| :--- | :--- | :--- |
| **Language** | Python | `>=3.12` |
| **Framework** | FastAPI | `>=0.110.0` |
| **Server** | Uvicorn | `>=0.28.0` |
| **Database & Auth** | Supabase | Postgres + JWT Auth + Storage |
| **Agent Orchestration** | LangGraph + LangChain | Multi-node state machine workflow |
| **LLM Core** | Gemini 3.6 Flash | Multi-key fallback (`GEMINI_API_KEY_1..3`) |
| **Embeddings** | `gemini-embedding-001` | 3072-dimensional vector schema |
| **Vector DB** | Qdrant | Semantic memory persistence |
| **Token Security** | Cryptography (Fernet AES) | SHA-256 derived keys |
| **Caching** | Custom In-Memory TTL Cache | Thread-safe with event-driven invalidation |

---

## 📁 Repository Structure

```text
backend/
├── .env                    # Environment secrets & model configuration
├── .gitignore              # Exclusions
├── pyproject.toml          # Metadata & dependencies
├── requirements.txt        # Runtime python packages
├── README.md               # Backend architecture & documentation
└── app/
    ├── main.py             # FastAPI app entrypoint & startup handlers
    ├── agent/              # LangGraph workflow engine
    │   ├── graph.py        # 3-node graph (Guardrail -> Agent -> Memory)
    │   ├── guardrail.py    # Gemini security guardrail classification
    │   ├── state.py        # AgentState TypedDict schema
    │   └── tools.py        # Token-optimized context formatter & DB mutation tools
    ├── api/v1/             # REST API routes
    │   ├── auth.py         # Sign-up, Sign-in, Profile with TTL caching
    │   ├── chat.py         # LangGraph AI chat endpoint
    │   ├── documents.py    # Document & receipt OCR processing
    │   ├── finance.py      # Transactions, Budgets, Goals with caching & invalidations
    │   ├── report.py       # Async HTML email report delivery via Resend
    │   ├── router.py       # API v1 aggregator
    │   └── telegram.py     # Telegram Webhook & Fernet-encrypted link codes
    ├── core/               # Infrastructure & configuration
    │   ├── cache.py        # Centralized TTL Caching Engine
    │   ├── config.py       # Pydantic settings & env validation
    │   ├── database.py     # Supabase public & admin client singletons
    │   ├── security.py     # JWT Bearer authentication dependency
    │   └── vector_db.py    # Qdrant client & collection initializer
    ├── schemas/            # Pydantic validation schemas
    └── services/           # Service layer
        ├── email.py        # HTML email summary generator (Resend)
        ├── memory.py       # Qdrant memory save & similarity search
        ├── ocr.py          # Gemini 3.6 Flash Vision OCR parser
        └── telegram_auth.py# Fernet AES token encryption & link code verification
```

---

## ⚡ Core Engineering Implementations

### 1. Centralized TTL Caching & Event-Driven Invalidation
To minimize database latency and prevent PostgREST connection strain, all backend read endpoints use centralized in-memory TTL caching (`app/core/cache.py`):
- `GET /auth/me`: 5-minute (`300s`) TTL cache (`user_profile:{user_id}`).
- `GET /finance/transactions`: 3-minute (`180s`) TTL cache.
- `GET /finance/budgets`: 3-minute (`180s`) TTL cache.
- `GET /finance/goals`: 3-minute (`180s`) TTL cache.
- `AI Context`: 3-minute (`180s`) TTL cache (`user_financial_context:{user_id}`).

**Event-Driven Cache Invalidation:** Any mutation operation (`create`, `update`, `delete` transaction, budget, or goal) calls `invalidate_user_caches(user_id)`, instantly clearing all cached entries for that user to ensure 100% data consistency.

### 2. Token Overhead Optimization (80% Reduction)
Instead of injecting full verbose JSON payloads (`{"created_at": "...", "id": "...", "user_id": "..."}`) into LLM system prompts, context is serialized into a high-density format:
```text
Tx: [₹500(Groceries/Supermarket,2026-08-14)] | Budgets: [Food:₹15000/mo] | Goals: [Laptop:₹10000/₹82000]
```
This reduces system prompt token overhead from **~1,200 tokens down to ~200 tokens** per interaction.

### 3. Selective Qdrant Vector Memory Storage
Rather than cluttering Qdrant vector storage with generic conversational messages, `memory_save_node` uses heuristic preference filtering (`PREFERENCE_KEYWORDS`). Memory persistence only triggers when a user explicitly expresses long-term financial rules, income details, or habits.

### 4. Stateful Telegram Token Security (Fernet AES)
Single-use link codes (`FP-XXXX`) are encrypted using Fernet symmetric AES encryption derived from standard app secret keys and stored in Supabase. Plaintext tokens are never stored on disk or in database columns.

---

## 🚀 Environment Setup & API Run

1. **Environment Variables (`.env`)**:
   ```env
   PROJECT_NAME="ARTHA AI"
   MODEL_NAME="gemini-3.6-flash"
   EMBEDDING_MODEL_NAME="gemini-embedding-001"
   GEMINI_API_KEY="your-gemini-key"
   SUPABASE_URL="https://your-project.supabase.co"
   SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
   QDRANT_URL="https://your-qdrant-cluster.qdrant.tech"
   QDRANT_API_KEY="your-qdrant-key"
   RESEND_API_KEY="re_123456789"
   ```

2. **Install & Run**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```

3. **Interactive API Docs**:
   Navigate to `http://localhost:8000/docs` for OpenAPI Swagger documentation.

---

*Authored by the ARTHA AI Engineering Team.*
