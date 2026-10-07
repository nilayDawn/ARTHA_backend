/**
 * ============================================================================
 * ARTHA AI — k6 Soak / Endurance Test Scenario
 * ============================================================================
 * 
 * Purpose:
 * Detects degradation that manifests exclusively over extended periods of continuous
 * execution at a sustainable load level. 
 * Evaluates:
 * - Gradual latency creep or throughput decay over time
 * - Memory leak indicators or connection pool exhaustion
 * - Long-term stability of database connections and cache layers
 * 
 * Soak Profile (Development-Safe Extended Window):
 * - Stage 1 : Ramp Up    : 0 -> 12 VUs over 30s
 * - Stage 2 : Steady Hold: Hold 12 VUs for 3m00s  (Sustained continuous traffic)
 * - Stage 3 : Ramp Down  : 12 -> 0 VUs over 20s
 * Total Duration: ~3 minutes 50 seconds (configurable via SOAK_DURATION)
 * 
 * Workload Distribution:
 * - 40% : Transaction Ledger Reads  (GET /api/v1/transactions with filters)
 * - 25% : Financial Analytics       (GET /api/v1/summary with month params)
 * - 15% : Catalog Reference Data    (GET /api/v1/catalogue/*)
 * - 10% : Transaction Writes        (POST /transactions with immediate cleanup)
 * -  5% : Budgets & Goals           (GET /budgets, GET /goals)
 * -  5% : Health & User Profile     (GET /health, GET /auth/me)
 * 
 * Environment Variables Supported:
 * - BASE_URL       : Target API host (default: "http://localhost:8000")
 * - AUTH_TOKEN     : Bearer JWT token for authenticated operations
 * - SOAK_VUS       : Steady sustained concurrency (default: 12)
 * - SOAK_HOLD_TIME : Duration of steady hold stage (default: "3m")
 * 
 * Execution:
 *   AUTH_TOKEN="<token>" k6 run scenarios/soak.js
 * ============================================================================
 */

import http from 'k6/http';
import { sleep, group } from 'k6';
import { BASE_URL, DEFAULT_PARAMS, createSummaryHandler } from '../config.js';
import { getAuthHeaders, resolveToken, hasAuthToken } from '../helpers/auth.js';
import { generateTransaction, formatMonth } from '../helpers/data.js';
import {
  verifyResponse,
  healthDuration,
  catalogueDuration,
  transactionDuration,
  summaryDuration,
} from '../helpers/checks.js';

const SUSTAINED_VUS = parseInt(__ENV.SOAK_VUS || '12', 10);
const HOLD_DURATION = __ENV.SOAK_HOLD_TIME || '3m';

export const options = {
  stages: [
    { duration: '30s', target: SUSTAINED_VUS },   // Stage 1: Gentle ramp-up
    { duration: HOLD_DURATION, target: SUSTAINED_VUS }, // Stage 2: Sustained endurance window
    { duration: '20s', target: 0 },               // Stage 3: Gentle ramp-down
  ],
  thresholds: {
    http_req_failed: ['rate<0.02'],                       // Error rate must remain < 2% throughout
    http_req_duration: ['p(90)<1200', 'p(95)<1600'],       // Latency must not suffer progressive creep
    checks: ['rate>0.98'],                                // Assertion pass rate > 98%
  },
};

export const handleSummary = createSummaryHandler('soak');

export function setup() {
  const token = resolveToken(BASE_URL);
  return { token };
}

export default function (data) {
  const token = data?.token || '';
  const isAuthEnabled = hasAuthToken(token);
  const authHeaders = isAuthEnabled ? getAuthHeaders(token) : DEFAULT_PARAMS.headers;
  const authParams = { headers: authHeaders, timeout: '30s' };

  // Weighted probabilistic distribution [0, 99]
  const roll = Math.floor(Math.random() * 100);

  // 1. Transaction Ledger Reads (40% Weight)
  if (roll < 40) {
    if (isAuthEnabled) {
      group('Read Transactions', () => {
        const limits = [10, 20, 50];
        const limit = limits[Math.floor(Math.random() * limits.length)];
        const url = `${BASE_URL}/api/v1/transactions?limit=${limit}`;

        const res = http.get(url, {
          ...authParams,
          tags: { name: 'get_transactions' },
        });
        transactionDuration.add(res.timings.duration);
        verifyResponse(res, 200, 'GET /transactions');
      });
    } else {
      const res = http.get(`${BASE_URL}/health`, { ...DEFAULT_PARAMS, tags: { name: 'health_check' } });
      healthDuration.add(res.timings.duration);
      verifyResponse(res, 200, 'GET /health', ['status']);
    }
  }

  // 2. Financial Analytics Summary (25% Weight)
  else if (roll < 65) {
    if (isAuthEnabled) {
      group('Financial Summary', () => {
        const currentMonth = formatMonth(new Date());
        const url = `${BASE_URL}/api/v1/summary?month=${currentMonth}`;

        const res = http.get(url, {
          ...authParams,
          tags: { name: 'get_summary' },
        });
        summaryDuration.add(res.timings.duration);
        verifyResponse(res, 200, 'GET /summary');
      });
    } else {
      const res = http.get(`${BASE_URL}/api/v1/catalogue/categories`, {
        ...DEFAULT_PARAMS,
        tags: { name: 'catalogue_categories' },
      });
      catalogueDuration.add(res.timings.duration);
      verifyResponse(res, 200, 'GET /catalogue/categories');
    }
  }

  // 3. Catalog Reference Data (15% Weight)
  else if (roll < 80) {
    group('Catalog Lookups', () => {
      const endpoints = [
        { path: '/api/v1/catalogue/categories', tag: 'catalogue_categories' },
        { path: '/api/v1/catalogue/merchants', tag: 'catalogue_merchants' },
        { path: '/api/v1/catalogue/budget-templates', tag: 'catalogue_budget_templates' },
      ];
      const selected = endpoints[Math.floor(Math.random() * endpoints.length)];

      const res = http.get(`${BASE_URL}${selected.path}`, {
        ...DEFAULT_PARAMS,
        tags: { name: selected.tag },
      });
      catalogueDuration.add(res.timings.duration);
      verifyResponse(res, 200, `GET ${selected.path}`);
    });
  }

  // 4. Transaction Writes with Immediate Cleanup (10% Weight)
  else if (roll < 90) {
    if (isAuthEnabled) {
      group('Create & Cleanup Transaction', () => {
        const payload = generateTransaction(__VU);
        const createRes = http.post(`${BASE_URL}/api/v1/transactions`, JSON.stringify(payload), {
          ...authParams,
          tags: { name: 'create_transaction' },
        });
        const created = verifyResponse(createRes, 201, 'POST /transactions', ['id']);

        if (created) {
          try {
            const body = JSON.parse(createRes.body);
            if (body.id) {
              const delRes = http.del(`${BASE_URL}/api/v1/transactions/${body.id}`, null, {
                ...authParams,
                tags: { name: 'delete_transaction' },
              });
              verifyResponse(delRes, 200, 'DELETE /transactions/:id');
            }
          } catch (_) {}
        }
      });
    } else {
      const res = http.get(`${BASE_URL}/`, { ...DEFAULT_PARAMS, tags: { name: 'root_check' } });
      verifyResponse(res, 200, 'GET /', ['status']);
    }
  }

  // 5. Budgets & Goals (5% Weight)
  else if (roll < 95) {
    if (isAuthEnabled) {
      group('Budgets and Goals', () => {
        const target = Math.random() > 0.5 ? '/api/v1/budgets' : '/api/v1/goals';
        const res = http.get(`${BASE_URL}${target}`, {
          ...authParams,
          tags: { name: target === '/api/v1/budgets' ? 'get_budgets' : 'get_goals' },
        });
        verifyResponse(res, 200, `GET ${target}`);
      });
    } else {
      const res = http.get(`${BASE_URL}/health`, { ...DEFAULT_PARAMS, tags: { name: 'health_check' } });
      verifyResponse(res, 200, 'GET /health', ['status']);
    }
  }

  // 6. Baseline Health & Profile (5% Weight)
  else {
    group('Health & Profile', () => {
      const healthRes = http.get(`${BASE_URL}/health`, {
        ...DEFAULT_PARAMS,
        tags: { name: 'health_check' },
      });
      healthDuration.add(healthRes.timings.duration);
      verifyResponse(healthRes, 200, 'GET /health', ['status']);

      if (isAuthEnabled) {
        const meRes = http.get(`${BASE_URL}/api/v1/auth/me`, {
          ...authParams,
          tags: { name: 'auth_me' },
        });
        verifyResponse(meRes, 200, 'GET /auth/me', ['id', 'email']);
      }
    });
  }

  // Consistent pacing: 0.5s - 1.2s sleep between actions
  sleep(0.5 + Math.random() * 0.7);
}
