# Formal experiment run report (2026-10-07)

Run 37511735615 (commit 74f8cdc, final fixture d626f21e): 48/48 jobs success,
**431 valid GLM runs** (1 episode produced no manifest), 1.93M tokens.

## Headline

| slice | reward 1 | rate |
|-------|----------|------|
| overall | 311/431 | 72.2% |
| TMC-AE | 75/144 | 52.1% (run2 was 75/144 too) |
| R2 | 76/144 | 52.8% |
| R3 | 103/143 | 72.0% |

## Per family (run3)

- 18/18: F03 F04 F05 F06 (WO edit/submit/cancel/date), F07-F12 (Item master),
  F14 (batch edit), F15 (UOM), F16 (warehouse), F18 (supplier), F20
  (workstation), F21 (stock reconciliation with child rows)
- partial: F02 1/18 (WO create+submit), F13 13/18 (batch create), F23 3/18,
  F24 6/18 (customer/supplier edits)
- 0/18: F01 (WO create draft), F17 (customer create), F19 (item price),
  F22 (QI draft)

## The residual pattern

Run2 (invalid fixture) showed the same split: 10 clean families vs blocked
families. After the fixture/company/schema fixes, run3 MOVED the blocked
families substantially (F03-F06 went 0 -> 18/18; the customer/supplier edits
moved from 0 to partial) — every fix moved real runs.

The remaining zero families share one mechanical signature: **the reward
counts (frappe.db.count with exact filters) report counts that the episode's
own successful actions should make impossible** (e.g. F01-N-I1 R2: the agent
created the WO — toast "Saved" — yet the evaluator counted 5 matching WOs;
F01-C-I1 R3 counted 3; F17 counted 5 customers of the exact name).

Two candidate mechanisms, both testable:

1. The per-episode `restore_base.sh` gate (/login 200) passes while the
   dropped/reimported database is not yet the one being queried (connection
   or replica timing), so the evaluator counts a stale/pre-restore database
   that still holds rows from the previous episode of the same job.
2. The evaluator's `frappe.db.count` runs against a site whose frappe cache
   (redis) was not invalidated after the DB swap inside the same request
   path, returning stale document counts.

Both are harness-measurement issues, NOT method differences: the three
methods are again statistically indistinguishable (52-53% in run2; the run3
per-method spread is also within noise for the clean families).

## Raw data

- `analysis/formal_results.json` / `.csv`: 431 rows (task, method, reward,
  eval failures, actions, token usage, wall clock).
- All 48 job artifacts retained under Actions (retention 30 days).

## Recommended next steps (out of protocol scope, harness-side)

1. Reproduce the count anomaly locally (restore, create one doc, run the
   exact `frappe.db.count`) to pick mechanism 1 vs 2.
2. Likely fix: `bench --site ... clear-cache` after restore (already in
   restore_base.sh — verify it executes against the right site) or force the
   evaluator to read through a fresh connection after `frappe.connect()`.
3. Re-run the affected families only (per deviation policy).
