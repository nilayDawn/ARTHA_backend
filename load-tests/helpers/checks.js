/**
 * ============================================================================
 * ARTHA AI — k6 Reusable Checks & Metric Instruments
 * ============================================================================
 * 
 * Purpose:
 * Centralizes assertions, status code validations, JSON structure verifications,
 * and custom k6 metric instruments (Rates, Trends, Counters) across all test runs.
 * 
 * Key Instruments:
 * - appErrors           : Rate metric tracking application/HTTP errors (0 or 1)
 * - successRate         : Rate metric tracking successful operations (0 or 1)
 * - checksFailed        : Counter recording aggregate failed assertions
 * - healthDuration      : Latency trend for /health and root endpoints
 * - catalogueDuration   : Latency trend for catalogue/reference endpoints
 * - transactionDuration : Latency trend for transaction CRUD operations
 * - summaryDuration     : Latency trend for financial summary aggregation queries
 * 
 * Helper Functions:
 * - verifyResponse(res, status, name, requiredFields) :
 *     Asserts HTTP status code, verifies JSON validity, checks for required fields,
 *     and automatically records pass/fail to custom metric instruments.
 * ============================================================================
 */


import { check } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom Application-Level Metrics
export const appErrors = new Rate('app_errors');
export const successRate = new Rate('success_rate');
export const checksFailed = new Counter('checks_failed');

// Endpoint-specific Latency Trends
export const healthDuration = new Trend('health_duration', true);
export const catalogueDuration = new Trend('catalogue_duration', true);
export const transactionDuration = new Trend('transaction_duration', true);
export const summaryDuration = new Trend('summary_duration', true);

/**
 * Standard HTTP & JSON verification check.
 * 
 * @param {Response} res - k6 HTTP response
 * @param {number|number[]} expectedStatus - Expected HTTP status code(s)
 * @param {string} endpointName - Tag name for diagnostics
 * @param {string[]} requiredFields - List of top-level keys required in JSON
 * @returns {boolean} Whether all checks passed
 */
export function verifyResponse(res, expectedStatus = 200, endpointName = 'endpoint', requiredFields = []) {
  const allowedStatuses = Array.isArray(expectedStatus) ? expectedStatus : [expectedStatus];
  
  const statusOk = allowedStatuses.includes(res.status);
  
  let jsonOk = true;
  let fieldsOk = true;

  if (res.status >= 200 && res.status < 300) {
    try {
      const data = JSON.parse(res.body);
      if (requiredFields.length > 0 && typeof data === 'object' && data !== null) {
        for (const field of requiredFields) {
          if (!(field in data)) {
            fieldsOk = false;
            break;
          }
        }
      }
    } catch (_) {
      // If expected JSON response but failed parsing
      jsonOk = false;
    }
  }

  const passed = check(res, {
    [`${endpointName} status is ${allowedStatuses.join('/')}`]: () => statusOk,
    [`${endpointName} valid JSON body`]: () => jsonOk,
    [`${endpointName} has required fields`]: () => fieldsOk,
  });

  if (!passed) {
    checksFailed.add(1);
    appErrors.add(1);
    successRate.add(0);
  } else {
    appErrors.add(0);
    successRate.add(1);
  }

  return passed;
}
