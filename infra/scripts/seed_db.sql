-- ===========================================================
-- Fraud Detection System - Production Database Seed Script
-- -----------------------------------------------------------
-- Seeds reference data for:
--   • Blacklist Providers
--   • Policy Guidance Entries
--   • Sample Claims for Testing
--
-- Usage:
--   psql "$DB_URL" -f infra/scripts/seed_db.sql -v ON_ERROR_STOP=1
--
-- Assumes Alembic migrations or db.py have created:
--   - blacklist (provider TEXT PRIMARY KEY)
--   - policies (query TEXT PRIMARY KEY)
--   - claims (claimant_id TEXT, amount NUMERIC, etc.)
--
-- Safe for multiple runs (idempotent via ON CONFLICT).
-- ===========================================================

BEGIN;

-- ===========================================================
-- 🏥 BLACKLISTED PROVIDERS
-- ===========================================================
INSERT INTO blacklist (provider, reason, added_at)
VALUES
  ('shady_clinic', 'Historical overbilling and fraud reports', CURRENT_TIMESTAMP),
  ('fake_vendor', 'Reported for issuing fictitious invoices', CURRENT_TIMESTAMP),
  ('ghost_hospital', 'Non-existent provider; flagged by audit', CURRENT_TIMESTAMP),
  ('quick_cash_medical', 'Pattern of high-volume, low-value claims', CURRENT_TIMESTAMP)
ON CONFLICT (provider) DO NOTHING;


-- ===========================================================
-- 📜 POLICY / GUIDANCE RESPONSES
-- ===========================================================
INSERT INTO policies (query, response, required_docs, source, created_at)
VALUES
  (
    'What documents are needed for a claim?',
    'For standard claims, submit: Government-issued ID, original invoice/receipt, medical/incident report, and witness statements if applicable. Digital copies accepted.',
    ARRAY['Government ID', 'Original Invoice', 'Medical Report', 'Witness Statement'],
    'Claims Policy v2.0',
    CURRENT_TIMESTAMP
  ),
  (
    'Why was my claim rejected?',
    'Claims may be rejected if fraud probability >70% or if critical alarms (e.g., blacklist hit) are triggered. You may appeal within 30 days with additional proof.',
    ARRAY['Appeal Form', 'Additional Proof', 'Explanation Letter'],
    'Fraud Policy v1.5',
    CURRENT_TIMESTAMP
  ),
  (
    'How long does processing take?',
    'Standard claims: 5–7 business days. High-risk reviews: 10–14 days. Track progress in your online portal.',
    ARRAY['Tracking ID'],
    'Processing Policy v1.0',
    CURRENT_TIMESTAMP
  ),
  (
    'What if I have a new bank account?',
    'New banks require verification (ID + bank statement). Processing may take up to 3 additional days.',
    ARRAY['Bank Statement', 'ID'],
    'Payout Policy v1.0',
    CURRENT_TIMESTAMP
  )
ON CONFLICT (query) DO UPDATE
  SET response = EXCLUDED.response,
      required_docs = EXCLUDED.required_docs,
      source = EXCLUDED.source;


-- ===========================================================
-- 💰 SAMPLE CLAIMS (TESTING DATA)
-- ===========================================================
INSERT INTO claims (
  claimant_id,
  amount,
  report_delay_days,
  provider,
  notes,
  location,
  timestamp,
  is_new_bank,
  fraud_probability,
  decision,
  alarms,
  created_at
)
VALUES
  -- ✅ Legitimate claim
  (
    'legit_user_1',
    2500.00,
    2,
    'Trusted Clinic',
    'Minor fender bender, no injuries.',
    'New York, NY',
    '2023-10-01 10:00:00',
    FALSE,
    15.0,
    'Approve',
    '[]',
    CURRENT_TIMESTAMP
  ),

  -- ⚠️ Medium risk (late reporting)
  (
    'medium_user_1',
    7500.00,
    8,
    'Out-of-Network Hospital',
    'Slip and fall at work.',
    'Los Angeles, CA',
    '2023-09-20 14:30:00',
    FALSE,
    45.0,
    'Review',
    '[{"type": "late_reporting", "description": "Reported 8 days late", "severity": "medium"}]',
    CURRENT_TIMESTAMP
  ),

  -- 🚨 High risk (fraudulent)
  (
    'fraud_user_1',
    20000.00,
    15,
    'shady_clinic',
    'Staged accident for quick cash, exaggerated whiplash symptoms.',
    'Far Away, TX',
    '2023-09-15 03:15:00',
    TRUE,
    85.0,
    'Reject',
    '[{"type": "high_amount", "description": "Exceeds $10000", "severity": "high"},
      {"type": "blacklist_hit", "description": "Shady clinic", "severity": "high"},
      {"type": "suspicious_keywords", "description": "Staged, quick cash", "severity": "high"}]',
    CURRENT_TIMESTAMP
  ),

  -- 🔁 Repeat claimant
  (
    'repeat_user_1',
    6000.00,
    3,
    'Repeat Provider',
    'Multiple claims from same claimant within 12 months.',
    'New York, NY',
    '2023-10-05 11:00:00',
    FALSE,
    60.0,
    'Review',
    '[{"type": "repeat_claimant", "description": "3 claims in 12 months", "severity": "medium"}]',
    CURRENT_TIMESTAMP
  )
ON CONFLICT DO NOTHING;


-- ===========================================================
-- 🧩 PERFORMANCE OPTIMIZATION
-- ===========================================================
CREATE INDEX IF NOT EXISTS idx_claims_claimant_id ON claims (claimant_id);
CREATE INDEX IF NOT EXISTS idx_claims_created_at ON claims (created_at);
CREATE INDEX IF NOT EXISTS idx_claims_provider ON claims (provider);

-- Vacuum/analyze to refresh planner stats
VACUUM ANALYZE claims;
VACUUM ANALYZE blacklist;
VACUUM ANALYZE policies;


-- ===========================================================
-- 📊 SUMMARY OUTPUT
-- ===========================================================
SELECT '✅ Claims inserted: ' || COUNT(*) FROM claims;
SELECT '✅ Blacklist entries: ' || COUNT(*) FROM blacklist;
SELECT '✅ Policies seeded: ' || COUNT(*) FROM policies;

COMMIT;
