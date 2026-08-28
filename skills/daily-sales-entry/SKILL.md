---
name: daily-sales-entry
description: Use when implementing, changing, testing, or debugging the SVR Daily Sales Entry module - its calculation chain (gas/oil consumption and amounts, expenses, credit cards, new credits, the Net Bal Hand Off summary, the Daily Summary), the 23:59 IST Last-Shift-Reading carry-forward, or the locked Sell-Rate snapshot. Covers the section 1-8 formulas and the invariants the backend engine and the renderer mirror must both hold.
---

# Daily Sales Entry

Daily Sales Entry is the system's primary data input (SDD §10). One row per pump per
shift per submitting user. Manual mode is built; OCR and Excel import converge on the
same record and are stubbed (`501`).

## Where the code is

| Concern | File |
|---|---|
| Calculation engine (authoritative) | `backend/src/svr_backend/calc/daily_sales_entry.py` |
| Shared numeric helpers (`parse_amt`, `round4`) | `backend/src/svr_backend/calc/amounts.py` |
| API (`/calc`, `/prefill`, CRUD) | `backend/src/svr_backend/api/daily_sales_entry.py` |
| Carry-forward (23:59 IST, gap-day, catch-up) | `backend/src/svr_backend/carry_forward.py` |
| Rate Master lookup (Sell vs Buy) | `backend/src/svr_backend/rates.py` |
| Renderer mirror (UX only) | `frontend/src/renderer/lib/calc-mirror.js` |
| Screen | `frontend/src/renderer/screens/daily-sales-entry/` |
| Reference mockup | `docs/01-BRD-Requirement-Gathering/daily_sales_report_branded.html` |

## Invariants

1. **Backend wins.** `calc-mirror.js` exists only to fill the gap between keystroke
   and the `/calc` response. Any formula change lands in
   `calc/daily_sales_entry.py` first; the mirror is updated to match and is never
   the source of truth (SDD §7.3, §6.4).
2. **Blank-guard.** Consumption / Amount / Closing Stock stay `None` until the
   required input is entered — never compute from an empty field defaulting to 0
   (the SDD §6.4 bug).
3. **Sell Rate, not Buy Rate**, feeds gas rows (SDD §9 row 3). The rate is snapshot
   onto the entry at create time; the client cannot override it.
4. **Carry-forward** fills `hs_last` / `ms_last` from the most recent prior entry
   with a reading (gap days skip back). Already-set `*_last` is never overwritten.
5. Every write goes RBAC-check → recompute → persist → `audit.record_write`.
   Sales edits only its own submission; delete is Manager/Owner only.

## Formulas

See `references/formula-register.md` for the section 1–8 register (extracted from
SDD §9) and the worked example the tests pin.

## Verify

```
python skills/daily-sales-entry/scripts/verify_calc.py     # worked example
cd backend && python -m pytest tests/test_calc_daily_sales_entry.py tests/test_daily_sales_entry_api.py tests/test_carry_forward.py
cd frontend && npx playwright test daily-sales-entry
```
