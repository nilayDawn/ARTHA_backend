/**
 * ============================================================================
 * ARTHA AI — k6 Breakpoint / Capacity Test Scenario
 * ============================================================================
 * 
 * Purpose:
 * Determines the approximate maximum sustainable capacity of the API by
 * systematically stepping concurrency through progressively higher plateaus
 * (15 -> 30 -> 50 -> 75 VUs).
 * 
 * Capacity & Degradation Objectives:
 * - Identify the concurrency tier where throughput plateaus (saturation point)
 * - Identify the latency knee where p95 response times scale exponentially
 * - Detect the breakpoint where error rates rise above acceptable SLAs
 * - Pinpoint the primary bottleneck tier under maximum load
 * 
 * Stepped Ramp Profile:
 * - Stage 1 : Ramp to 15 VUs over 30s
 * - Stage 2 : Hold 15 VUs for 30s       (Tier 1: 15 VUs)
 * - Stage 3 : Ramp to 30 VUs over 30s
 * - Stage 4 : Hold 30 VUs for 30s       (Tier 2: 30 VUs)
 * - Stage 5 : Ramp to 50 VUs over 30s
 * - Stage 6 : Hold 50 VUs for 30s       (Tier 3: 50 VUs)
 * - Stage 7 : Ramp to 75 VUs over 30s
 * - Stage 8 : Hold 75 VUs for 30s       (Tier 4: 75 VUs Peak Probe)
 * - Stage 9 : Ramp down to 0 VUs over 20s
 * Total Duration: ~4 minutes 30 seconds
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
 * - BASE_URL            : Target API host (default: "http://localhost:8000")
 * - AUTH_TOKEN          : Bearer JWT token for authenticated operations
 * - BREAKPOINT_MAX_VUS  : Maximum peak plateau (default: 75)
 * 
 * Execution:
 *   AUTH_TOKEN="<token>" k6 run scenarios/breakpoint.js
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

const MAX_VUS = parseInt(__ENV.BREAKPOINT_MAX_VUS || '75', 10);
const TIER_1 = Math.round(MAX_VUS * 0.20); // 15 VUs
const TIER_2 = Math.round(MAX_VUS * 0.40); // 30 VUs
const TIER_3 = Math.round(MAX_VUS * 0.67); // 50 VUs

export const options = {
  stages: [
    { duration: '30s', target: TIER_1 },          // Ramp to Tier 1 (15 VUs)
    { duration: '30s', target: TIER_1 },          // Hold Tier 1
    { duration: '30s', target: TIER_2 },          // Ramp to Tier 2 (30 VUs)
    { duration: '30s', target: TIER_2 },          // Hold Tier 2
    { duration: '30s', target: TIER_3 },          // Ramp to Tier 3 (50 VUs)
    { duration: '30s', target: TIER_3 },          // Hold Tier 3
    { duration: '30s', target: MAX_VUS },         // Ramp to Peak Tier 4 (75 VUs)
    { duration: '30s', target: MAX_VUS },         // Hold Peak Tier 4
    { duration: '20s', target: 0 },               // Controlled ramp-down
  ],
  thresholds: {
    http_req_failed: ['rate<0.15'],                       // Flag if error rate exceeds 15%
    http_req_duration: ['p(95)<4000'],                    // Flag if 95% exceeds 4s
    checks: ['rate>0.85'],                                // Overall assertion rate > 85%
  },
};

export const handleSummary = createSummaryHandler('breakpoint');

export function setup() {
  const token = resolveToken(BASE_URL);
  return { token };
}

export default function (data) {
  const token = data?.token || '';
  const isAuthEnabled = hasAuthToken(token);
  const authHeaders = isAuthEnabled ? getAuthHeaders(token) : DEFAULT_PARAMS.headers;
  const authParams = { headers: authHeaders, timeout: '30s' };

  // Weighted probabilistic selection [0, 99]
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

  // Compact pacing under capacity probe (0.2s - 0.7s)
  sleep(0.2 + Math.random() * 0.5);
}
