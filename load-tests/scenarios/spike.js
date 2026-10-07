/**
 * ============================================================================
 * ARTHA AI — k6 Spike Test Scenario
 * ============================================================================
 * 
 * Purpose:
 * Evaluates API resiliency and recovery behavior during sudden, abrupt traffic surges.
 * Measures response-time explosion, failure spikes during the burst, and whether
 * the system returns to normal baseline performance once the spike subsides.
 * 
 * Spike Profile:
 * - Stage 1 : Low Baseline      : Hold 2 VUs for 20s   (Normal calm state)
 * - Stage 2 : Sudden Surge      : 2 -> 35 VUs in 10s   (17.5x rapid traffic surge)
 * - Stage 3 : Hold Peak Surge   : Hold 35 VUs for 30s  (Shock duration)
 * - Stage 4 : Sudden Drop       : 35 -> 2 VUs in 10s   (Immediate traffic collapse)
 * - Stage 5 : Recovery Window   : Hold 2 VUs for 30s   (Assess latency normalization)
 * - Stage 6 : Ramp Down         : 2 -> 0 VUs in 10s    (Cool down)
 * Total Duration: ~1 minute 50 seconds
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
 * - BASE_URL        : Target API host (default: "http://localhost:8000")
 * - AUTH_TOKEN      : Bearer JWT token for authenticated operations
 * - SPIKE_PEAK_VUS  : Maximum spike concurrency (default: 35)
 * 
 * Execution:
 *   AUTH_TOKEN="<token>" k6 run scenarios/spike.js
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

const PEAK_VUS = parseInt(__ENV.SPIKE_PEAK_VUS || '35', 10);

export const options = {
  stages: [
    { duration: '20s', target: 2 },               // Stage 1: Calm baseline
    { duration: '10s', target: PEAK_VUS },         // Stage 2: Sudden surge to peak
    { duration: '30s', target: PEAK_VUS },         // Stage 3: Hold peak spike
    { duration: '10s', target: 2 },               // Stage 4: Abrupt traffic plunge
    { duration: '30s', target: 2 },               // Stage 5: Recovery observation window
    { duration: '10s', target: 0 },               // Stage 6: Cool down
  ],
  thresholds: {
    http_req_failed: ['rate<0.08'],                       // Flag if error rate exceeds 8% during spike
    http_req_duration: ['p(90)<2500', 'p(95)<3500'],       // Spike latency thresholds
    checks: ['rate>0.92'],                                // Assertions pass rate > 92%
  },
};

export const handleSummary = createSummaryHandler('spike');

export function setup() {
  const token = resolveToken(BASE_URL);
  return { token };
}

export default function (data) {
  const token = data?.token || '';
  const isAuthEnabled = hasAuthToken(token);
  const authHeaders = isAuthEnabled ? getAuthHeaders(token) : DEFAULT_PARAMS.headers;
  const authParams = { headers: authHeaders, timeout: '30s' };

  // Weighted random distribution [0, 99]
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

  // Realistic user pacing between requests (0.4s - 1.0s)
  sleep(0.4 + Math.random() * 0.6);
}
