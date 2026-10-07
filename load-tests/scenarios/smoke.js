/**
 * ============================================================================
 * ARTHA AI — k6 Smoke Test Scenario
 * ============================================================================
 * 
 * Purpose:
 * Validates baseline API health, schema conformity, and sanity under minimal
 * concurrency (1-2 VUs) before escalating to heavier load profiles.
 * 
 * Flow Tested:
 * 1. Health & Root Endpoints   : GET /health, GET /
 * 2. Reference & Catalog       : GET /catalogue/categories, /merchants, /budget-templates
 * 3. Authenticated Ledger      : GET /auth/me, GET /transactions, GET /summary,
 *                                GET /budgets, GET /goals
 * 4. Safe Write Lifecycle      : POST /transactions -> verify 201 -> DELETE /transactions/:id
 * 
 * Environment Variables:
 * - SMOKE_VUS      : Virtual users count (default: 2)
 * - SMOKE_DURATION : Scenario duration (default: "30s")
 * - AUTH_TOKEN     : Optional Bearer token for authenticated group
 * 
 * Execution:
 *   AUTH_TOKEN="<token>" k6 run scenarios/smoke.js
 * ============================================================================
 */


import http from 'k6/http';
import { sleep, group } from 'k6';
import { BASE_URL, DEFAULT_PARAMS, createSummaryHandler } from '../config.js';
import { getAuthHeaders, resolveToken, hasAuthToken } from '../helpers/auth.js';
import { generateTransaction } from '../helpers/data.js';
import {
  verifyResponse,
  healthDuration,
  catalogueDuration,
  transactionDuration,
  summaryDuration,
} from '../helpers/checks.js';

export const options = {
  vus: parseInt(__ENV.SMOKE_VUS || '2', 10),
  duration: __ENV.SMOKE_DURATION || '30s',
  thresholds: {
    http_req_failed: ['rate<0.01'],                    // Error rate < 1%
    http_req_duration: ['p(95)<800', 'p(99)<1500'],    // 95% of requests under 800ms
    checks: ['rate>0.99'],                             // >99% assertions pass
  },
};

export const handleSummary = createSummaryHandler('smoke');

export function setup() {
  const token = resolveToken(BASE_URL);
  return { token };
}

export default function (data) {
  const token = data?.token || '';
  const isAuthEnabled = hasAuthToken(token);

  // 1. Health & Root Control Group
  group('Health & Root Endpoints', () => {
    const healthRes = http.get(`${BASE_URL}/health`, {
      ...DEFAULT_PARAMS,
      tags: { name: 'health_check' },
    });
    healthDuration.add(healthRes.timings.duration);
    verifyResponse(healthRes, 200, 'GET /health', ['status']);

    const rootRes = http.get(`${BASE_URL}/`, {
      ...DEFAULT_PARAMS,
      tags: { name: 'root_check' },
    });
    verifyResponse(rootRes, 200, 'GET /', ['status', 'message']);
  });

  // 2. Catalogue Reference Endpoints (Unauthenticated Reads)
  group('Catalogue Endpoints', () => {
    const catRes = http.get(`${BASE_URL}/api/v1/catalogue/categories`, {
      ...DEFAULT_PARAMS,
      tags: { name: 'catalogue_categories' },
    });
    catalogueDuration.add(catRes.timings.duration);
    verifyResponse(catRes, 200, 'GET /catalogue/categories');

    const merchRes = http.get(`${BASE_URL}/api/v1/catalogue/merchants`, {
      ...DEFAULT_PARAMS,
      tags: { name: 'catalogue_merchants' },
    });
    catalogueDuration.add(merchRes.timings.duration);
    verifyResponse(merchRes, 200, 'GET /catalogue/merchants');

    const templatesRes = http.get(`${BASE_URL}/api/v1/catalogue/budget-templates`, {
      ...DEFAULT_PARAMS,
      tags: { name: 'catalogue_budget_templates' },
    });
    catalogueDuration.add(templatesRes.timings.duration);
    verifyResponse(templatesRes, 200, 'GET /catalogue/budget-templates');
  });

  // 3. Authenticated Endpoints (Executed if AUTH_TOKEN is supplied)
  if (isAuthEnabled) {
    const authHeaders = getAuthHeaders(token);
    const authParams = { headers: authHeaders, timeout: '30s' };

    group('Authenticated User & Ledger Endpoints', () => {
      // User Profile
      const meRes = http.get(`${BASE_URL}/api/v1/auth/me`, {
        ...authParams,
        tags: { name: 'auth_me' },
      });
      verifyResponse(meRes, 200, 'GET /auth/me', ['id', 'email']);

      // List Transactions
      const txRes = http.get(`${BASE_URL}/api/v1/transactions?limit=20`, {
        ...authParams,
        tags: { name: 'get_transactions' },
      });
      transactionDuration.add(txRes.timings.duration);
      verifyResponse(txRes, 200, 'GET /transactions');

      // Financial Summary
      const summaryRes = http.get(`${BASE_URL}/api/v1/summary`, {
        ...authParams,
        tags: { name: 'get_summary' },
      });
      summaryDuration.add(summaryRes.timings.duration);
      verifyResponse(summaryRes, 200, 'GET /summary');

      // Budgets & Goals
      const budgetsRes = http.get(`${BASE_URL}/api/v1/budgets`, {
        ...authParams,
        tags: { name: 'get_budgets' },
      });
      verifyResponse(budgetsRes, 200, 'GET /budgets');

      const goalsRes = http.get(`${BASE_URL}/api/v1/goals`, {
        ...authParams,
        tags: { name: 'get_goals' },
      });
      verifyResponse(goalsRes, 200, 'GET /goals');

      // Safe Lifecycle Write + Cleanup (Smoke check: create 1 transaction, verify, then delete)
      const newTx = generateTransaction(__VU);
      const createRes = http.post(`${BASE_URL}/api/v1/transactions`, JSON.stringify(newTx), {
        ...authParams,
        tags: { name: 'create_transaction' },
      });
      const createdOk = verifyResponse(createRes, 201, 'POST /transactions', ['id']);

      if (createdOk) {
        try {
          const createdBody = JSON.parse(createRes.body);
          const txId = createdBody.id;
          if (txId) {
            const delRes = http.del(`${BASE_URL}/api/v1/transactions/${txId}`, null, {
              ...authParams,
              tags: { name: 'delete_transaction' },
            });
            verifyResponse(delRes, 200, 'DELETE /transactions/:id');
          }
        } catch (_) {}
      }
    });
  }

  // Pacing: 1 second between iterations for gentle smoke traffic
  sleep(1);
}
