# ERPNext TMC-AE External Validation

跨系统制造环境实验:在 **ERPNext v15.99.1** 上以公开 GitHub Actions 免费标准 runner 运行
TMC-AE / R2 (ATG-adapted) / R3 (Task-State-adapted) 三种方法的对比实验。

- **Task set**: 24 task families × 3 conditions (N/P/C) × 2 data instances = **144 paired tasks**
- **Formal runs**: 144 × 3 methods = **432 runs**,以 48 个 matrix jobs(family × instance)组织,`max-parallel: 20`
- **Agent interface**: 仅 ERPNext Web UI(Playwright + Chromium,headless)
- **LLM**: GLM-5.3,temperature = 0,API key 只存于 GitHub Actions Secret `GLM_API_KEY`

## 合规声明

本仓库**只包含**合成实验材料:ERPNext environment adapter、合成的制剂制造 fixtures、
可公开的三种方法实验实现、evaluator、protocol、GitHub Actions workflows、统计分析脚本。

**严禁出现**(提交前必须检查):

- 真实患者、医院、人员信息或任何未脱敏的原医院实验材料
- 私有 MES 源码、厂商代码
- API key、密码、token(一律走 Actions Secret)

所有业务数据均为虚构("Open Preparation Lab" 合成制剂公司),不对应任何真实药品/机构。

## Gate 流程

| Gate | 内容 | 状态 |
|------|------|------|
| 1 | `erpnext-smoke.yml`:runner 磁盘清理 → 启动 ERPNext → Playwright UI 读写 → evaluator 读回 | **通过**(2026-10-05,v15.99.1,run 37271739495;v15 适配修复见 git log 96bf125..c87a054) |
| 2 | 完整 base fixture(`base_fixture.sql.gz`)+ 正式 evaluator | **在 v15.99.1 上重建并验证**(2026-10-05,run 37272681828;build/restore `STATE_HASH` 一致,sha256 `e8a67b65`) |
| 3 | 2 个独立 development families × 36 pilot runs(不进正式集) | pending |
| — | 冻结 protocol(evaluator / 任务 / 预算不得再改) | pending |
| 正式 | 48 matrix jobs × 9 runs = 432 runs | pending |

## 环境冻结(锚点)

- ERPNext `v15.99.1`(tag commit `b2a8af5ba66a775e9a1887ae03235d68062c7e63`;2026-10-05 由 v16.37.0 切换)
- frappe `version-15`(切换时 head `0b282e81ef30a7f6b8ff376ca8eacf9fb9f28f05`)
- frappe_docker `f71a386bc13f75dcc0cf7462f025f531576a04fc`(pwd.yml 不变;v15 时由 `smoke/start_erpnext.sh` 将 mariadb 钉到 `10.6`,v15 不兼容 mariadb 11.x)
- runner `ubuntu-24.04`,Playwright 版本在 smoke 中确定后冻结
- 详细版本/digest 记录于每次运行产出的 `environment_manifest.json`

## 目录

```
.github/workflows/   CI workflows(仅 workflow_dispatch 手动触发)
scripts/             runner 磁盘清理等基础设施脚本
smoke/               Gate-1 smoke test(启动栈/UI 测试/evaluator 测试/指标采集)
adapter/             ERPNext environment adapter(Phase 2)
evaluator/           正式 evaluator(Phase 2)
fixtures/            base_fixture.sql.gz 与任务 fixtures(Phase 2)
tasks/               task_families.yaml / tasks_144.jsonl(Phase 2)
protocol/            protocol.md(Gate 3 后冻结)
analysis/            统计分析脚本(Phase 3)
```
