/**
 * ============================================================================
 * ARTHA AI — k6 Authentication Helpers
 * ============================================================================
 * 
 * Purpose:
 * Encapsulates authentication handling, Bearer token header construction,
 * token discovery, and programmatic login logic for load testing scenarios.
 * 
 * Key Features:
 * - getAuthHeaders(token)     : Generates HTTP headers with Bearer Authorization
 * - hasAuthToken(token)       : Boolean check to selectively run authenticated flows
 * - loginUser(email, pass)    : Performs API login to obtain a fresh JWT token
 * - resolveToken(baseUrl)     : Automatically determines the best token source
 *                               (Priority: AUTH_TOKEN env -> test user login -> empty)
 * ============================================================================
 */


import http from 'k6/http';
import { BASE_URL, AUTH_TOKEN } from '../config.js';

/**
 * Returns Bearer Authorization headers with JSON content type.
 */
export function getAuthHeaders(token = AUTH_TOKEN) {
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Checks whether an auth token is currently provided.
 */
export function hasAuthToken(token = AUTH_TOKEN) {
  return Boolean(token && token.trim().length > 0);
}

/**
 * Programmatically log in with credentials to acquire a fresh JWT token.
 * Typically called once inside setup() to avoid rate limits during iterations.
 */
export function loginUser(email, password, baseUrl = BASE_URL) {
  const url = `${baseUrl}/api/v1/auth/login`;
  const payload = JSON.stringify({ email, password });
  const params = {
    headers: { 'Content-Type': 'application/json' },
    tags: { name: 'auth_login' },
  };

  const res = http.post(url, payload, params);
  if (res.status === 200) {
    try {
      const body = JSON.parse(res.body);
      return body.access_token || null;
    } catch (_) {
      return null;
    }
  }
  return null;
}

/**
 * Resolves the authentication token to use for a test run.
 * Priority:
 * 1. Explicit AUTH_TOKEN environment variable
 * 2. TEST_USER_EMAIL + TEST_USER_PASSWORD login
 * 3. Returns empty string (unauthenticated fallback)
 */
export function resolveToken(baseUrl = BASE_URL) {
  if (hasAuthToken(AUTH_TOKEN)) {
    return AUTH_TOKEN;
  }

  const testEmail = __ENV.TEST_USER_EMAIL;
  const testPassword = __ENV.TEST_USER_PASSWORD;
  if (testEmail && testPassword) {
    const token = loginUser(testEmail, testPassword, baseUrl);
    if (token) {
      return token;
    }
  }

  return '';
}
