# Evaluator

Post-run final-state checks against the database / Frappe ORM:

- required documents exist
- required field values correct
- required object relationships correct
- expected Job Card / QI / Batch / Stock Entry states correct
- pre-existing data preserved
- no forbidden duplicates or unrelated persistent modifications

reward = 1 only if ALL conditions hold. The agent never sees evaluator
conditions. Frozen before the formal 432 runs.
