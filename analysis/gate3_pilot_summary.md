# Gate 3 pilot results (2026-10-05/06)

ERPNext v15.99.1, GLM-5.3 (flashx for TMC, flash for R2/R3), temperature 0,
serial runs on `erpnext-devtest.yml`, one restored base fixture per run.

36 paired runs = 2 dev families (DF01 Work Order, DF02 Item master)
x 3 conditions (N/P/C) x 2 instances x 3 methods (TMC-AE / R2 / R3).

Reward = 1 only if every ORM-evaluated reward condition holds
(exists/fields/not_exists, docstatus, counts).

## Matrix (reward)

| task      | TMC | R2 | R3 |
|-----------|-----|----|----|
| DF01-N-I1 | 1   | 1  | 1  |
| DF01-N-I2 | 1   | 1  | 1  |
| DF01-P-I1 | 0   | 0  | 0  |
| DF01-P-I2 | 0   | 0  | 0  |
| DF01-C-I1 | 0   | 0  | 0  |
| DF01-C-I2 | 0   | 0  | 0  |
| DF02-N-I1 | 1   | 1  | 1  |
| DF02-N-I2 | 1   | 1  | 1  |
| DF02-P-I1 | 1   | 1  | 1  |
| DF02-P-I2 | 0   | 0  | 0  |
| DF02-C-I1 | 0   | 0  | 0  |
| DF02-C-I2 | 0   | 0  | 0  |

Per method: TMC 5/12, R2 5/12, R3 5/12 (identical).
Per condition: N 12/12, P 3/12, C 0/12.

## Reading

- All three methods succeed on single-record creates and on a simple
  find-record-and-rename edit (DF02-P-I1).
- All three methods fail identically on: multi-hop record location
  (DF01-P: find a draft WO among statuses), edits to fields rendered deeper in
  the form (DF02-P-I2 description), and plan-change/submit flows with
  not_exists guards (all C conditions).
- Trajectory spot-checks (R3 DF01-P-I1) show failures are planning/navigation
  behavior (filtering lists, one malformed action per episode, 3-attempt
  exhaustion), not harness defects: the same chain with the deterministic
  planner completes every condition type.
- Methods are currently indistinguishable at this task difficulty; the C
  conditions (0/12) indicate the difficulty floor sits above all three
  planner stacks and should be recalibrated before the formal runs if
  method separation is the goal.
- Token cost: 1-3 LLM calls and 1-4k tokens per run observed.

## Harness fixes baked in during the pilot (v15-specific)

Save-button cascade, tab/section reveal, quick-entry dialog fill verification,
readback without visibility filtering, restore without backend restart,
compose-up retry. Full list in git log 60bdf7a..9fb07b6.
