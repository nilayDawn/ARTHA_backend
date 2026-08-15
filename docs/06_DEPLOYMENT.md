# Complete Production Deployment & Architecture Documentation

**Project:** FinPilot AI (API Service: `artha-api-live`)

**Target Environment:** Azure App Service (Linux, Python 3.12)

**Authentication & Storage:** Supabase

**Vector Long-Term Memory:** Qdrant Cloud Cluster

**AI & Multimodal Vision:** Google Gemini 2.5

**Interface Channels:** React (Vite) Web SPA & Telegram Bot (`@BotFather` Webhook)

---

## 1. Executive Summary & Architectural Decisions

### 1.1 Why Azure App Service vs. Free Tier Hosts (e.g., Render / Fly.io / Vercel Serverless)

When designing production architectures for multimodal, agentic AI systems like FinPilot AI, choice of infrastructure directly impacts reliability, latency, and operational throughput:

1. **Elimination of Cold Starts ($0$ Inactivity Latency):**
* *The Problem:* Free-tier hosting providers (like Render or Railway free tiers) force inactive compute containers to hibernate after 10–15 minutes of idle time. Waking an ASGI application containing heavy AI dependencies (Google GenAI SDK, Pydantic core serialization engines, Qdrant client connections, LangGraph workflows) takes **25 to 50 seconds**.
* *The Azure Solution:* By utilizing an **Azure App Service Basic (B1) Plan** powered by the **Azure for Students Subscription**, the app operates on dedicated compute (1 Dedicated vCPU, 1.75 GB RAM) with the `Always On` flag activated. The container never sleeps.


2. **Telegram Webhook Stability:**
* Telegram's webhook dispatcher has an internal timeout (~5 seconds). If a user uploads a receipt image on Telegram while a server is hibernated, Telegram encounters a connection timeout, fails the update, or sends cascading retries. Azure responds to incoming webhook POST events in sub-millisecond dispatch times.


3. **Segregated Monorepo vs. Two Repositories:**
* Rather than maintaining a complex polyrepo build or a combined monorepo build with nested root configs, we maintain two discrete GitHub repositories (`backend` and `frontend`). This decouples continuous integration pipelines, isolates deployment failures, and eliminates build-path ambiguity.



```
                    ┌────────────────────────────────────────────────────────┐
                    │               FINPILOT AI CLOUD ARCHITECTURE           │
                    └────────────────────────────────────────────────────────┘

    [ Telegram Bot Client ]                  [ React + Vite SPA Frontend ]
               │                                           │
               │ HTTPS Webhook                             │ REST API (Bearer JWT)
               ▼                                           ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ AZURE APP SERVICE (Linux Container - Python 3.12 - Basic B1 Plan)                         │
│ App Name: artha-api-live                                                                 │
│ URL: https://artha-api-live-f3cke3azcmd2d4fw.centralindia-01.azurewebsites.net             │
│                                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Process Supervisor: Gunicorn 26.0 (2 Workers)                                       │  │
│  │ Worker Engine:      Uvicorn ASGI (uvicorn.workers.UvicornWorker)                    │  │
│  │ Binding Interface:  0.0.0.0:8000 (Internal Routing)                                 │  │
│  └──────────────────────────────────────────┬──────────────────────────────────────────┘  │
│                                             │                                             │
│  ┌──────────────────────────────────────────▼──────────────────────────────────────────┐  │
│  │ FastAPI Application Layer (app.main:app)                                            │  │
│  │  ├─ /api/v1/auth        (User identity verification & session management)           │  │
│  │  ├─ /api/v1/finance     (Transactions, budgets, categories, goals CRUD)            │  │
│  │  ├─ /api/v1/documents   (Receipt & statement upload pipeline)                       │  │
│  │  ├─ /api/v1/chat        (LangGraph + Gemini conversational agent)                   │  │
│  │  ├─ /api/v1/telegram    (Webhook processor, bot routing & account linking)          │  │
│  │  └─ /api/v1/reports     (Monthly AI executive summaries via Resend SMTP)            │  │
│  └──────────────────┬───────────────────────┬───────────────────────────┬──────────────┘  │
└─────────────────────┼───────────────────────┼───────────────────────────┼─────────────────┘
                      │                       │                           │
                      ▼                       ▼                           ▼
          ┌───────────────────────┐ ┌───────────────────┐     ┌───────────────────────┐
          │     SUPABASE BAAS     │ │   QDRANT CLOUD    │     │   GOOGLE GEMINI API   │
          │  ├─ PostgreSQL (OLTP) │ │  Vector Database  │     │  ├─ Gemini 2.5 Flash  │
          │  ├─ Auth Engine (JWT) │ │  User Financial   │     │  │  Vision OCR Engine │
          │  └─ Storage Buckets   │ │  Memory Embeddings│     │  └─ LangGraph Routing │
          └───────────────────────┘ └───────────────────┘     └───────────────────────┘

```

---

## 2. Step-by-Step Deployment Lifecycle & Rationale

### Step 1: Azure App Service Resource Provisioning

* **Resource Group:** `ARTHA_rg` (Logical grouping for security policies, regional collocation, and unified billing breakdown).
* **Service Plan:** `ASP-ARTHArg-b7e3` (Linux, Tier: Basic B1).
* **Runtime Stack:** `Python 3.12`.
* **Region:** `Central India` (Minimizes network round-trip time for regional queries).

#### Rationale for Configuration Parameters:

1. **Operating System (Linux):** Linux provides standard POSIX container environments required for high-performance Python ASGI processes, eliminating Windows OS virtualization overhead.
2. **Startup Command Customization:**
```bash
gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120

```


* `--workers 2`: Formula $(2 \times \text{vCPU}) = 2$ workers allows parallel processing of concurrent requests. If one worker is blocked awaiting a long Gemini OCR document parse or Qdrant vector retrieval, the second worker continues accepting incoming Telegram webhook updates without request dropping.
* `--worker-class uvicorn.workers.UvicornWorker`: Combines Gunicorn's process monitoring and auto-restart capabilities with Uvicorn's event loop (`uvloop`).
* `--bind 0.0.0.0:8000`: Explicitly binds to port 8000, which Azure App Service automatically routes via its internal reverse proxy.
* `--timeout 120`: Increases standard worker timeout to 120 seconds, preventing worker termination during heavy multi-page bank statement parsing with large multimodal contexts.



---

### Step 2: Environment Variable Configuration

The following production variables were persisted into Azure App Service configuration:

| Key | Purpose / Role |
| --- | --- |
| `SUPABASE_URL` | Base API URL to managed Supabase database instance. |
| `SUPABASE_ANON_KEY` | Public client token for user-scoped JWT queries. |
| `SUPABASE_SERVICE_ROLE_KEY` | Elevated administrative key used by backend workers to bypass Row Level Security when syncing background Telegram jobs. |
| `BUCKET_NAME` | S3-compatible private bucket (`financial_documents`) storing user receipt scans and PDFs. |
| `GEMINI_API_KEY` | Access token for Google Gemini 2.5 Flash multimodal models and embeddings. |
| `QDRANT_URL` | Cluster endpoint for vector storage and semantic financial memory. |
| `QDRANT_API_KEY` | Authentication key for remote Qdrant Cloud. |
| `TELEGRAM_BOT_TOKEN` | Secure token issued by `@BotFather` to validate incoming bot actions. |
| `RESEND_API_KEY` | Transactional email API token for delivering monthly automated financial health reports. |
| `EMAIL_FROM` | Verified sender signature (`FinPilot AI <onboarding@resend.dev>`). |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | Set to `1`. Instructs Azure Oryx to run native server-side builds (`pip install`). |
| `ENABLE_ORYX_BUILD` | Set to `true`. Activates the Oryx compiler engine. |

---

### Step 3: CI/CD Automation via GitHub Actions & Publish Profile

#### Solving the Microsoft Entra ID (OIDC) Limitation:

Azure default workflows attempt to negotiate an OpenID Connect (OIDC) federated token via Microsoft Entra ID. Because Azure for Students subscriptions operate inside shared university directory tenants with restricted identity permissions, standard users lack administrative rights to create Federated Enterprise App Registrations.

#### The Secure Solution: SCM Publish Profile

By downloading the encrypted XML Publish Profile from Azure App Service (`SCM Basic Auth`) and injecting it as a repository secret (`AZUREAPPSERVICE_PUBLISHPROFILE`), GitHub Actions deploys authenticated source payloads directly without requiring Entra ID tenant administrative privilege.

#### Final `.github/workflows/deploy.yml` Pipeline:

```yaml
name: Deploy FastAPI Backend to Azure Web App

on:
  push:
    branches:
      - main
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository source
        uses: actions/checkout@v4

      - name: Deploy source code to Azure App Service
        uses: azure/webapps-deploy@v3
        with:
          app-name: 'artha-api-live'
          publish-profile: ${{ secrets.AZUREAPPSERVICE_PUBLISHPROFILE }}
          package: .

```

---

## 3. Critical Production Bugs Encountered & Solutions Applied

During the deployment lifecycle, three fundamental cloud-architecture errors occurred. Understanding their root causes ensures long-term operational resilience:

### Incident 1: `OSError: [Errno 30] Read-only file system: '/home/site/wwwroot/Logs/...'`

* **Symptoms:** Gunicorn master initialized, but worker processes repeatedly threw `Worker failed to boot (Exit Code: 3)`.
* **Root Cause:** In the local development codebase, `app/utils/logger.py` instantiated a `TimedRotatingFileHandler` that attempted to write log files to the local disk (`/home/site/wwwroot/Logs/logs_YYYY-MM-DD.log`). When applications are deployed into Azure App Service containers, the root application directory (`/home/site/wwwroot`) is mounted as **strictly read-only** to guarantee immutable infrastructure.
* **Resolution:** Re-engineered `app/utils/logger.py` to stream directly to standard output (`sys.stdout`) using a `logging.StreamHandler`. Azure's native telemetry forwarder automatically intercepts `sys.stdout` and routes it into the Azure Live Log Stream and Azure Application Insights without disk writes.

```python
# app/utils/logger.py
import logging
import sys

def setup_logging():
    logger = logging.getLogger("FinPilotAI")
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    log_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    return logger

logger = setup_logging()

```

---

### Incident 2: `ImportError: GLIBC_2.33 not found (cryptography / rust.abi3.so)`

* **Symptoms:** App crashed on boot with `ImportError: /lib/x86_64-linux-gnu/libc.so.6: version 'GLIBC_2.33' not found`.
* **Root Cause:** When the GitHub Actions workflow executed `pip install --target=".python_packages/..."` inside GitHub's `ubuntu-latest` virtual runner (Ubuntu 24.04), `pip` downloaded binary `.whl` files for compiled C/Rust dependencies (`cryptography`, `pydantic-core`) compiled against **GLIBC 2.33+**. However, Azure App Service runs an enterprise Linux base image with **GLIBC 2.31**. When the container attempted to dynamic-link the pre-compiled `.so` library, the OS kernel rejected it due to the binary version mismatch.
* **Resolution:**
1. Removed the client-side `pip install` from GitHub Actions.
2. Configured GitHub Actions to push raw, uncompiled application source code directly (`package: .`).
3. Configured `SCM_DO_BUILD_DURING_DEPLOYMENT=1` and `ENABLE_ORYX_BUILD=true` in Azure, forcing Azure's **Oryx Build Engine** to download and build wheels compiled directly against the container's exact GLIBC target environment.



---

### Incident 3: Missing `email-validator` Dependency

* **Symptoms:** Pydantic schema validation for `UserSignUp` failed on import with `ImportError: email-validator is not installed`.
* **Root Cause:** `pydantic` requires the optional `email-validator` package to evaluate `EmailStr` types at runtime.
* **Resolution:** Appended `email-validator>=2.1.0` and `resend>=0.8.0` directly to `requirements.txt`.

---

## 4. Telegram Webhook Production Integration

### 4.1 Transition from Polling/Ngrok to Production HTTPS Webhook

During development, bots often rely on `getUpdates` (long-polling) or `ngrok` tunnels. In production, polling wastes CPU cycles and memory. Switching to an event-driven HTTPS webhook allows Telegram servers to send incoming updates directly to FastAPI as HTTP POST requests.

### 4.2 Webhook Registration

Executed against the official Telegram Bot API:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://artha-api-live-f3cke3azcmd2d4fw.centralindia-01.azurewebsites.net/api/v1/telegram/webhook"}'

```

### 4.3 Webhook Verification Payload

Running `getWebhookInfo` confirmed active registration:

```json
{
  "ok": true,
  "result": {
    "url": "https://artha-api-live-f3cke3azcmd2d4fw.centralindia-01.azurewebsites.net/api/v1/telegram/webhook",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "max_connections": 40,
    "ip_address": "...",
    "allowed_updates": ["message", "edited_message", "callback_query"]
  }
}

```

---

## 5. Verification & Live Endpoint Catalog

The backend service is healthy and accepting encrypted traffic over TLS 1.3:

* **Base Production Host:** `https://artha-api-live-f3cke3azcmd2d4fw.centralindia-01.azurewebsites.net`
* **Health Check Probe:** `GET /health` $\rightarrow$ `{"status": "healthy"}`
* **Interactive OpenAPI Swagger Documentation:** `GET /docs`
* **OpenAPI Schema Specification:** `GET /openapi.json`
* **Telegram Webhook Receiver:** `POST /api/v1/telegram/webhook`
* **Conversational AI Agent Endpoint:** `POST /api/v1/chat`
* **Multimodal OCR Processing:** `POST /api/v1/documents/upload`
* **Automated Financial Reporting:** `POST /api/v1/reports/send-email`

---

## 6. Maintenance & Operational Runbook

### How to Deploy Future Backend Code Updates:

Because continuous deployment is established via GitHub Actions:

1. Make your code modifications locally.
2. Commit and push directly to your backend repository's `main` branch:
```bash
git add .
git commit -m "feat: enhance conversational agent memory context"
git push origin main

```


3. GitHub Actions will package the source code, deploy it to Azure App Service, trigger Oryx to install any new dependencies in `requirements.txt`, and gracefully reload Gunicorn worker processes with zero user downtime.