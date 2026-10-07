# ARTHA AI — k6 API Load Testing Suite

Comprehensive, professional k6 load-testing suite for the ARTHA AI Personal Finance API.

---

## Directory Structure

```text
load-tests/
├── results/              # Machine-readable output JSONs and execution summaries
├── scenarios/            # Test scenario scripts
│   ├── smoke.js          # Smoke Test (1-2 VUs, functionality & health sanity)
│   ├── load.js           # Average Load Test (realistic traffic distribution)
│   ├── stress.js         # Stress Test (gradual ramp to identify degradation)
│   ├── spike.js          # Spike Test (sudden traffic burst & recovery)
│   ├── soak.js           # Soak / Endurance Test (sustained load for leak detection)
│   └── breakpoint.js     # Breakpoint / Capacity Test (find max sustainable limit)
├── helpers/
│   ├── auth.js           # Bearer authentication resolution and headers
│   ├── data.js           # Realistic data generators (transactions, budgets, users)
│   └── checks.js         # Assertions, validation checks, and custom metrics
├── config.js             # Base configuration, thresholds, and summary handlers
├── collection.json       # Postman API Collection
└── README.md             # Documentation and usage instructions
```

---

## Configuration & Environment Variables

The test suite is fully configurable via standard environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `BASE_URL` | `http://localhost:8000` | Target API host and port |
| `AUTH_TOKEN` | *(empty)* | Optional Bearer JWT token for authenticated endpoints |
| `RESULTS_DIR` | `load-tests/results` | Target directory where JSON test reports are stored |
| `SMOKE_VUS` | `2` | Number of virtual users for Smoke Test |
| `SMOKE_DURATION`| `30s` | Test duration for Smoke Test |

---

## Running the Tests

Execute tests from the project root or backend directory using `k6 run`.

### 1. Smoke Test (Unauthenticated / Public Sanity)
```bash
k6 run load-tests/scenarios/smoke.js
```

### 2. Smoke Test (With Authenticated Endpoints)
If you have a Supabase user Bearer token:
```bash
AUTH_TOKEN="<your_jwt_token>" k6 run load-tests/scenarios/smoke.js
```

---

## Results & Reporting

Every test run automatically records:
1. A machine-readable JSON artifact inside `load-tests/results/<scenario>-<timestamp>.json`
2. A high-level summary printed to stdout in the terminal.

These JSON outputs preserve metrics across all runs and feed directly into the final `LOAD_TEST_REPORT.md`.
