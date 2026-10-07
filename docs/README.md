# 📚 ARTHA AI — Backend Documentation Hub

<p align="center">
  <img src="https://img.shields.io/badge/Repository-Backend%20Engine-7952b3?style=for-the-badge" alt="Repository" />
  <img src="https://img.shields.io/badge/Author-Nilay%20Dawn-009688?style=for-the-badge" alt="Author" />
</p>

> [!NOTE]
> This `docs/` directory is the technical specifications repository, architecture design log, and performance benchmark archive for the **ARTHA AI Backend**.
>
> Return to root: [⬅️ Backend README](../README.md)

---

## 🗂️ Documentation Index

| Document | Description | Target Audience |
| :--- | :--- | :--- |
| ⚡ **[LOAD_TEST_REPORT.md](LOAD_TEST_REPORT.md)** | **k6 API Load Testing & Benchmarks**: Comprehensive multi-scenario performance test results (Smoke, Load, Stress, Spike, Soak, Breakpoint), throughput analysis (~50 req/s), latency SLAs, capacity boundaries, and engineering findings. | Performance Engineers, System Architects, SREs |
| 🛠️ **[problems_and_improvements_made.md](problems_and_improvements_made.md)** | **Audit Bottlenecks & Improvements**: Root causes identified during load testing (threadpool starvation, over-invalidation, worker sizing for Azure Web App), code optimizations implemented, and migration indexes. | Performance Engineers, Backend Developers, Cloud Ops |
| 🏛️ **[ARCHITECTURE.md](ARCHITECTURE.md)** | **System Architecture & ADRs**: High-level Hexagonal topology, LangGraph StateGraph agent machine, multimodal OCR data flow, security defense-in-depth, and formal Architectural Decision Records (ADRs). | Software Architects, Engineering Leads |
| 📄 **[PRD.md](PRD.md)** | **Product Requirement Document**: Real-world user problem analysis, target user personas, promised vs. delivered feature matrix, non-functional requirements, and product roadmap. | Product Owners, Recruiters, Tech Leads |
| 📈 **[PROGRESS.md](PROGRESS.md)** | **Personal Engineering Progress & Logbook**: Milestone delivery tracking (Phases 1–5 completed, 6 & 7 backlog), benchmark verification logs, daily engineering journal, bug fixes, and active sprint checklists. | Developers & Engineering Leads |

---

### 📊 Scenario-Specific Performance Reports

Detailed raw metrics, latency breakdowns, and findings for each individual k6 test scenario:

* 🔬 **[Smoke Test (2 VUs)](performance/smoke-report.md)** — Sanity, schema validation, cold-start latency analysis
* ⚖️ **[Normal Load Test (10 VUs)](performance/load-report.md)** — 777 requests, 100% check pass rate, 0.00% error baseline
* 🧗 **[Stress Test (50 VUs)](performance/stress-report.md)** — 4,493 requests, 5x concurrency scale, degradation knee identification
* ⚡ **[Spike Test (35 VUs)](performance/spike-report.md)** — Sudden 17.5x traffic surge, elastic recovery verification
* 🌊 **[Soak Test (12 VUs)](performance/soak-report.md)** — Continuous sustained load, zero latency creep, leak validation
* 💥 **[Breakpoint Test (75 VUs)](performance/breakpoint-report.md)** — 12,919 requests, ~50 req/s in-memory engine throughput ceiling

---

## 🏗️ Backend Directory Structure

```text
backend/
├── README.md                         # 🏛️ Root Backend README (Quickstart, Features, Badges)
├── docs/                             # 📚 Technical Documentation & Benchmark Hub
│   ├── README.md                     # This documentation index
│   ├── LOAD_TEST_REPORT.md           # Master k6 performance audit report
│   ├── problems_and_improvements_made.md # Load test audit bottlenecks & code fixes
│   ├── ARCHITECTURE.md               # Hexagonal Architecture & ADRs
│   ├── PRD.md                        # Product Requirements Document
│   ├── PROGRESS.md                   # Development milestones & engineering log
│   └── performance/                  # Individual k6 test scenario reports
│       ├── smoke-report.md
│       ├── load-report.md
│       ├── stress-report.md
│       ├── spike-report.md
│       ├── soak-report.md
│       └── breakpoint-report.md
├── app/                              # Hexagonal Ports, Pluggable Adapters, 7 Domain Modules
├── migrations/                       # SQL migrations & performance indexes
│   └── 001_performance_indexes.sql
├── gunicorn.conf.py                  # Dynamic multi-worker config for local & Azure
├── tests/                            # 23 Automated Pytest suites (1.90s execution)
├── load-tests/                       # k6 load testing scenarios, configs & helpers
└── requirements.txt                  # Python dependencies
```

