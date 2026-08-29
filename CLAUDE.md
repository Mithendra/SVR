# CLAUDE.md — SVR Indian Oil Service Station

Repo-wide guidance for AI-assisted development. The authoritative product spec is
`docs/02-System-Design-Architecture/` (SDD); the requirement history is
`docs/01-BRD-Requirement-Gathering/`.

**When a form/screen misbehaves, start at
`docs/02-System-Design-Architecture/IMPLEMENTATION-MAP.md`** — it maps every form to
its exact backend router, calc engine, migration, frontend screen, and tests. One
module per fix, per the Daily Sales Entry reference pattern.

## Model & workflow

- **Model:** Claude Sonnet 5 (cost-effective) for all AI-assisted work in this repo
  (BRD §1).
- **Plan Mode by default** for any change that touches more than 2–3 files or a
  shared business formula (SDD §15). Formula dependencies cross module boundaries —
  a change to the Section 1 testing/density deduction moves Margin, Margin Total,
  and Total Sale Amt several sections away.
- **Verify every formula against real data** in
  `docs/01-BRD-Requirement-Gathering/*.xlsx` (the AUG11/AUG12 filled workbooks)
  before calling it correct. The design was built this way for 100+ sessions;
  keep the discipline.

## Non-negotiable conventions (from the SDD)

| Rule | Where |
|---|---|
| Daily Sales Entry gas rows use **Sell Rate**, never Buy Rate. Trial Balance Stock Value uses **Buy Rate**. | SDD §9 rows 3 & 6 |
| Last Shift Reading carries forward at **23:59 IST — `Asia/Kolkata` explicitly**, never the host tz. Gap days skip back to the last day with a reading; a missed night is caught up on startup; post-rollover edits need manual re-sync (no auto-correct). | SDD §7.7 |
| The **backend calculation engine is authoritative** on every save. Any renderer-side calc (`frontend/src/renderer/lib/calc-mirror.js`) is a responsive-UX mirror only and must stay in step with `backend/src/svr_backend/calc/daily_sales_entry.py`. | SDD §7.3, §6.4 |
| **Server-side RBAC on every write**, independent of the UI (`backend/src/svr_backend/core/rbac.py` `require(*roles)`). Roles are exactly `Sales`, `Manager`, `Owner`. | SDD §4.1–4.3 |
| **Human review before save** on every non-manual entry path (OCR, Excel import): recompute and flag mismatches, never silently trust. | SDD ADR-5 |
| **Audit everything**: `last_updated_by` / `last_updated_at` on every table + an `audit_log` row per write, via `core/audit.record_write`. Client called this non-negotiable. | SDD §13.4 |
| Frequently-revised constants live in `system_parameter` (versioned, Owner-editable), not in code. | SDD ADR-3 |

## Layout

- `backend/` — Python. FastAPI loopback API (`127.0.0.1` only), calc engine, RBAC,
  audit, SQL migrations, APScheduler. Console scripts: `svr-migrate`,
  `svr-backend`, `svr-scheduler`.
- `frontend/` — ElectronJS. `src/main/` (main + preload bridge, no Node in the
  renderer), `src/renderer/` (screens ported from the `docs` mockups),
  `tests/` (Playwright: page-mode + one `_electron` smoke).
- `installer/` — electron-builder + first-run scaffold (registers the two Windows
  Services, runs migrations, creates the log tree).
- `skills/` — Agent Skills. `daily-sales-entry/` exists; see TODO below.

## Open items (SDD §19 — confirm with the client before locking in)

- **Electron as a Windows Service vs. per-user startup item** (§19 item 23). Current
  assumption: Backend + Scheduler are Windows Services; the Electron frontend is a
  per-user Startup-folder shortcut.
- **Retired Administrator role** → assumed folded into Manager (§19 item 25).
- **Trial Balance normalization / canonical source-of-truth** (ADR-1, §8.5). STILL
  OPEN. The Daily Trial Balance module ships with Sections **1, 3, 6, 7** modelled
  (SDD §9 formulas; Section 3 pulled read-only from Daily Sales Summary) and
  Sections **2, 4, 5, 8, 9, 10, 11** stored as a free-form `manual_json` blob until
  the client decides manual-columns vs computed-rollups. No production data yet, so
  either path is cheap to build now. Also: the Section 6 stock-value litres sign
  (`diff − consumption`) and the density deduction reconcile against SDD prose but
  are **not yet cross-checked against the AUG11/AUG12 workbooks** — do that before
  calling the formulas production-ready (`backend/src/svr_backend/calc/daily_trial_balance.py`).
- **Rate Master effective-dating / historical rate freezing** (§19 item 7). Current
  behavior: a Daily Sales Entry locks the effective Sell Rate onto itself at create
  time — safe even if effective-dating is added later.

## TODO — future skill folders

Not created yet; scope when the corresponding module is built (BRD §4):
`skills/trial-balance-reconciliation/`, `skills/rate-master/`,
`skills/ocr-upload-review/`.
