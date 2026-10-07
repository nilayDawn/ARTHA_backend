/**
 * ============================================================================
 * ARTHA AI — k6 Central Load Testing Configuration
 * ============================================================================
 * 
 * Purpose:
 * Provides central configuration parameters, default thresholds, HTTP options,
 * and automated result exporters used across all load test scenarios.
 * 
 * Environment Variables Supported:
 * - BASE_URL     : Target API URL (default: "http://localhost:8000")
 * - AUTH_TOKEN   : Bearer JWT token for authenticated endpoints (default: "")
 * - RESULTS_DIR  : Destination directory for JSON test outputs (default: "results")
 * 
 * Key Exports:
 * - BASE_URL, AUTH_TOKEN, RESULTS_DIR : Resolved runtime environment constants
 * - DEFAULT_THRESHOLDS                : Initial engineering baseline SLA thresholds
 * - DEFAULT_PARAMS                    : Standard JSON headers and HTTP timeouts
 * - createSummaryHandler(scenario)    : Native k6 summary exporter saving unique
 *                                       JSON artifacts to results/ and printing
 *                                       formatted reports to stdout
 * ============================================================================
 */

export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
export const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';
export const RESULTS_DIR = __ENV.RESULTS_DIR || 'results';




// Initial Engineering Thresholds (baseline SLA targets)
export const DEFAULT_THRESHOLDS = {
  http_req_failed: ['rate<0.01'],         // < 1% HTTP failure rate
  http_req_duration: ['p(90)<400', 'p(95)<800', 'p(99)<1500'], // Latency targets
  checks: ['rate>0.99'],                  // > 99% check pass rate
};

// Common request parameters
export const DEFAULT_PARAMS = {
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'User-Agent': 'k6-load-tester/1.0',
  },
  timeout: '30s',
};

/**
 * Generates an ISO-like timestamp safe for filenames: YYYY-MM-DD-HHmmss
 */
export function getTimestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

/**
 * Creates a standardized handleSummary callback for k6 test scenarios.
 * Outputs:
 *  1. Machine-readable JSON file in RESULTS_DIR/<scenario>-<timestamp>.json
 *  2. Clean terminal summary in stdout
 */
export function createSummaryHandler(scenarioName) {
  return function handleSummary(data) {
    const timestamp = getTimestamp();
    const jsonPath = `${RESULTS_DIR}/${scenarioName}-${timestamp}.json`;
    
    // Enrich with run metadata
    const reportData = {
      metadata: {
        scenario: scenarioName,
        timestamp: new Date().toISOString(),
        baseUrl: BASE_URL,
        hasAuth: Boolean(AUTH_TOKEN),
      },
      ...data,
    };

    // Build text summary for terminal
    const metrics = data.metrics || {};
    const reqs = metrics.http_reqs ? metrics.http_reqs.values.count : 0;
    const rate = metrics.http_reqs ? (metrics.http_reqs.values.rate || 0).toFixed(2) : '0';
    const failedRate = metrics.http_req_failed ? (metrics.http_req_failed.values.rate * 100).toFixed(2) : '0';
    const avgDuration = metrics.http_req_duration ? metrics.http_req_duration.values.avg.toFixed(2) : '0';
    const p90 = metrics.http_req_duration?.values['p(90)'] ? metrics.http_req_duration.values['p(90)'].toFixed(2) : '0';
    const p95 = metrics.http_req_duration?.values['p(95)'] ? metrics.http_req_duration.values['p(95)'].toFixed(2) : '0';
    const p99 = metrics.http_req_duration?.values['p(99)'] ? metrics.http_req_duration.values['p(99)'].toFixed(2) : '0';

    const checkPass = metrics.checks ? (metrics.checks.values.rate * 100).toFixed(2) : '100';

    const terminalSummary = `
================================================================================
                    ARTHA AI API LOAD TEST RESULTS
================================================================================
Scenario:             ${scenarioName}
Timestamp:            ${reportData.metadata.timestamp}
Target URL:           ${BASE_URL}
Auth Configured:      ${reportData.metadata.hasAuth ? 'Yes (Bearer)' : 'No'}
Results Output:       ${jsonPath}
--------------------------------------------------------------------------------
Total Requests:       ${reqs} (${rate} req/s)
HTTP Failure Rate:    ${failedRate}%
Checks Passed:        ${checkPass}%
Latency (Avg):        ${avgDuration} ms
Latency (p90):        ${p90} ms
Latency (p95):        ${p95} ms
Latency (p99):        ${p99} ms
================================================================================
Raw machine-readable result saved to: ${jsonPath}
`;

    const resultFiles = {};
    resultFiles[jsonPath] = JSON.stringify(reportData, null, 2);
    resultFiles['stdout'] = terminalSummary;

    return resultFiles;
  };
}
