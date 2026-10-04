# Protocol

`protocol.md` 将在 Gate 3(36 pilot runs)通过后**冻结**。冻结后不得修改:

- task task definitions(24 families × N/P/C × 2 instances)
- reward conditions(evaluator)
- step budget(browser action budget = 80)
- method implementations(TMC-AE / R2 / R3)

Gate 顺序:

1. **Gate 1** — `erpnext-smoke.yml`:GitHub runner 上 ERPNext + Playwright + evaluator 链路验证
2. **Gate 2** — 完整 base fixture(`base_fixture.sql.gz`,restore 后 hash 一致)+ 正式 evaluator
3. **Gate 3** — 2 个独立 development families × 3 conditions × 2 instances × 3 methods = 36 pilot runs
   (不进入正式 24 families;infrastructure/protocol pilot)
4. 冻结 protocol → 一次性启动正式 48 matrix jobs × 9 runs = 432 runs
