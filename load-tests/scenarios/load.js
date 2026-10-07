/**
 * ============================================================================
 * ARTHA AI — k6 Normal Load Test Scenario
 * ============================================================================
 * 
 * Purpose:
 * Simulates expected normal application traffic under production-like conditions.
 * Uses a staged ramp (ramp-up, steady state, ramp-down) and realistic probabilistic
 * endpoint weighting to emulate natural user activity.
 * 
 * Workload Distribution:
 * - 40% : Transaction Ledger Reads  (GET /api/v1/transactions with filters)
 * - 25% : Financial Analytics       (GET /api/v1/summary with month params)
 * - 15% : Catalog Reference Data    (GET /api/v1/catalogue/*)
 * - 10% : Transaction Writes        (POST /transactions with immediate cleanup)
 * -  5% : Budgets & Goals           (GET /budgets, GET /goals)
 * -  5% : Health & User Profile     (GET /health, GET /auth/me)
 * 
 * Staged Concurrency Profile:
 * - Stage 1 : 0 -> 10 VUs over 30s   (Ramp up)
 * - Stage 2 : Hold 10 VUs for 1m30s  (Steady load)
 * - Stage 3 : 10 -> 0 VUs over 20s   (Ramp down)
 * Total Duration: ~2 minutes 20 seconds
 * 
 * Environment Variables Supported:
 * - BASE_URL      : Target API host (default: "http://localhost:8000")
 * - AUTH_TOKEN    : Bearer JWT token for authenticated operations
 * - TARGET_VUS    : Peak steady VUs (default: 10)
 * 
 * Execution:
 *   AUTH_TOKEN="<token>" k6 run scenarios/load.js
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

const PEAK_VUS = parseInt(__ENV.TARGET_VUS || '10', 10);

export const options = {
  stages: [
    { duration: '30s', target: PEAK_VUS },        // Ramp up
    { duration: '1m30s', target: PEAK_VUS },      // Steady state
    { duration: '20s', target: 0 },               // Ramp down
  ],
  thresholds: {
    http_req_failed: ['rate<0.02'],                       // Error rate < 2%
    http_req_duration: ['p(90)<800', 'p(95)<1200', 'p(99)<2500'], // Latency SLAs
    checks: ['rate>0.98'],                                // Assertion pass rate > 98%
  },
};

export const handleSummary = createSummaryHandler('load');

export function setup() {
  const token = resolveToken(BASE_URL);
  return { token };
}

export default function (data) {
  const token = data?.token || '';
  const isAuthEnabled = hasAuthToken(token);
  const authHeaders = isAuthEnabled ? getAuthHeaders(token) : DEFAULT_PARAMS.headers;
  const authParams = { headers: authHeaders, timeout: '30s' };

  // Generate weighted random bucket [0, 99]
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
      // Unauthenticated fallback
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

  // 4. Transaction Writes with Cleanup (10% Weight)
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

  // 5. Budgets & Goals Reads (5% Weight)
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

  // Realistic user pacing: random sleep between 0.5s and 1.5s
  sleep(0.5 + Math.random());
}
