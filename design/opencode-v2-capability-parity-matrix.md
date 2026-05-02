# OpenCode V2 Capability Parity Matrix

本文档记录 ClaudeCode 版能力到 OpenCode 版能力的映射状态。它不是要求 OpenCode 复制 ClaudeCode 的目录结构，而是用于追踪产品能力是否已有 OpenCode-native 实现。

## 状态定义

| 状态 | 含义 |
|---|---|
| 已实现 | OpenCode 版已有等价能力 |
| 部分实现 | 核心能力存在，但验证、编排或产品化不足 |
| 待规划 | OpenCode 版需要补齐，但不属于当前 OpenSpec 变更范围 |
| 不适用 | ClaudeCode 宿主特有能力，不应迁移 |
| 替代实现 | OpenCode 使用不同机制实现同类目标 |

## OpenCode-native 增强项

这些增强项不改变主链目标：核心体验仍是 AI/user 设计 workflow graph，Python runtime 做契约校验、受控生成和 managed apply。增强集中在 OpenCode 宿主工程化、安装隔离、可审计验证和恢复能力上。

| 增强项 | 相对 ClaudeCode 原版的增量 | 当前落点 |
|---|---|---|
| 全局轻量 bootstrap | 新项目只需要全局 `/wp-install` 引导，从用户级版本化 cache 物化完整 project-local package；避免完整全局安装造成命令污染和版本串扰 | `package-deploy.py install-bootstrap`、`bootstrap-runtime.py`、`/wp-install`、`/wp-upgrade` |
| package/target 严格分层 | WorkflowProgram 产品包命令、agent、plugin 与生成后的目标 workflow command/plugin 分开管理；目标资产必须由 `workflow-spec.yaml` registry 声明 | `.opencode/*`、`.workflowprogram/package/*`、target bundle validator |
| managed apply 强化 | 写入有 manifest、lock、idempotency、rollback/recover、unmanaged conflict 检测；package venv 作为 managed directory 被安装器识别 | managed apply runtime、install manifest、`package-deploy.py` |
| 真实 OpenCode host smoke 分层 | package host integration smoke 和 target host reload smoke 分开；host/API 不可用或超时时返回 `ENVIRONMENT-SKIP`，不把宿主问题伪装成语义通过或失败 | `host-integration-smoke.py`、`target-host-smoke.py`、`runtime_host.py` |
| 宿主隔离诊断 | doctor 显式检查全局 OpenCode 配置、Claude 资产、oh-my-opencode 资产、版本和 reload 风险 | `doctor.py`、host isolation validation |
| 安装生命周期产品化 | 支持 status、upgrade、uninstall、offline lock、project-local venv、bootstrap status，便于本地项目长期维护 | `package-deploy.py`、`bootstrap-runtime.py`、install/status docs |
| schema/error/privacy 契约 | spec、manifest、run-state、install manifest 具备 schema version；错误码和隐私脱敏形成跨 validator/runtime 的统一约束 | schema migration、error taxonomy、privacy redaction |
| AI graph 设计的确定性落地 | stage/intentflow 的结构固定，但节点名称、顺序、分支、fan-in/out、准入准出、可选自迭代和 hook 由 AI/user 在 accepted spec 中定义 | `workflow-spec.md`、`workflow-spec.yaml`、graph validator |

## 能力映射

| 能力域 | ClaudeCode 版能力 | OpenCode 版状态 | OpenCode 处理方式 | 对应 spec |
|---|---|---|---|---|
| 产品命令 | `develop`、`preflight`、`hotfix`、`iterate`、`ship` | 已实现 | `/wp-*` package commands + runtime intents | 已完成 |
| 产品命令 | `evolve-workflow` | 已实现 | `/wp-evolve` + managed apply evolve plan | `opencode-product-lifecycle-intents` |
| 产品审计 | `workflow-audit`、`workflowprogram-audit` | 已实现 | `/wp-audit` 非变更审计 | `opencode-product-lifecycle-intents` |
| 自然语言编排 | `workflowprogram-orchestrate` skill | 替代实现 | `/wp-orchestrate` + `route-intent.py`；默认只路由和产出建议，不自动执行变更 | `opencode-product-lifecycle-intents` |
| Agent 基础包 | designer/validator/verifier/reviewers | 已实现 | `.opencode/agents/*.md` package agents | 已完成 |
| 测试场景生成 | `test-scenario-generator` agent | 已实现 | 新增 package agent + evidence 输出 | `opencode-agentteam-orchestration` |
| 团队编排 | host team utilities / reviewer roles | 已实现 | 增加 role schema、team planner、fan-in evidence；不模拟宿主 subagent 调度 | `opencode-agentteam-orchestration` |
| Skills | commit/doc/review/test/validate-file | 部分实现 | 不直接复制为 Claude skill；按 OpenCode command/agent/doc 迁移必要能力 | `opencode-validation-depth` |
| Spec 模板 | workflow-spec-support templates | 部分实现 | 作为 OpenCode design templates 或 generator fixtures | `opencode-validation-depth` |
| 插件 hook | Claude hooks | 替代实现 | OpenCode `.opencode/plugins/workflowprogram.ts` hook bridge | 已完成 / `opencode-contract-hardening` |
| Custom tool | Claude tool/plugin 扩展 | 部分实现 | OpenCode plugin bridge 后续补 tool registry 约束 | `opencode-contract-hardening` |
| Runtime 主链 | workflow-entry / workflow-runner | 已实现 | Python runtime under package root | 已完成 |
| 运行状态总线 | `state-bus.py`、`stage-progress.py` | 部分实现 | 当前有 run evidence；后续补统一状态总线和进度工具 | `opencode-validation-depth` |
| 澄清包 | clarification package/review | 已实现 | 已有澄清资产并补充 clarification review generator | `opencode-validation-depth` |
| 深度校验 | draft/runtime/lessons validators | 已实现 | 增加 deep validators；不把 generated design view 当作核心语义来源 | `opencode-validation-depth` |
| Host doctor | doctor/probe/remediation | 已实现 | 补齐 host isolation、版本兼容、reload 诊断 | `opencode-host-isolation-and-compatibility` |
| Host bootstrap | apply-host-bootstrap | 替代实现 | OpenCode 不默认改全局配置；提供诊断和显式 remediation | `opencode-host-isolation-and-compatibility` |
| Package smoke | verify plugin load | 已实现 | package host integration smoke | 已完成 |
| Target reload smoke | 目标工作流真实加载 | 已实现 | target host reload smoke；API 不可用时按 `ENVIRONMENT-SKIP` 分类，不伪造真实执行结果 | `opencode-target-host-verification` |
| Build/release | Claude plugin/package metadata | 替代实现 | OpenCode release build from `package/` to clean artifact | `opencode-release-and-installation` |
| 安装生命周期 | plugin install/runtime bootstrap | 已实现 | package deploy + venv + status/reinstall/lock regression | `opencode-release-and-installation` |
| 新项目安装体验 | 全局 skill/command 引导安装 | 已实现 | 全局轻量 `/wp-install` bootstrap + 用户级 cache + project-local materialization | `opencode-global-bootstrap-installer` |
| Schema 演进 | 隐式脚本契约 | 已实现 | schema version + migration | `opencode-contract-hardening` |
| 写入恢复 | managed generation | 已实现 | lock、idempotency、rollback/recover manifest | `opencode-contract-hardening` |
| 权限与隐私 | settings/hooks 约束 | 已实现 | permission policy + privacy redaction | `opencode-contract-hardening` |
| Claude plugin metadata | `.claude-plugin/plugin.json`、marketplace | 不适用 | 不迁移；OpenCode 使用 `.opencode/*` 加载 | 无 |

## 当前完成范围

| 范围 | 能力 |
|---|---|
| 本次已完成 | audit/evolve/orchestrate、agentteam role schema、test-scenario-generator、host isolation、target host reload smoke、capability parity 维护 |
| 本次已完成 | release build、schema migration、managed apply hardening、error taxonomy、deep validators、offline/reinstall/status regression |
| 后续可规划 | target agents/skills、marketplace/npm 发布、多宿主抽象 |
