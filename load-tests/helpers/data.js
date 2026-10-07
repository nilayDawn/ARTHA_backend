/**
 * ============================================================================
 * ARTHA AI — Realistic Test Data Generators
 * ============================================================================
 * 
 * Purpose:
 * Generates realistic, schema-compliant, non-colliding mock payloads
 * for write tests (transactions, budgets, goals, test users).
 * 
 * Functions:
 * - generateTransaction(vuId) : Generates TransactionCreate payload with valid
 *                               merchant, realistic amount, and category
 * - generateBudget(vuId)      : Generates BudgetCreate payload with YYYY-MM month
 * - generateGoal(vuId)        : Generates GoalCreate payload with future deadline
 * - generateTestUser(vuId)    : Generates unique user signup payload with timestamp
 * - formatDate(date)          : Formats JavaScript Date into YYYY-MM-DD
 * - formatMonth(date)         : Formats JavaScript Date into YYYY-MM
 * ============================================================================
 */


const CATEGORIES = ['Food & Dining', 'Groceries', 'Utilities', 'Transportation', 'Entertainment', 'Healthcare'];
const MERCHANTS = ['Fresh Mart', 'City Metro', 'Blue Cafe', 'Power Corp', 'Corner Pharmacy', 'Quick Fuel'];

/**
 * Random element from array
 */
function randomChoice(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

/**
 * Formats a Date object to YYYY-MM-DD
 */
export function formatDate(d = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/**
 * Formats a Date object to YYYY-MM
 */
export function formatMonth(d = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}`;
}

/**
 * Generates a valid TransactionCreate payload
 */
export function generateTransaction(vuId = 0) {
  const now = new Date();
  const amount = parseFloat((10 + Math.random() * 490).toFixed(2));
  return {
    amount: amount,
    merchant: `${randomChoice(MERCHANTS)} (k6-${vuId})`,
    category: randomChoice(CATEGORIES),
    date: formatDate(now),
    source: 'load_test',
  };
}

/**
 * Generates a valid BudgetCreate payload
 */
export function generateBudget(vuId = 0) {
  const now = new Date();
  return {
    category: `${randomChoice(CATEGORIES)}_${vuId}_${Date.now() % 10000}`,
    monthly_limit: parseFloat((5000 + Math.random() * 20000).toFixed(2)),
    month: formatMonth(now),
  };
}

/**
 * Generates a valid GoalCreate payload
 */
export function generateGoal(vuId = 0) {
  const future = new Date();
  future.setMonth(future.getMonth() + 6);
  return {
    goal_name: `Goal_${vuId}_${Date.now() % 10000}`,
    target_amount: parseFloat((20000 + Math.random() * 50000).toFixed(2)),
    saved_amount: parseFloat((1000 + Math.random() * 5000).toFixed(2)),
    deadline: formatDate(future),
  };
}

/**
 * Generates a unique user signup payload
 */
export function generateTestUser(vuId = 0) {
  const timestamp = Date.now();
  const randomSuffix = Math.floor(Math.random() * 10000);
  return {
    email: `loadtest_${timestamp}_${vuId}_${randomSuffix}@example.com`,
    password: `TestP@ss_${timestamp}`,
    full_name: `LoadTest User ${vuId}`,
  };
}
