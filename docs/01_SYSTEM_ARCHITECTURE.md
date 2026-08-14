# 🏛️ 01. System Architecture & High-Level Blueprint

> **ARTHA AI — Enterprise Financial Backend Architecture**  
> *A comprehensive technical breakdown of the asynchronous FastAPI backend, stateful LangGraph agent, vector database memory tier, cryptographic token security, and caching engine.*

---

## 📌 1. System Overview

**ARTHA AI** is an intelligent personal finance platform built for high-throughput, sub-second latency financial analysis, automated OCR receipt parsing, conversational AI reasoning, and multi-channel notification dispatches (Telegram Webhooks & Resend HTML Emails).

Rather than operating as a simple LLM wrapper, ARTHA AI uses a decoupled **microservices-ready architecture**:

```
+-----------------------------------------------------------------------------------+
|                                 CLIENT SURFACES                                   |
|       (React 19 Dashboard Web App / Telegram Bot Webhook / REST Clients)         |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                                 FASTAPI API GATEWAY                               |
|              (Uvicorn ASGI Server / CORS Middleware / JWT Bearer Auth)            |
+------------------------------------------+----------------------------------------+
                                           |
                   +-----------------------+-----------------------+
                   |                       |                       |
                   v                       v                       v
        +----------+----------+ +----------+----------+ +----------+----------+
        |   LangGraph Agent   | |  Centralized Cache  | | Supabase Postgres DB|
        | (Gemini 3.6 Flash)  | |  (In-Memory TTL)    | | (Auth, DB, Storage) |
        +----------+----------+ +---------------------+ +---------------------+
                   |
                   v
        +----------+----------+
        | Qdrant Vector Memory|
        | (gemini-embedding)  |
        +---------------------+
```

---

## 🛠 2. Component Specifications

### 2.1 Web Framework & Routing (`FastAPI`)
- **Asynchronous Execution**: Powered by `FastAPI` and `uvicorn`, handling non-blocking REST requests.
- **Security Middleware**: CORS security layer allowing cross-origin requests from authenticated React frontends.
- **Data Validation**: Strict Pydantic v2 schemas (`app/schemas/`) enforcing strong typing for input payloads and API response contracts.

### 2.2 Relational Persistence & Authentication (`Supabase`)
- **Auth Engine**: Managed Supabase Auth with JWT Bearer tokens. Client requests supply `Authorization: Bearer <JWT>`, which is validated asynchronously by `app/core/security.py`.
- **Database Tables**:
  - `users`: User profiles, email, `telegram_chat_id`, Fernet-encrypted Telegram link tokens, and expiration timestamps.
  - `transactions`: Categorized ledger entries (amount, category, merchant, date, type).
  - `budgets`: Category-based monthly spending limits.
  - `goals`: Target savings goals with progress tracking.

### 2.3 Conversational AI Engine (`LangGraph` + `Gemini 3.6 Flash`)
- **Graph State Machine**: A 3-node state graph orchestrating input evaluation, database context assembly, long-term memory recall, response generation, and selective memory persistence.
- **Fallback Resilience**: Multi-key fallback pipeline (`GEMINI_API_KEY_1..3`) to ensure high availability across rate limits.

### 2.4 Vector Memory Tier (`Qdrant` + `gemini-embedding-001`)
- **Semantic Storage**: Stores long-term user habits, preferences, and financial rules.
- **Schema**: 3072-dimensional vector collection (`user_memories`) indexed with Cosine Similarity and payload metadata filtering scoped by `user_id`.

---

## 📊 3. End-to-End Request Lifecycle

```
[User Chat Request] ──▶ [JWT Bearer Auth Validation]
                               │
                               ▼
                   [Security Guardrail Node]
                               │
                   ├── (If Blocked) ──▶ [Return Refusal Response]
                   │
                   └── (If Allowed) ──▶ [Fetch DB Context (TTL Cached)]
                                               │
                                               ▼
                                    [Recall Qdrant Memory]
                                               │
                                               ▼
                                  [Gemini 3.6 Flash Inference]
                                               │
                                               ▼
                                 [Structured Action Execution]
                                               │
                                               ▼
                               [Selective Qdrant Persistence]
```

---

*Continue reading:*
- [02. Token & Cache Optimization](02_TOKEN_AND_CACHE_OPTIMIZATION.md)
- [03. Security & Guardrails](03_SECURITY_AND_GUARDRAILS.md)
- [04. Agent Workflow & Memory](04_AGENT_WORKFLOW_AND_MEMORY.md)
- [05. API Specification](05_API_DOCUMENTATION.md)
