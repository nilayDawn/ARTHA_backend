# Spike Test Report

## 1. Test Overview
The Spike Test evaluated the resilience, elasticity, and recovery dynamics of the ARTHA AI API during an abrupt, severe traffic burst. Concurrency jumped rapidly from a 2 VU calm baseline to a 35 VU peak within 10 seconds (**a 17.5x sudden surge**), held for 30 seconds, plummeted back to 2 VUs, and observed a 30-second recovery window.

* **Target URL:** `http://localhost:8000`
* **Test Timestamp:** 2026-10-07T05:03:44.126Z
* **Raw Result File:** `load-tests/results/spike-2026-10-07-103344.json`
* **Authentication:** Active (Supabase Bearer JWT)

---

## 2. Test Configuration

| Parameter | Configured Value | Description |
| :--- | :--- | :--- |
| Stages Profile | 2 VUs (20s) → 35 VUs (10s) → Hold 35 VUs (30s) → 2 VUs (10s) → Hold 2 VUs (30s) → 0 VUs (10s) | Severe abrupt spike profile |
| Total Duration | 1 minute 50 seconds | Compact shock test |
| Baseline Traffic | 2 VUs | Calm state |
| Peak Surge | 35 VUs | 17.5x immediate surge |
| User Think Time | Random 0.4s – 1.0s | Paced user traffic |
| Traffic Distribution | 40% Tx Reads, 25% Summary, 15% Catalog, 10% Writes, 5% Budgets/Goals, 5% Health/Profile | Same realistic weighted workload |

---

## 3. Overall Result
* **Status:** **PASSED** (Excellent Elastic Recovery)
* **Total Requests:** **1,039** requests
* **Throughput:** **9.43 req/sec**
* **HTTP Failure Rate:** **1.44%** (15 errors out of 1,039 total requests)
* **Checks Pass Rate:** **99.52%** (3,102 passed, 15 failed)

---

## 4. Key Metrics & SLA Thresholds

| Metric | Measured Value | Threshold Target | Status |
| :--- | :--- | :--- | :---: |
| HTTP Failure Rate | 1.44% (15 errors) | `< 8.0%` | **PASSED** |
| Checks Pass Rate | 99.52% | `> 92.0%` | **PASSED** |
| Average Latency | 875.00 ms | - | - |
| Median Latency | 853.84 ms | - | - |
| p90 Latency | 1715.31 ms | `< 2500 ms` | **PASSED** |
| p95 Latency | 1925.66 ms | `< 3500 ms` | **PASSED** |
| Max Latency | 3117.77 ms | - | Peak burst queue latency |

---

## 5. Endpoint Performance Breakdown

| Endpoint / Operation | Total Requests | Failed | Error Rate | Avg Latency | p90 Latency | p95 Latency | Assessment |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `GET /health` | 40 | 0 | 0.0% | 4.07 ms | 3.30 ms | 4.55 ms | Impervious to traffic spikes |
| `GET /api/v1/catalogue/*` | 114 | 0 | 0.0% | 3.85 ms | 7.14 ms | 9.92 ms | Flawless shock absorption |
| `GET /api/v1/auth/me` | 40 | 2 | 5.0% | ~540 ms | ~890 ms | ~1200 ms | Handled sudden burst |
| `GET /api/v1/transactions` | 366 | 6 | 1.64% | 972.42 ms | 1764.21 ms | 1913.49 ms | Handled burst; recovered cleanly |
| `GET /api/v1/summary` | 251 | 2 | 0.80% | 948.70 ms | 1651.36 ms | 1927.75 ms | Stable analytics execution |
| `POST /api/v1/transactions` | 92 | 0 | **0.0%** | ~980 ms | ~1600 ms | ~1850 ms | **100% write success (92 created)** |
| `DELETE /api/v1/transactions/:id` | 92 | 3 | 3.26% | ~790 ms | ~1300 ms | ~1500 ms | 89 cleaned up immediately |
| `GET /api/v1/budgets` | 27 | 1 | 3.70% | ~710 ms | ~1150 ms | ~1350 ms | Minor transient drop during burst |
| `GET /api/v1/goals` | 17 | 1 | 5.88% | ~700 ms | ~1100 ms | ~1300 ms | Minor transient drop during burst |

---

## 6. Shock & Recovery Dynamics Analysis

1. **Shock Absorption Phase (2 → 35 VUs in 10s):**
   * Total latency inflated from baseline ~480 ms to a peak of **3,117.77 ms** as concurrent requests queued for remote database round trips.
   * Only **15 requests** failed across the entire burst (1.44% error rate), demonstrating that the system's ASGI event loop buffered the sudden influx without dropping worker processes.
2. **Post-Spike Recovery Window (35 → 2 VUs):**
   * Immediately following the 10-second drop back to 2 VUs, queued connections cleared completely.
   * Latency for in-memory routes dropped back to **sub-5ms**, and database queries normalized to **450–650 ms**.
   * Zero leftover queue lag or hanging connections were observed.

---

## 7. Findings

### Finding: Flawless In-Memory Shock Absorption
**Severity:** Informational
**Evidence:**  
Across 154 combined calls to `/health` and `/catalogue/*`, average latency was **3.8 – 4.1 ms** with **0 failures**, even during the peak 35 VU spike.
**Status:** Confirmed
**Cause:**  
Endpoints that do not touch remote network databases are completely decoupled from external WAN bottlenecks and absorb sudden traffic surges effortlessly.
**Confidence:** High

### Finding: Controlled Database Saturation Under Burst Conditions
**Severity:** Low
**Evidence:**  
During the 17.5x concurrency burst, 15 HTTP requests failed (1.44% of total requests) with max latency peaking at 3.11s. All 92 write operations (`POST /transactions`) succeeded with HTTP 201.
**Status:** Confirmed
**Cause:**  
A rapid spike from 2 to 35 concurrent requests temporarily saturated the HTTP connection pool to Supabase Auth and PostgreSQL, causing a small fraction of requests to encounter gateway timeouts.
**Recommendation:**  
Increase client connection pool limits and configure graceful client retry with exponential backoff for transient 500/504 responses during sudden spikes.
**Confidence:** High

---

## 8. Severity Summary
* **Critical:** 0
* **High:** 0
* **Medium:** 0
* **Low:** 1 (1.44% transient failures during 17.5x surge)
* **Informational:** 1 (Immediate post-spike recovery with zero hanging connections)

---

## 9. Conclusion
The API demonstrated strong elasticity and shock absorption during the Spike Test. It absorbed a **17.5x traffic surge** with only a **1.44% transient error rate** and recovered to full health immediately once traffic normalized.

The system is validated and ready for **Phase 7: Soak Test** to evaluate stability, memory behavior, and resource consumption over a sustained duration.
