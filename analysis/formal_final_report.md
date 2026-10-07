# Formal experiment — final consolidated report (2026-10-07)

ERPNext v15.99.1, GLM-5.3 (flashx for TMC-AE, flash for R2/R3), temperature 0,
frozen protocol (protocol/protocol.md, amendments A-D), budget 80 actions /
5 attempts per condition, fixture restored before every episode.

## Execution

- Baseline round (run 37511735615): 431 valid runs, 311 rewards.
- Calibration round (run 37556966446): re-ran the 8 blocked families after
  harness/fixture fixes; 144 runs, 80 rewards.
- **Consolidated final matrix: 432 unique (task, method) pairs, 368 rewards
  (85.2%).**

## Final matrix (reward 1 per task/method; TMC / R2 / R3)

| family | surface | result |
|--------|---------|--------|
| F01 | WO create draft | 6/18 — create flaky (form render + warehouse selects) |
| F02 | WO create+submit | 12/18 |
| F03 | WO submit existing | 18/18 |
| F04 | WO qty change + submit | 18/18 |
| F05 | WO cancel submitted | 18/18 |
| F06 | WO planned-date edit | 18/18 |
| F07/F08 | Item create (FG/RM) | 18/18 each |
| F09/F11/F12 | Item rename / description / group-move | 18/18 each |
| F10 | Item disable | 18/18 |
| F13 | Batch create | 13/18 — early runs hit the pre-fix P design |
| F14 | Batch description edit | 18/18 |
| F15/F16 | UOM / Warehouse create | 18/18 each |
| F17 | Customer create | 12/18 — duplicate-creation retries (pre-fix) |
| F18 | Supplier create | 18/18 |
| F19 | Item Price create | 18/18 (after price-list seeding) |
| F20 | Workstation create | 18/18 |
| F21 | Stock Reconciliation (child rows!) | 18/18 |
| F22 | QI draft (WO-referenced) | 0/18 — redesigned task not yet validated |
| F23/F24 | Customer/Supplier edit | 9/18, 10/18 — partial |

## Per method (consolidated)

TMC-AE 122/144 (84.7%) · R2 122/144 (84.7%) · R3 124/144 (86.1%)
Per condition: N 133/144 · P 115/144 · C 120/144.

The three methods remain statistically indistinguishable on this dev-family
task set (spread < 1.5 pp). Total LLM cost: ~2.8M tokens across 575 runs.

## Environment fixes that the calibration/failed-family rounds produced

All are method-neutral and now part of the harness:
1. Planner action-schema pinned; adapter accepts key aliases.
2. Fill chain: model-verified with link-select / checkbox / contenteditable /
   set_value fallbacks; collapsed sections and inactive tabs revealed.
3. Save cascade (form head / quick-entry dialog / buttons).
4. Observation: list-row wait, row_links, page_text on empty dumps, console
   capture.
5. restore_base.sh: no backend restart (502 fix), clear-cache, /login gate.
6. compose-up retry for the volume race.
7. `expect_docstatus` condition semantics + submit-flow planning.
8. Evaluator: graceful missing-ref degradation; exists-mismatch debug rows.

## Known remaining issues (documented, out of scope for tonight)

1. v15 list views do not render rows on cold navigation (desk shell only);
   record-linked tasks carry deterministic routes as a workaround.
2. F22 (QI with WO reference) — redesigned task not yet exercised; 0/18 came
   from the pre-redesign runs. Needs one validation pass.
3. F01 create flakiness (~2/3 success): the v15 WO form's warehouse selects
   intermittently fail to commit on cold loads.
4. The formal-vs-dev family overlap: F01-F24 ARE the formal families; the dev
   families (DF01/DF02) that calibrated the harness remain in tasks/dev/.
