# Claude WorkflowProgram Backport OpenSpec Input

本文档整理 OpenCode v2 中适合反哺 ClaudeCode 版 WorkflowProgram 的宿主无关能力，作为后续 Claude 版 OpenSpec change 的输入材料。

本输入不要求 Claude 版迁移 OpenCode 实现。目标是把已澄清的产品模型、artifact 契约、验证边界和证据纪律同步回 Claude 版。

## Change Id

`align-claude-workflow-graph-contract`

## 目标

把 Claude 版 WorkflowProgram 从隐式 AI 设计与脚本执行，升级为显式的：

- AI/user 设计 workflow graph
- accepted `workflow-spec.md` 做人类可读回读
- accepted `workflow-spec.yaml` 做唯一机器语义源
- Python/runtime 做校验、生成和受控写入
- 目标 workflow 资产必须由 spec 声明
- managed apply 只负责目标 workflow 写入
- 自迭代、澄清、验证、handoff 作为可选能力模板，由 AI 按需求编排

核心目标不是削弱 Claude 的 AI 设计能力，而是让 AI 设计结果进入可审计、可验证、可恢复的 WorkflowProgram 契约。

## 非目标

本次不处理安装部署和 Claude 插件市场已经覆盖的问题：

- Claude 插件市场安装、升级、卸载
- OpenCode `/wp-install`、`/wp-status`、`/wp-upgrade`、`/wp-uninstall`
- OpenCode bootstrap、cache、venv、`package-deploy.py`
- OpenCode `.opencode/*` 布局
- OpenCode plugin bridge、OpenCode hook 名称、OpenCode custom tool 接口
- OpenCode CLI probe、`opencode run`、sidecar timeout cleanup
- OpenCode host smoke runner 的具体实现
- 新增独立 AI evidence 概念，例如 `AI-DESIGN-*`、`ai-design-source.json`

## 背景问题

当前设计容易把 AI 与 Python 误拆成二选一：

- 纯 prompt/skill 驱动被认为不可靠。
- 纯 Python 模板会把 workflow 固化成机械产物。
- 正确模型应是 AI 设计 graph，Python 校验和 apply。

Claude 版应显式保留 AI 设计能力，但要求 AI 设计必须落到 accepted spec。runtime 不应再从隐藏固定模板中生成 workflow 语义。

## 需要反哺的能力

| 能力 | 目标 | 思路 |
|---|---|---|
| AI graph 设计模型 | 去掉固定 S1-S6 生产路径，让 AI/user 定义请求特定 workflow graph | 固定 spec 外层结构；AI 定义节点、边、顺序、分支、fan-in/fan-out、准入准出、上下文业务语义 |
| 核心 artifact 契约 | 消除多个语义源造成的歧义 | `workflow-spec.md` 是人类可读设计回读；`workflow-spec.yaml` 是唯一机器语义源；其他 view 只能是派生诊断报告 |
| 澄清、回读、确认门禁 | 防止需求不清时直接生成目标 workflow | broad request 先澄清；生成前回读 graph、能力选择、禁用能力、上下文契约和将写文件；明确确认后 runtime 才能写入 |
| 可选能力模板 | 让通用流程可复用，但不固定塞进所有 workflow | clarification、validation、self-iteration、merge/fan-in、handoff 作为模板库；AI 按需求选择并展开到 graph |
| 目标资产声明 | 防止 runtime 生成 spec 没声明的 command、skill、agent、hook | 在 `workflow-spec.yaml` registry 中声明目标资产；runtime 只生成声明资产；validator 检查生成物一致性 |
| managed apply | 让目标 workflow 写入可恢复、可审计 | candidate bundle、apply lock、idempotent diff、unmanaged conflict report、rollback/recover manifest、apply result evidence |
| 验证分层 | 避免把设计失败、生成失败、宿主不可用混成一个结果 | 分开验证澄清/回读、spec、生成物、managed apply、Claude 宿主可见性；宿主/API 不可用分类为 `ENVIRONMENT-SKIP` |
| schema/error/privacy 契约 | 让报告和状态长期可迁移、可排错、可发布 | `workflow-spec.yaml`、run-state、managed manifest、validation report 加 schema version；统一错误码、remediation 和日志脱敏 |
| agentteam 证据纪律 | 防止 team plan 被误判为 agent 已执行 | team plan 只是计划；只有实际 subagent 输出、调度记录或明确 evidence 才算参与证据；影响设计的 agent 输出必须反映到 accepted spec |

## 只反哺思想、不反哺实现

| OpenCode 能力 | Claude 版处理 |
|---|---|
| host smoke 分层 | 保留语义验证、宿主可见性、环境不可用的分类思想；不要迁移 OpenCode runner |
| package/target 分层 | 保留产品包资产与目标 workflow 资产分层原则；映射到 Claude plugin/command/skill/agent/hook 边界 |
| host isolation doctor | 改为检查 Claude 生态冲突，例如全局 `.claude`、重复 command/skill/hook、插件市场版本冲突 |
| target asset registry | 保留 registry 规则；资产类型换成 Claude command、skill、agent、hook |
| runtime provider abstraction | 如 Claude 插件市场入口已稳定，不需要 OpenCode provider 层；只保留宿主不可用的结果分类 |

## 设计思路

### 1. Artifact Chain

Claude 版应采用单一语义链：

```text
clarification/readback
  -> accepted workflow-spec.md
  -> accepted workflow-spec.yaml
  -> Python validation
  -> candidate bundle
  -> managed apply
  -> validation report
```

`workflow-view.md`、`workflow-lowlevel.md` 等文件如果存在，只能由 `workflow-spec.yaml` 派生，不能反向参与 workflow 语义决策。

### 2. Graph Spec Shape

`workflow-spec.yaml` 建议保留固定外层结构：

- `meta`
- `nodes`
- `transitions`
- `templates`
- `intent_routes`
- `context_contract`
- `registry`
- `outputs`
- `runtime_contract`
- `generated_runtime_contract`

固定的是字段结构和校验规则。请求实例中的节点名称、顺序、分支逻辑、fan-in/fan-out、准入准出条件、上下文业务含义由 AI/user 设计。

### 3. Confirmation Gate

确认必须具体，不能只依赖 `--confirmed` 或类似标记。

确认前必须说明：

- 将写入 `workflow-spec.md`
- 将写入 `workflow-spec.yaml`
- 将运行 Python validation/generation/apply
- 将创建哪些目标 command、skill、agent、hook 或 runtime 文件
- 哪些能力被启用，哪些能力被禁用

### 4. Target Asset Registry

Claude 版的目标资产应由 spec registry 驱动：

- spec 未声明的目标资产不得生成
- runtime 只能生成 spec 声明的资产
- validator 必须检查目标文件与 registry 一致
- 未声明资产应 `FAIL` 或至少 `WARN`，具体取决于是否会影响运行安全

### 5. Managed Apply Boundary

managed apply 只覆盖目标 workflow 写入，不覆盖 Claude 插件市场安装。

应输出：

- apply plan
- candidate bundle
- conflict report
- rollback manifest
- recover instruction/evidence
- final apply result

### 6. Evidence Rule

agent/team evidence 的成功条件必须明确：

- team plan 不等于 agent 已执行
- agent 被列入计划不等于 agent 已参与
- agent 输出如果改变设计，必须进入 accepted `workflow-spec.yaml`
- standalone AI evidence 不能绕过澄清、回读、确认和 spec 校验

## OpenSpec Tasks 草案

```md
## 1. Design Contract

- [ ] 1.1 Document "AI/user graph design + Python validation/apply" as the Claude WorkflowProgram model.
- [ ] 1.2 Remove fixed S1-S6 from the production workflow design path.
- [ ] 1.3 Define `workflow-spec.md` as human-readable accepted design/readback.
- [ ] 1.4 Define `workflow-spec.yaml` as the only machine-readable semantic source.
- [ ] 1.5 Mark generated views as non-semantic derived reports only.

## 2. Clarification And Confirmation

- [ ] 2.1 Require clarification for broad or underspecified workflow requests.
- [ ] 2.2 Require design readback before runtime generation.
- [ ] 2.3 Require explicit user confirmation before writing target workflow assets.
- [ ] 2.4 Ensure confirmation names the artifacts and files to be written.

## 3. Graph Spec

- [ ] 3.1 Define fixed graph spec shape: nodes, transitions, context contract, registry, outputs, runtime contract.
- [ ] 3.2 Allow AI to define request-specific node names, sequence, branch logic, fan-in/fan-out, entry/exit criteria.
- [ ] 3.3 Treat clarification, validation, self-iteration, merge, and handoff as optional templates selected by AI.

## 4. Target Asset Registry

- [ ] 4.1 Require target commands/skills/agents/hooks to be declared in `workflow-spec.yaml`.
- [ ] 4.2 Generate only assets declared by the accepted spec.
- [ ] 4.3 Validate generated assets against the spec registry.
- [ ] 4.4 Fail or warn on undeclared target assets.

## 5. Managed Apply

- [ ] 5.1 Route all target workflow writes through candidate bundle + managed apply.
- [ ] 5.2 Add lock, idempotent diff, conflict report, rollback manifest, and recover evidence.
- [ ] 5.3 Keep plugin marketplace installation outside this change.

## 6. Validation And Evidence

- [ ] 6.1 Validate clarification/readback evidence.
- [ ] 6.2 Validate graph shape and transition reachability.
- [ ] 6.3 Validate runtime/generated artifacts against `workflow-spec.yaml`.
- [ ] 6.4 Classify host/API unavailable checks as `ENVIRONMENT-SKIP`.
- [ ] 6.5 Add schema version, error code, remediation, and privacy redaction checks.
- [ ] 6.6 Enforce agentteam evidence discipline: plan is not execution evidence.

## 7. Regression

- [ ] 7.1 Add a fixture where AI defines a non-S1-S6 graph.
- [ ] 7.2 Add a fixture where self-iteration is selected only when needed.
- [ ] 7.3 Add a fixture where undeclared target assets are rejected.
- [ ] 7.4 Add a negative fixture where confirmation is missing and no target assets are written.
- [ ] 7.5 Add a negative fixture where agent/team-plan evidence exists but accepted spec is missing.
```

## 验收口径

Claude 版完成本 change 后，应满足：

- 生产路径不再依赖固定 S1-S6 模板生成 workflow 语义
- broad request 缺少澄清和回读时不会写入目标 workflow
- `workflow-spec.yaml` 是唯一机器语义源
- 目标资产与 spec registry 一致
- managed apply 能报告冲突并支持 rollback/recover
- agentteam plan 不会被误判为执行证据
- 宿主不可用时能够与 workflow 语义失败区分

## 一句话总结

这次反哺的目标是把 Claude 版从隐式 AI 设计与脚本执行，升级为显式 AI graph 设计、accepted spec、Python 校验/apply 的闭环；同时不碰 Claude 插件市场负责的安装部署问题。
