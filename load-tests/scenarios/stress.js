/**
 * ============================================================================
 * ARTHA AI — k6 Stress Test Scenario
 * ============================================================================
 * 
 * Purpose:
 * Gradually pushes concurrency beyond normal operating limits (up to 50 VUs)
 * to locate the latency degradation inflection point, observe connection pool
 * pressure, and determine system recovery characteristics.
 * 
 * Staged Concurrency Profile (Stepped Escalation):
 * - Stage 1 : 0 -> 10 VUs over 20s   (Baseline warm-up)
 * - Stage 2 : 10 -> 25 VUs over 30s  (Moderate stress — 2.5x normal traffic)
 * - Stage 3 : Hold 25 VUs for 1m00s  (Evaluate stability at 25 VUs)
 * - Stage 4 : 25 -> 50 VUs over 30s  (Heavy stress — 5x normal traffic)
 * - Stage 5 : Hold 50 VUs for 1m00s  (Evaluate saturation and bottleneck behavior)
 * - Stage 6 : 50 -> 0 VUs over 20s   (Ramp down & recovery measurement)
 * Total Duration: ~3 minutes 40 seconds
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
 * - BASE_URL         : Target API host (default: "http://localhost:8000")
 * - AUTH_TOKEN       : Bearer JWT token for authenticated operations
 * - STRESS_PEAK_VUS  : Maximum peak concurrency (default: 50)
 * 
 * Execution:
 *   AUTH_TOKEN="<token>" k6 run scenarios/stress.js
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

const PEAK_VUS = parseInt(__ENV.STRESS_PEAK_VUS || '50', 10);
const MID_VUS = Math.floor(PEAK_VUS / 2);

export const options = {
  stages: [
    { duration: '20s', target: 10 },              // Warm up to baseline
    { duration: '30s', target: MID_VUS },          // Step 1: Ramp to 25 VUs
    { duration: '1m00s', target: MID_VUS },        // Sustain 25 VUs
    { duration: '30s', target: PEAK_VUS },         // Step 2: Ramp to 50 VUs
    { duration: '1m00s', target: PEAK_VUS },       // Sustain 50 VUs
    { duration: '20s', target: 0 },                // Ramp down and observe recovery
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'],                       // Flag if error rate exceeds 5%
    http_req_duration: ['p(90)<1800', 'p(95)<3000'],       // Stress SLA indicators
    checks: ['rate>0.95'],                                // Overall check pass rate > 95%
  },
};

export const handleSummary = createSummaryHandler('stress');

export function setup() {
  const token = resolveToken(BASE_URL);
  return { token };
}

export default function (data) {
  const token = data?.token || '';
  const isAuthEnabled = hasAuthToken(token);
  const authHeaders = isAuthEnabled ? getAuthHeaders(token) : DEFAULT_PARAMS.headers;
  const authParams = { headers: authHeaders, timeout: '30s' };

  // Weighted random selection [0, 99]
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

  // 3. Catalog & Reference Data (15% Weight)
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

  // Dynamic user pacing under stress (0.3s - 1.0s)
  sleep(0.3 + Math.random() * 0.7);
}
