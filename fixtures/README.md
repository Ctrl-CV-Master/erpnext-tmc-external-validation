# Fixtures

- `base_fixture.sql.gz` — deterministic synthetic base snapshot of the
  "Open Preparation Lab" environment (created at Gate 2), restored per run.
- `task_fixtures/` — deterministic per-task initial-state deltas
  (N / P / C × instance 1/2), applied after base restore, verified by hash.
