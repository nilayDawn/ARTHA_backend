-- ============================================================================
-- ARTHA AI — Production Database Performance Indexes
-- Run this in the Supabase Cloud SQL Editor to accelerate queries
-- ============================================================================

-- 1. Accelerate transaction date-range queries & chronologically sorted lists
-- Endpoints: GET /api/v1/transactions, GET /api/v1/summary
CREATE INDEX IF NOT EXISTS idx_transactions_user_date 
ON public.transactions (user_id, date DESC);

-- 2. Accelerate category filtering (Food, Utilities, Shopping, Income, etc.)
-- Endpoints: GET /api/v1/transactions?category=...
CREATE INDEX IF NOT EXISTS idx_transactions_user_category 
ON public.transactions (user_id, category);

-- 3. Accelerate search by merchant name
-- Endpoint: GET /api/v1/transactions?search=...
CREATE INDEX IF NOT EXISTS idx_transactions_user_merchant 
ON public.transactions (user_id, merchant);

-- 4. Accelerate monthly budget lookups
-- Endpoint: GET /api/v1/budgets?month=YYYY-MM
CREATE INDEX IF NOT EXISTS idx_budgets_user_month 
ON public.budgets (user_id, month);

-- 5. Accelerate active financial goals lookup
-- Endpoint: GET /api/v1/goals
CREATE INDEX IF NOT EXISTS idx_goals_user 
ON public.goals (user_id);

-- 6. Accelerate document lookups by user
-- Endpoint: GET /api/v1/documents
CREATE INDEX IF NOT EXISTS idx_documents_user 
ON public.documents (user_id);
