# Gate 3 pilot results (2026-10-05/06) — baseline + calibration

ERPNext v15.99.1, GLM-5.3 (flashx for TMC, flash for R2/R3), temperature 0,
serial runs on `erpnext-devtest.yml`, one restored base fixture per run.

36 paired baseline runs (2 dev families x N/P/C x 2 instances x 3 methods)
+ 15 calibration runs after harness/fixture fixes (only P/C re-run; N results
stand — the calibration did not change create flows).

Reward = 1 only if every ORM-evaluated reward condition holds
(exists/fields/not_exists, docstatus, counts).

## Calibrated matrix (reward; baseline reward in parentheses where it changed)

| task      | TMC       | R2        | R3        |
|-----------|-----------|-----------|-----------|
| DF01-N-I1 | 1         | 1         | 1         |
| DF01-N-I2 | 1         | 1         | 1         |
| DF01-P-I1 | 1 (was 0) | 1 (was 0) | 1 (was 0) |
| DF01-P-I2 | 1 (was 0) | 1 (was 0) | 1 (was 0) |
| DF01-C-I1 | 1 (was 0) | 1 (was 0) | 1 (was 0) |
| DF01-C-I2 | 1 (was 0) | 1 (was 0) | 1 (was 0) |
| DF02-N-I1 | 1         | 1         | 1         |
| DF02-N-I2 | 1         | 1         | 1         |
| DF02-P-I1 | 1 (was 0) | 1 (was 0) | 1 (was 0) |
| DF02-P-I2 | 1 (was 0) | 1 (was 0) | 1 (was 0) |
| DF02-C-I1 | 1 (was 0) | 1 (was 0) | 1 (was 0) |
| DF02-C-I2 | 1 (was 0) | 1 (was 0) | 1 (was 0) |

Per method after calibration: TMC 12/12, R2 12/12, R3 12/12.

## What the baseline → calibration delta was (and was not)

The baseline 0s on P/C were environment and harness gaps, not method
differences. Fixes applied before the calibration round (equal for all
methods):

1. Action-schema: the planner prompt now pins exact per-type key names and the
   adapter accepts common aliases (GLM emitted navigate/click with different
   keys, which the adapter silently rejected).
2. Submit semantics: conditions can declare `expect_docstatus`; the readback
   returns docstatus and the episode keeps working until the document is
   actually submitted (baseline stopped at the first field-confirmed save).
3. Work Order submit prerequisites: BOM items carry `from_warehouse` and items
   carry `item_defaults.default_warehouse` — without them the server rejects
   every submit ("Source Warehouse" mandatory in Required Items).
4. Fixture pre-state: draft WOs for all P/C tasks (C/D/E/F rows) — two of the
   four were missing from the original fixture.
5. UI affordances: collapsed-section expansion, inactive-tab activation,
   checkbox fill, rich-text editor fallback (contenteditable / set_value),
   Save-button cascade, list-row wait before observations, and 5 attempts
   (was 3).
6. Known remaining environment limitation: v15 list views do not render rows
   on cold navigation in this headless setup (desk shell renders, list body
   does not; no console errors; count API responds). P/C tasks therefore carry
   deterministic record routes, mirroring a user following a link from a
   message. Formal-run tasks should be designed with this in mind.

## Conclusion for protocol freeze

With calibrated affordances all three methods solve every dev condition; the
pilot's job (expose environment/measurement defects before freezing) is done.
The formal 432-run experiment can proceed on the frozen protocol; method
separation must come from the formal task set's difficulty spread, not from
the dev families.
