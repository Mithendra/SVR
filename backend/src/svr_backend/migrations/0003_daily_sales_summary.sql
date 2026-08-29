-- 0003_daily_sales_summary.sql - fill out the daily_sales_summary stub from 0002
-- (SDD 5.23-5.25 / 10). One row per shift_date. It binds the Office + Road
-- daily_sales_entry submissions, records the per-pump human verification, and
-- gates the (future) upload into Daily Trial Balance Section 2 until BOTH pumps
-- are verified. The combined per-line totals are derived at read time from the
-- two entries' cached `result` JSON - not stored - so they can never drift.

ALTER TABLE daily_sales_summary ADD COLUMN off_salesman       TEXT;
ALTER TABLE daily_sales_summary ADD COLUMN road_salesman      TEXT;
-- entry_mode of each submission, echoed for the verifier's context.
ALTER TABLE daily_sales_summary ADD COLUMN off_method         TEXT;
ALTER TABLE daily_sales_summary ADD COLUMN road_method        TEXT;
-- free-text detail when a pump is verified "with corrections".
ALTER TABLE daily_sales_summary ADD COLUMN off_verified_note  TEXT;
ALTER TABLE daily_sales_summary ADD COLUMN road_verified_note TEXT;
ALTER TABLE daily_sales_summary ADD COLUMN status             TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'verified', 'uploaded'));
ALTER TABLE daily_sales_summary ADD COLUMN prepared_by        TEXT;
ALTER TABLE daily_sales_summary ADD COLUMN verified_by        TEXT;
ALTER TABLE daily_sales_summary ADD COLUMN uploaded_by        TEXT;
ALTER TABLE daily_sales_summary ADD COLUMN uploaded_at        TEXT;

CREATE INDEX idx_dss_status ON daily_sales_summary (status);
