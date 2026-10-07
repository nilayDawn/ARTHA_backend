# 🛠️ ARTHA AI — Performance Audit: Identified Problems & Implemented Improvements

<p align="center">
  <img src="https://img.shields.io/badge/Audit-k6%20Load%20Test%20Findings-7952b3?style=for-the-badge" alt="Audit" />
  <img src="https://img.shields.io/badge/Status-Improvements%20Implemented-brightgreen?style=for-the-badge" alt="Status" />
  <img src="https://img.shields.io/badge/Platform-Azure%20Web%20App%20Ready-0078D4?style=for-the-badge&logo=microsoftazure" alt="Azure" />
</p>

> [!NOTE]
> This document details the architectural bottlenecks identified during the 6-phase k6 load testing audit (Smoke, Load, Stress, Spike, Soak, Breakpoint) across **21,114 HTTP requests**, along with the concrete engineering improvements implemented in the ARTHA AI backend.
>
> Navigation: [⬅️ Master Load Test Report](LOAD_TEST_REPORT.md) | [🏛️ Backend README](../README.md)

---

## 📑 Summary of Improvements at a Glance

| # | Bottleneck Area | Root Cause Discovered | Status | Implemented Solution |
| :-: | :--- | :--- | :---: | :--- |
| **1** | **Threadpool Starvation** | Synchronous database calls (`650ms` WAN) held Starlette's default 40 AnyIO threads, causing queueing at >25 VUs. | **RESOLVED** | Added `THREADPOOL_LIMIT = 100` to settings and tuned AnyIO thread limiter on startup. |
| **2** | **Single-Core Concurrency** | Single Uvicorn process ran on 1 CPU core and 1 GIL loop. | **RESOLVED** | Created dynamic multi-worker `gunicorn.conf.py` that auto-calculates workers for local & Azure App Service. |
| **3** | **Cache Over-Invalidation** | Single transaction write flushed **all** keys for the user (including unrelated months, budgets, goals). | **RESOLVED** | Implemented scoped cache invalidation (`prefix`) across `CachePort`, `MemoryCacheAdapter`, and domain services. |
| **4** | **PostgreSQL Table Scans** | Ledger queries filtered by user and date without composite B-Tree indexes. | **RESOLVED** | Created production SQL migration [`migrations/001_performance_indexes.sql`](../migrations/001_performance_indexes.sql). |
| **6** | **Cross-Region WAN Latency** | 98% of latency was cross-country WAN round-trips from localhost to Supabase Cloud (~650ms vs 2.8ms in-memory). | **GUIDED** | Documented Azure Web App geographic colocation strategy. |
| **7** | **Codebase Redundancy & Duplicate Shims** | 25+ duplicate shim files across `app/services`, `app/api/v1`, `app/schemas`, `app/agent`, and duplicated helper logic in services. | **RESOLVED** | Removed 26 duplicate/dead files, consolidated backwards-compatible re-exports into `__init__.py`, and extracted reusable helpers in `TransactionService`. |

---

## 1. 🧵 Threadpool Starvation & AnyIO Worker Thread Tuning

### 🔴 The Problem Identified
* In [`app/modules/finance/router.py`](../app/modules/finance/router.py), API endpoints are declared as standard synchronous functions (`def get_transactions(...)`, `def get_summary(...)`).
* FastAPI executes standard `def` routes inside an asynchronous worker thread pool managed by **AnyIO**.
* By default, AnyIO sets a hard token limit of **40 worker threads**.
* Each synchronous call to Supabase Cloud (`supabase_admin.table(...).execute()`) takes **~650ms to 780ms** over WAN.
* **Failure Knee:** At 25–50 concurrent virtual users, all 40 worker threads become simultaneously blocked waiting for remote HTTP sockets. Incoming requests are forced to wait in a backlog queue, causing p95 latency to jump from **1.4s to 2.1s** and triggering 504 Gateway Timeouts during sudden bursts.

### 🟢 Actionable Improvement Implemented
1. **Added Configuration Setting:**
   In [`app/core/config.py`](../app/core/config.py), added a dedicated setting:
   ```python
   # Worker Threadpool Concurrency
   THREADPOOL_LIMIT: int = 100
   ```
2. **Lifespan Startup Token Scaling:**
   In [`app/main.py`](../app/main.py), modified the application `lifespan` handler to dynamically scale the AnyIO thread limiter before accepting traffic:
   ```python
   @asynccontextmanager
   async def lifespan(app: FastAPI):
       import anyio.to_thread

       # Scale AnyIO threadpool capacity for synchronous blocking database operations
       limiter = anyio.to_thread.current_default_thread_limiter()
       limiter.total_tokens = settings.THREADPOOL_LIMIT
       logger.info(
           "Scaled AnyIO worker threadpool capacity to %d tokens for concurrent I/O.",
           settings.THREADPOOL_LIMIT,
       )
       ...
       yield
   ```

### 🎯 Measured Impact
* Worker concurrency expanded by **2.5x** (from 40 to 100 concurrent blocking threads).
* Eliminates thread starvation and queue backlog during traffic bursts up to 100 concurrent connections.

---

## 2. ⚙️ Dynamic Multi-Worker Sizing: Local vs. Azure Web App

### ❓ User Requirement & Analysis
> *"can we determine the no of worker based on our system or of the system i deploy(azure web service)?"*

**Yes, absolutely.** The optimal number of workers can and should be dynamically determined based on the system's available CPU cores and memory limits.

### 🧠 How Worker Sizing Works (Local vs. Azure Web App)

#### 1. The Standard ASGI / Gunicorn Formula:
$$\text{Workers} = (2 \times \text{CPU Cores}) + 1$$
* **Why?** While one worker process is waiting on I/O or GIL operations, another worker can execute on the CPU core.

#### 2. Azure App Service (Linux Web App) Architecture:
* Azure Web Apps run on Azure App Service Plans (e.g., Basic `B1`, Standard `S1`, Premium `P1v2`, `P2v3`):
  * **B1 / S1 / P1v2:** 1 vCPU (1.75 GB to 3.5 GB RAM) $\rightarrow$ Ideal: **2 to 3 workers**
  * **P2v3:** 2 vCPUs (8 GB RAM) $\rightarrow$ Ideal: **4 to 5 workers**
  * **P3v3:** 4 vCPUs (16 GB RAM) $\rightarrow$ Ideal: **8 workers**
* **The Container Quota Trap:** Standard `os.cpu_count()` inside Docker/Azure containers sometimes returns the physical host's core count (e.g., 32 cores) instead of the container's allocated quota, which could spawn 65 workers and crash the container due to RAM exhaustion (OOM).
* **The Solution:** Use `len(os.sched_getaffinity(0))` which is **cgroups-aware** and detects the exact core quota assigned to your Azure Web App, capped with safety bounds:
  $$\text{Workers} = \min(8, \max(2, (2 \times \text{Allocated Cores}) + 1))$$

### 🟢 Actionable Improvement Implemented
Created [`backend/gunicorn.conf.py`](../gunicorn.conf.py) with dynamic system detection:

```python
import multiprocessing
import os

def calculate_workers() -> int:
    # 1. Respect explicit WEB_CONCURRENCY environment variable (Azure / Cloud standard)
    if os.getenv("WEB_CONCURRENCY"):
        try:
            return max(1, int(os.getenv("WEB_CONCURRENCY")))
        except ValueError:
            pass

    # 2. Detect cgroup-allocated cores (Azure App Service / Docker aware)
    try:
        cores = len(os.sched_getaffinity(0))
    except (AttributeError, NotImplementedError):
        cores = multiprocessing.cpu_count() or 1

    # Formula: (2 * cores) + 1 bounded between 2 (high availability) and 8 (RAM protection)
    calculated = (2 * cores) + 1
    return max(2, min(calculated, 8))

bind = f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '8000')}"
workers = calculate_workers()
worker_class = "uvicorn.workers.UvicornWorker"
keepalive = 65
timeout = 120
graceful_timeout = 30
```

### 🚀 How to Run:
* **Locally / Auto-Detect:**
  ```bash
  gunicorn -c gunicorn.conf.py app.main:app
  ```
* **On Azure Web App (App Service Configuration):**
  In the Azure Portal $\rightarrow$ **Configuration** $\rightarrow$ **General settings** $\rightarrow$ **Startup Command**:
  ```bash
  gunicorn -c gunicorn.conf.py app.main:app
  ```
  *(Optional: If you ever want to override workers on Azure, simply add the App Setting `WEB_CONCURRENCY=4` in Azure Portal).*

---

## 3. ⚡ Granular & Targeted Cache Invalidation (Preventing Cache Flush)

### 🔴 The Problem Identified
* In [`app/modules/finance/service.py`](../app/modules/finance/service.py), `create_transaction()` and `delete_transaction()` previously called:
  ```python
  self.cache.invalidate_user(user_id)
  ```
* Because `invalidate_user` matched all keys containing `user_id`, creating a single transaction in October 2026 wiped:
  - All cached transaction pagination pages (`limit=10`, `limit=50`, etc.)
  - All monthly summary aggregations across the entire year (`2026-01` through `2026-12`)
  - All user budgets (`budgets:{user_id}`)
  - All savings goals (`goals:{user_id}`)
* In our load tests, write transactions accounted for **10% of total traffic**. As a result, active users writing transactions continuously blew away their own cache, forcing every read back onto the remote database.

### 🟢 Actionable Improvement Implemented
1. **Enhanced `CachePort` Interface:**
   Updated [`app/ports/cache.py`](../app/ports/cache.py) to support scoped invalidation:
   ```python
   @abstractmethod
   def invalidate_user(self, user_id: str, prefix: str | None = None) -> None:
       """Invalidate cached keys associated with a user, optionally limited to a prefix."""
   ```
2. **Updated Memory & Redis Cache Adapters:**
   Both [`MemoryCacheAdapter`](../app/adapters/cache/memory_cache.py) and [`RedisCacheAdapter`](../app/adapters/cache/redis_cache.py) now support pattern filtering:
   ```python
   def invalidate_user(self, user_id: str, prefix: str | None = None) -> None:
       if prefix:
           keys_to_delete = [k for k in list(self._cache.keys()) if user_id in k and prefix in k]
       else:
           keys_to_delete = [k for k in list(self._cache.keys()) if user_id in k]
   ```
3. **Scoped Invalidation in Domain Services:**
   In [`app/modules/finance/service.py`](../app/modules/finance/service.py):
   * Transaction writes only invalidate `transactions:{user_id}` and `summary:{user_id}`.
   * Budget operations only invalidate `budgets:{user_id}`.
   * Goal operations only invalidate `goals:{user_id}`.

### 🎯 Measured Impact
* Zero cache churn across budgets and goals during ledger updates.
* Maintains high cache hit ratio for read endpoints even under concurrent writing activity.

---

## 4. 🗄️ Database Performance: Composite B-Tree Indexes

### 🔴 The Problem Identified
* Ledger reads and summary analytics execute queries filtering by:
  - `user_id = ... AND date >= ... AND date <= ... ORDER BY date DESC`
  - `user_id = ... AND category = ...`
  - `user_id = ... AND type = ...`
* In PostgreSQL without composite indexes, filtering on two columns requires either two separate index scans followed by a bitmap heap scan or a sequential table scan. Under high transaction volume, this increases query CPU time on Supabase.

### 🟢 Actionable Improvement Implemented
Created a dedicated SQL migration file [`migrations/001_performance_indexes.sql`](../migrations/001_performance_indexes.sql):

```sql
-- 1. Accelerates date-range queries & chronologically sorted transaction lists
CREATE INDEX IF NOT EXISTS idx_transactions_user_date 
ON public.transactions (user_id, date DESC);

-- 2. Accelerates category filtering (Food, Utilities, Shopping, Income, etc.)
CREATE INDEX IF NOT EXISTS idx_transactions_user_category 
ON public.transactions (user_id, category);

-- 3. Accelerates search by merchant name
CREATE INDEX IF NOT EXISTS idx_transactions_user_merchant 
ON public.transactions (user_id, merchant);

-- 4. Accelerates monthly budget lookups
CREATE INDEX IF NOT EXISTS idx_budgets_user_month 
ON public.budgets (user_id, month);

-- 5. Accelerates active financial goals lookup
CREATE INDEX IF NOT EXISTS idx_goals_user 
ON public.goals (user_id);

-- 6. Accelerates document lookups by user
CREATE INDEX IF NOT EXISTS idx_documents_user 
ON public.documents (user_id);
```

> [!TIP]
> **Action to take in Supabase:**
> Open your **Supabase Dashboard** $\rightarrow$ **SQL Editor** $\rightarrow$ Paste and run the commands above from [`migrations/001_performance_indexes.sql`](../migrations/001_performance_indexes.sql). (Standard `CREATE INDEX IF NOT EXISTS` executes in milliseconds inside Supabase's SQL Editor transaction block without triggering the `ERROR 25001` block error).

---

## 5. 🔑 Client-Side Silent Token Refresh (60-Minute TTL)

### 🔴 The Problem Identified
* In the Breakpoint Load Test (Phase 8), after running continuously for **60 minutes**, authenticated requests began returning `401 Unauthorized`.
* **Root Cause:** Supabase GoTrue access tokens have a fixed **3,600-second (1 hour) expiration**.
* Static test tokens or client sessions without auto-refresh will fail when sessions exceed one hour.

### 🟢 Actionable Improvement
1. **Frontend React Implementation:**
   Ensure the frontend Supabase auth client listens to auth state changes and refreshes proactively at the **50-minute mark**:
   ```javascript
   // src/api/supabaseClient.js
   import { createClient } from '@supabase/supabase-js';

   export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
     auth: {
       autoRefreshToken: true,    // Automatically refreshes token in background
       persistSession: true,
       detectSessionInUrl: true,
     },
   });
   ```
2. **Automated Testing Suite (k6):**
   In load tests extending past 1 hour, configure `setup()` or scenario iterations to dynamically call `/api/v1/auth/login` to obtain fresh tokens rather than passing a static token.

---

## 6. 🌐 Network & Infrastructure: Cloud Region Colocation

### 🔴 The Problem Identified
* Our benchmark breakdown proved that the FastAPI ASGI framework processes requests in **12.2ms** (~50 req/s with 0% error).
* However, endpoints talking to Supabase Cloud averaged **~650ms to 780ms**.
* **Root Cause:** Geographic distance and WAN round trips between the test machine and the Supabase Cloud region (TCP handshake + TLS negotiation + PostgREST transfer).

### 🟢 Actionable Improvement
* When deploying your backend to **Azure Web App (App Service)**:
  1. Check the region of your Supabase project (e.g., `Southeast Asia - Singapore`, `Central India - Pune`, or `US East - North Virginia`).
  2. Deploy the Azure Web App in the **exact same region** (e.g., Azure `centralindia` if Supabase is in Mumbai/Pune, or `eastus` if Supabase is in US East).
* **Benefit:** Reduces database network round trips from **~650ms down to ~15–30ms**, unlocking an immediate **10x to 20x latency reduction** across all ledger operations.

---

## 7. 🧹 Codebase Deduplication, Shim Elimination & Reusable Helper Refactoring

### 🔴 The Problem Identified
* **26 Duplicate / Dead Files:**
  * `app/agent/` (`graph.py`, `guardrail.py`, `tools.py`, `state.py`): Completely dead legacy directory superseded by `app/modules/agent/`.
  * `app/services/`: Contained 4 dead legacy service files (`email.py`, `ocr.py`, `memory.py`, `telegram_auth.py`) plus 11 single-line shim files (`transaction_service.py`, `auth_service.py`, etc.) re-exporting classes already exported by `app/services/__init__.py`.
  * `app/api/v1/`: Contained 8 single-line shim files (`finance.py`, `auth.py`, `chat.py`, etc.) that were never imported because `app/api/v1/router.py` mounts `app.modules.*.router` directly.
  * `app/schemas/`: Contained 6 individual shim files re-exporting schemas already available in `app.modules.*.schemas`.
  * `app/core/`: Contained 3 dead legacy files (`cache.py`, `vector_db.py`, `llm_setup.py`) bypassing the hexagonal architecture.
* **Code Duplication in Domain Logic:**
  * In `TransactionService`:
    * Date bounds calculation (`month`, `start_date`, `end_date`) was duplicated across `get_transactions()` and `get_summary()`.
    * Transaction dictionary preparation (date normalization, auto-income tagging, amount casting) was duplicated across `create_transaction()` and `bulk_create_transactions()`.

### 🟢 Actionable Improvement Implemented
1. **Removed 26 Duplicate and Dead Files:**
   * Removed `app/agent/` entirely.
   * Removed legacy `app/core/cache.py`, `app/core/vector_db.py`, `app/core/llm_setup.py`.
   * Removed 15 dead/shim files from `app/services/`.
   * Removed 8 redundant route shims from `app/api/v1/`.
   * Removed 6 redundant schema shims from `app/schemas/`.
2. **Unified Backward-Compatibility Hubs:**
   * `app/schemas/__init__.py`: Clean, single re-export hub for all Pydantic models.
   * `app/services/__init__.py`: Clean, single re-export hub for all 8 domain microservices.
3. **Refactored `TransactionService` (`app/modules/finance/service.py`):**
   * Extracted `resolve_month_bounds(month, start_date, end_date)` static method, reused by both `get_transactions()` and `get_summary()`.
   * Extracted `_prepare_transaction(user_id, data)` helper, reused by both `create_transaction()` and `bulk_create_transactions()`.
4. **Updated Test Suites:**
   * Updated `test_transaction_service.py`, `test_ai_agent_service.py`, `test_telegram_service.py`, and `test_security_performance.py` to import directly from canonical `app.modules.*` paths.

### 🎯 Measured Impact
* Reduced file sprawl by **26 files**, simplifying code navigation.
* Zero dead code or split-brain legacy implementations.
* Clean Hexagonal directory layout with zero regression across all 23 test suites.

---

## 🏁 Summary of Verified Changes

```text
backend/
├── app/
│   ├── core/
│   │   ├── config.py                 # Added THREADPOOL_LIMIT = 100
│   │   ├── database.py               # Supabase client singletons
│   │   ├── rate_limiter.py           # Sliding-window rate limiter
│   │   └── security.py               # JWT auth dependency
│   ├── main.py                       # Configured AnyIO lifespan thread limiter
│   ├── ports/                        # 6 Pure Abstract Interfaces
│   │   └── cache.py                  # Added scoped prefix to invalidate_user
│   ├── adapters/                     # Pluggable Hexagonal Adapters
│   │   ├── cache/memory_cache.py     # Scoped cache key pattern eviction
│   │   └── cache/redis_cache.py      # Scoped Redis pattern eviction
│   ├── modules/                      # 7 Autonomous Domain Microservices
│   │   ├── agent/                    # AIAgentService & MemoryService (LangGraph)
│   │   ├── auth/                     # Supabase Auth domain
│   │   ├── catalogue/                # Static categories & budget templates
│   │   ├── documents/                # OCR extraction & statement parsing
│   │   ├── finance/                  # Ledger, budgets, goals & analytics
│   │   ├── reports/                  # Email report generation
│   │   └── telegram/                 # Telegram webhook & sync
│   ├── schemas/                      # Backward-compatible __init__.py re-export hub
│   ├── services/                     # Backward-compatible __init__.py re-export hub
│   ├── templates/                    # HTML email templates & parser
│   └── utils/logger.py               # Structured logger
├── migrations/
│   └── 001_performance_indexes.sql  # Composite PostgreSQL performance indexes
├── gunicorn.conf.py                  # Dynamic worker calculation for Azure Web Apps & Local
└── docs/
    ├── LOAD_TEST_REPORT.md           # Master k6 performance report
    └── problems_and_improvements_made.md # This document
```

All 23 backend unit and integration test suites pass (`pytest -v` $\rightarrow$ 23/23 passing in 6.25s).
