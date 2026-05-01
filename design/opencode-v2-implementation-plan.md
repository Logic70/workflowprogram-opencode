# OpenCode V2 实施计划

## 1. 目的与范围

本文档基于以下三份当前真源：

- `opencode-v2-highlevel-design.md`
- `opencode-v2-lowlevel-design.md`
- `opencode-v2-validation-matrix.md`

目标是把 OpenCode v2 从“设计成立”推进到“最小可运行产品包成立”，并确保实施顺序与契约分层一致。

本文档先规划 v1 核心链路，并在第 10 章补充后续能力闭环计划：

- OpenCode only
- `source-as-deployment-source`
- package command + package plugin + runtime 主链
- 安装脚本生成宿主可发现布局
- target bundle 生成、受控写入与分层校验

本文档不覆盖：

- Claude 兼容实现
- marketplace / npm 发布
- 多宿主抽象框架

## 2. 实施目标

v1 实施目标如下：

| 编号 | 目标 | 验收口径 |
|---|---|---|
| IP-01 | 建成可安装的 package deployment source | `package/` 自包含 commands/plugin/runtime/validators |
| IP-02 | 跑通安装部署主链 | 能安装到 project-local/global 布局并写出 install manifest |
| IP-03 | 跑通 `/wp-develop` 主链 | 能生成 candidate bundle 并执行 managed apply |
| IP-04 | 跑通 `/wp-validate` 主链 | 能分层输出 package/spec/target/run-state 结论 |
| IP-05 | 能生成最小 target bundle | 至少交付 `.workflowprogram/design/*` 与 `.workflowprogram/runtime/*` |
| IP-06 | 校验分层落地 | Package/Spec/Target/Run-State validator 均可执行 |
| IP-07 | smoke 最小闭环成立 | 安装、package load、develop、generate/apply smoke 可执行 |
| IP-08 | 生命周期入口闭合 | `audit/evolve/orchestrate` 与 command/runtime/spec flow 一致 |
| IP-09 | agentteam 编排可验证 | package agent role schema、team plan、fan-in evidence 可校验 |
| IP-10 | 宿主隔离可诊断 | 能识别外部 OpenCode/Claude/oh-my-opencode 资产串入与版本/reload 风险 |
| IP-11 | target host reload 可验证 | 能区分 package host smoke 与 target host reload smoke |
| IP-12 | release artifact 可复现 | 能生成干净 `dist/opencode/` 或 archive 并校验 manifest/checksum |
| IP-13 | 契约硬化落地 | schema version、migration、error code、apply recovery、permission/privacy 策略进入 validator |
| IP-14 | 新项目全局引导安装 | 全局只安装 bootstrap，完整 package 仍通过 project-local 物化到当前项目 |
| IP-15 | AI 设计路径可追踪 | package command/host 先形成 `workflow-spec.md` 与 accepted `workflow-spec.yaml`；runtime 只消费 accepted spec，agent/team-plan 证据仅作可选审计上下文 |

## 3. 实施边界

### 3.1 实施中的固定边界

- 部署源根路径：`PACKAGE_SOURCE_ROOT = opencode-v2/package/`
- 已安装产品包根路径：`WP_PACKAGE_ROOT`
- 目标项目根路径：`TARGET_ROOT`
- 运行证据根路径：`RUN_ROOT`

### 3.2 不允许破坏的设计约束

- `/wp-*` 只属于产品包命令。
- `workflowprogram.ts` 只属于产品包插件。
- `workflow-spec.yaml` 只描述目标工作流，不描述产品包契约。
- validator 必须分层，不能跨层兜底。
- package 必须自包含 runtime 与 validators。
- target commands / target plugins 是否生成，必须由 target spec 决定。

## 4. 阶段划分

### P0 设计冻结与清理

目标：

- 删除已废弃的设计工作稿
- 统一当前真源入口
- 冻结实现边界

任务：

1. 删除旧稿：
   - `architecture.md`
   - `spec-delta.md`
   - `implementation-plan.md`
2. 更新 `README.md`
3. 更新 `design/index.md`
4. 把三份当前真源与本实施计划设为唯一设计入口

验收：

- `opencode-v2/design/` 中不再保留旧设计工作稿
- 索引只指向当前真源

### P1 建立产品包部署源骨架

目标：

- 建成最小可安装的 deployment source

任务：

1. 建立：
   - `package/opencode.json`
   - `package/.opencode/commands/`
   - `package/.opencode/plugins/`
   - `package/.workflowprogram/runtime/`
   - `package/.workflowprogram/runtime/validators/`
   - `package/.workflowprogram/runtime/requirements.txt`
2. 定义最小产品命令：
   - `wp-develop.md`
   - `wp-validate.md`
3. 建立最小 package plugin：
   - `workflowprogram.ts`
4. 建立安装脚本：
   - `package-deploy.py`
5. 补充 Python 依赖与 venv 支持：
   - 依赖清单写入 `requirements.txt`
   - 安装器支持 `--create-venv`

验收：

- Package Validator 的 `PKG-01 ~ PKG-10` 可全部执行
- `PACKAGE_SOURCE_ROOT` 不依赖仓库根目录脚本

### P2 建立 runtime 主链

目标：

- 建成 `/wp-develop` 与 `/wp-validate` 共用的 runtime 主链

任务：

1. 实现：
   - `workflow-entry.py`
   - `workflow-runner.py`
   - `managed-assets.py`
2. 实现运行上下文对象：
   - `PackageContext`
   - `TargetContext`
   - `RunContext`
3. 统一 root 解析：
   - `WP_PACKAGE_ROOT`
   - `TARGET_ROOT`
   - `RUN_ROOT`
4. 建立最小 evidence writer

验收：

- `/wp-develop` 能进入 `workflow-entry.py`
- `RUN_ROOT/context.json`、`state.json`、`events.jsonl` 能被写出

### P3 建立 workflow spec 生成链

目标：

- 让 runtime 能生成目标工作流语义与 target design assets

任务：

1. 实现 `workflow_spec_engine`
2. 生成：
   - `workflow-spec.yaml`
   - target `.workflowprogram/design/*`
3. 落地 `workflow_spec_validator.py`
4. 确保 spec 不含 package contract 字段

验收：

- `SPEC-01 ~ SPEC-09` 可执行
- target design assets 与 spec 保持一致

### P4 建立 target bundle 生成与受控写入

目标：

- 生成最小 target bundle 并通过 managed apply 写入目标项目

任务：

1. 实现 `target_bundle_generator`
2. 最小目标交付：
   - `TARGET_ROOT/.workflowprogram/design/*`
   - `TARGET_ROOT/.workflowprogram/runtime/*`
3. 条件性交付：
   - `TARGET_ROOT/.opencode/commands/*`
   - `TARGET_ROOT/.opencode/plugins/*`
4. 生成：
   - `managed-change-plan.json`
   - `managed-change-result.json`
   - `managed-files.json`
5. 落地 `target_bundle_validator.py`

验收：

- `TGT-01 ~ TGT-09` 可执行
- target bundle 与 spec 对齐
- 无静默覆盖

### P5 建立分层校验协调器

目标：

- 让 `/wp-validate` 走完整分层校验链

任务：

1. 实现：
   - `package_contract_validator.py`
   - `workflow_spec_validator.py`
   - `target_bundle_validator.py`
   - `run_state_validator.py`
2. 实现 `validation_coordinator`
3. 输出统一 validation summary

验收：

- `/wp-validate` 能分别产出四层 verdict
- validator 不跨层检查不属于自己的契约

### P6 建立 smoke 闭环

目标：

- 跑通最小真实链路验证

任务：

1. 建立 package load smoke
2. 建立 `/wp-develop` smoke
3. 建立 generate/apply smoke
4. 在有条件时建立 host integration smoke
5. 无真实 OpenCode 环境时保留 `ENVIRONMENT-SKIP`

验收：

- `SMK-01 ~ SMK-04` 至少 PASS
- 真实环境可用时 `SMK-06` 至少达到 package command/plugin 可发现

## 5. 任务优先级

### 必须先做

- P0
- P1
- P2
- P3
- P4

原因：

- 在没有可安装 deployment source、安装链、runtime 主链和 target bundle 之前，分层校验无法真正落地。

### 第二优先级

- P5
- P6

### 后置项

- target host-visible agents / skills 扩展
- marketplace / npm 发布流程
- 多宿主抽象框架

## 6. 文件级实施清单

### 需要新增

| 文件 | 作用 |
|---|---|
| `package/opencode.json` | 产品包配置 |
| `package/.opencode/commands/wp-develop.md` | 产品设计入口 |
| `package/.opencode/commands/wp-validate.md` | 产品校验入口 |
| `package/.opencode/plugins/workflowprogram.ts` | package plugin bridge |
| `package/.workflowprogram/runtime/package-deploy.py` | 安装、状态检查与卸载 |
| `package/.workflowprogram/runtime/requirements.txt` | runtime Python 依赖 |
| `package/.workflowprogram/runtime/workflow-entry.py` | runtime 主入口 |
| `package/.workflowprogram/runtime/workflow-runner.py` | 阶段推进 |
| `package/.workflowprogram/runtime/managed-assets.py` | candidate/apply |
| `package/.workflowprogram/runtime/validators/package_contract_validator.py` | package 校验 |
| `package/.workflowprogram/runtime/validators/workflow_spec_validator.py` | spec 校验 |
| `package/.workflowprogram/runtime/validators/target_bundle_validator.py` | target bundle 校验 |
| `package/.workflowprogram/runtime/validators/run_state_validator.py` | run-state 校验 |

### 需要后续新增

| 文件 | 前提 |
|---|---|
| target `.opencode/commands/*` 模板 | target spec 明确要求生成 target commands |
| target `.opencode/plugins/*` 模板 | target spec 明确要求生成 target plugin |
| smoke 脚本与 fixture | P5 完成后 |

## 7. 风险与对策

### 风险 1：runtime 仍偷偷依赖仓库根目录脚本

对策：

- 以 `PKG-10` 作为强校验项
- 所有产品命令只允许调用当前 package runtime，对已安装布局即 `WP_PACKAGE_ROOT/.workflowprogram/package/runtime/*`

### 风险 2：`workflow-spec.yaml` 再次混入 package 语义

对策：

- 以 `SPEC-08` 作为强校验项
- 评审时优先检查 spec 是否引用产品包路径或产品包命名

### 风险 3：target bundle 被误做成 package 的镜像

对策：

- target bundle 只生成 target spec 要求的资产
- `TGT-06/TGT-07/TGT-08` 限制 target OpenCode 资产的条件生成与命名隔离

### 风险 4：产品命令与 target command 冲突

对策：

- 产品命令固定使用 `/wp-*`
- target commands 禁止占用 `/wp-*`

### 风险 5：package plugin 职责膨胀

对策：

- `workflowprogram.ts` 只做 bridge
- runtime 主链仍以 Python 脚本承载

### 风险 6：目标工作流生成退化为 Python-only

对策：

- package command/host 先完成澄清、设计回读和 accepted `workflow-spec.yaml`
- `agent-team-planner.py` 仅提供可选调度建议；无法调度 agent 不能被当作 mutation 成功证据
- runtime 缺少 `--spec` 时不得默认用 Python 模板生成生产 workflow；只有显式 fixture/fallback 才允许模板路径且必须返回 WARN

## 8. 建议执行顺序

1. 完成 P1，先让 package 能被宿主识别
2. 完成 P2，先让 `/wp-develop` 能进入 runtime
3. 完成 P8 的 AI 设计路径最小能力，让 `/wp-develop` 先形成 `workflow-spec.md` 与 accepted `workflow-spec.yaml` 再进入 runtime
4. 完成 P3，生成最小 target design assets
5. 完成 P4，形成最小 target bundle 与 managed apply
6. 完成 P5，建立 `/wp-validate` 的分层校验能力
7. 完成 P6，建立 smoke 闭环

## 10. 能力差距闭环实施计划

本章对应 OpenSpec change：`openspec/changes/complete-opencode-parity-gap-closure`。这些任务不改变 v1 核心链路已经成立的判断，但用于补齐与 ClaudeCode 版相比仍缺失的 OpenCode-native 能力。

### P7 生命周期入口闭合

目标：

- 消除 `audit` flow 已存在但产品命令与 runtime intent 不支持的不一致。
- 增加 `evolve` 与 `orchestrate`，让用户不必记忆每个具体命令。

任务：

1. 定义 `IntentContract`
2. 新增 `/wp-audit`、`/wp-evolve`、`/wp-orchestrate`
3. 扩展 `SUPPORTED_PACKAGE_INTENTS`
4. 实现 audit/evolve/orchestrate runtime handler
5. 增加 command/runtime/spec flow 一致性测试

验收：

- `wp-*` command、runtime handler、spec `intent_flows` 无悬空项
- `audit` 非变更，`evolve` 走 managed apply，`orchestrate` 低置信度时只澄清不变更

### P8 agentteam 编排与角色 schema

目标：

- 把 package agents 从静态文件集合升级为可编排团队结构。
- 明确 agentteam 与 subagent 的区别。
- 明确 AI 协作层与 Python runtime 的职责：host/model/agents 形成 accepted 设计，runtime 负责确定性校验、生成和写入。

任务：

1. 定义 agent role schema
2. 为现有 agents 增加角色元数据
3. 新增 `test-scenario-generator`
4. 实现 `agent-team-planner.py`
5. 为 `recommended_dispatch` 增加 `pre-runtime` / `post-runtime` 调度时机
6. 输出 `team-plan.json`、`team-plan.md`、dispatch trace、fan-in report
7. `workflow-entry.py --ai-evidence` 仅保留为 legacy 诊断字段；核心输入改为 `--draft` 与 `--spec`
8. 增加 package validator 对 role registry 的校验

验收：

- 一个阶段可配置零个、一个或多个 agent
- 多 reviewer 场景能生成 fan-in evidence
- role 引用不存在时 validator fail
- `/wp-develop` 等变更型命令先调度 pre-runtime 设计 agent，再进入 Python runtime

### P9 宿主隔离与兼容诊断

目标：

- 解决 WSL/OpenCode 场景中非本项目 skills/agents/commands 被识别的问题。

任务：

1. doctor 增加 host source inventory
2. 检测 project/global OpenCode 配置来源
3. 检测 ClaudeCode 与 oh-my-opencode 资产串入
4. 检测命名冲突与 shadowing
5. 增加 OpenCode 版本/plugin API/reload guidance
6. 增加 WSL/Windows 路径诊断

验收：

- doctor 能指出污染来源路径和风险类型
- remediation 只给建议，不自动删除用户全局资产

### P10 target host reload smoke

目标：

- 证明生成后的目标工作流能被 OpenCode host 发现，而不仅是 WorkflowProgram package 能被发现。

任务：

1. 定义 target host reload smoke contract
2. 构造 target command fixture
3. 构造 target plugin fixture
4. 真实 OpenCode 可用时执行 host reload smoke
5. 不可用时输出 `ENVIRONMENT-SKIP`
6. deterministic fallback 只验证文件契约，不伪造 host PASS

验收：

- package host smoke 与 target host reload smoke 分开报告
- provider/API 不可用不会导致假阳性

### P11 release build 与安装生命周期

目标：

- 从开发目录安装升级为可发布、可复现、可验证的 release 产物。

任务：

1. 新增 `tools/build_package.py`
2. 产出 `dist/opencode/` 或 archive
3. 排除 runs、cache、node_modules、logs、secrets
4. 写 release manifest 与 checksum
5. 从 release artifact 跑 install smoke
6. 补重复安装、升级、卸载、status 测试
7. 补离线依赖锁定方案

验收：

- release 包不含本地运行痕迹
- release artifact 可独立安装并通过 package validator

### P12 契约硬化

目标：

- 让 schema、写入恢复、错误码、权限和隐私不只停留在文档约束。

任务：

1. 给 spec/manifest/run-state/install manifest 增加 `schema_version`
2. 实现 migration engine 与 migration report
3. managed apply 增加 lock、idempotent diff、rollback manifest
4. 建立 error code registry
5. 定义 permission policy
6. 增加日志和证据脱敏

验收：

- validator 能识别 schema 不兼容、错误码缺失、敏感信息未脱敏
- apply 中断后 doctor 能说明 recover/rollback 路径

### P13 深度校验与 CI fixtures

目标：

- 补齐 ClaudeCode 版更细粒度的验证能力，并让回归测试更接近真实工作流。

任务：

1. 增加 workflow draft validator
2. 增加 lowlevel design validator
3. 增加 generated runtime validator
4. 增加 lessons delta validator
5. 增加 clarification review
6. 增加 sequential、target command、target plugin 三类 golden fixtures
7. 建立 CI 入口：`py_compile`、validator regression、install smoke、target host smoke、release integrity

验收：

- `/wp-validate` 或 `/wp-audit` 可选择执行 deep validation
- CI 没有真实 OpenCode host 时只 skip host-dependent checks，不标记 PASS

### P14 全局轻量 bootstrap 安装器

目标：

- 改善新项目首次使用体验，避免用户每个项目手写长安装命令。
- 避免完整 WorkflowProgram 全局安装带来的命令污染和版本串扰。

任务：

1. 新增 `bootstrap-runtime.py`
2. 扩展 `package-deploy.py install-bootstrap`
3. 扩展 `package-deploy.py bootstrap-status`
4. 扩展 `package-deploy.py uninstall-bootstrap`
5. 写入全局 `/wp-install`、`/wp-status`、`/wp-upgrade`、`/wp-uninstall`
6. 建立用户级版本化 package cache
7. smoke 覆盖 bootstrap install -> project-local install -> project status

验收：

- 全局 bootstrap 不安装完整 lifecycle commands、agents 或 package plugin
- 新项目通过 `/wp-install` 能获得完整 project-local package
- bootstrap manifest 和 project install manifest 均可追踪

## 9. 工作量估算

按有效开发时间估算：

| 阶段 | 估算 |
|---|---|
| P0 | 0.5 天 |
| P1 | 0.5 天 |
| P2 | 1.5 天 |
| P3 | 1 天 |
| P4 | 1 天 |
| P5 | 1 天 |
| P6 | 1 天 |

总计约：

- 最小实现：4.5 ~ 5 天
- 含完整校验与 smoke：6 ~ 6.5 天
