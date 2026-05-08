# OpenCode V2 Design Index

## 目的

本索引用于声明 OpenCode v2 的当前设计真源与文档分工。

## 当前生效真源

- [opencode-v2-highlevel-design.md](opencode-v2-highlevel-design.md)
- [opencode-v2-lowlevel-design.md](opencode-v2-lowlevel-design.md)
- [opencode-v2-graph-workflow-design.md](opencode-v2-graph-workflow-design.md)
- [opencode-v2-graph-workflow-plan.md](opencode-v2-graph-workflow-plan.md)
- [opencode-v2-validation-matrix.md](opencode-v2-validation-matrix.md)
- [opencode-v2-implementation-plan.md](opencode-v2-implementation-plan.md)
- [opencode-v2-capability-parity-matrix.md](opencode-v2-capability-parity-matrix.md)
- [claudecode-to-opencode-adaptation.html](claudecode-to-opencode-adaptation.html)
- [../openspec/changes/complete-opencode-parity-gap-closure](../openspec/changes/complete-opencode-parity-gap-closure)
- [../openspec/changes/align-opencode-design-flow-with-claude](../openspec/changes/align-opencode-design-flow-with-claude)
- [../openspec/changes/add-global-bootstrap-installer](../openspec/changes/add-global-bootstrap-installer)
- [../openspec/changes/add-ai-collaboration-layer](../openspec/changes/add-ai-collaboration-layer)
- [../openspec/changes/replicate-claude-latest-contracts](../openspec/changes/replicate-claude-latest-contracts)
- [../openspec/changes/add-opencode-requirement-logic-interview](../openspec/changes/add-opencode-requirement-logic-interview)
- [../openspec/changes/add-maintenance-cleaner](../openspec/changes/add-maintenance-cleaner)

## 文档分工

| 文档 | 作用 |
|---|---|
| `opencode-v2-highlevel-design.md` | 定义系统边界、分层契约、架构模型、部署与交付规划 |
| `opencode-v2-lowlevel-design.md` | 定义特性拆分、use case、模块接口、story 依赖与实现约束 |
| `opencode-v2-validation-matrix.md` | 定义 package/spec/target/run-state/smoke 的分层校验矩阵 |
| `opencode-v2-implementation-plan.md` | 定义实施阶段、优先级、文件级改造清单与风险收口顺序 |
| `opencode-v2-capability-parity-matrix.md` | 追踪 ClaudeCode 能力到 OpenCode-native 能力的映射状态，并记录 OpenCode 版的产品化增强项 |
| `claudecode-to-opencode-adaptation.html` | 以 HTML 方式总结 ClaudeCode 到 OpenCode 适配的关注点、难点和解决方案 |
| `../openspec/changes/complete-opencode-parity-gap-closure` | 定义本轮对齐 ClaudeCode 能力差距的 spec 分解、设计决策和实施任务 |
| `../openspec/changes/align-opencode-design-flow-with-claude` | 定义 AI/user 设计 graph、Python 校验/apply、确认门禁和核心 artifact 关系 |
| `../openspec/changes/add-global-bootstrap-installer` | 定义全局轻量 bootstrap、用户级 cache 和项目本地安装体验优化 |
| `../openspec/changes/add-ai-collaboration-layer` | 历史变更；host-dispatch 资产可保留，但语义上被 `align-opencode-design-flow-with-claude` 取代 |
| `../openspec/changes/replicate-claude-latest-contracts` | 定义 Claude 最新设计源血缘和 node loop 契约到 OpenCode top-level `design_refs`、`nodes[*].loop_policy` 的映射 |
| `../openspec/changes/add-opencode-requirement-logic-interview` | 定义 S1 需求逻辑访谈、七个 logic lenses、question backlog、requirement logic map 与 S5 handoff 校验 |
| `../openspec/changes/add-maintenance-cleaner` | 定义 `/wp-clean` 项目清理、bootstrap cache prune、保护路径和 maintenance report |

## 跨版本输入

| 文档 | 作用 |
|---|---|
| `claude-backport-openspec-input.md` | 整理可反哺 ClaudeCode 版的宿主无关能力，作为 Claude 版 OpenSpec change 输入；不包含安装部署和 OpenCode host 细节 |

## 当前设计结论

- OpenCode v2 是 **OpenCode only** 的产品路径。
- WorkflowProgram 自身加载形式与生成目标工作流加载形式必须严格分层。
- v1 采用 `source-as-deployment-source` 模式，不以前置构建产物为设计前提。
- 新项目体验采用“全局轻量 bootstrap + 用户级 cache + project-local materialization”，不采用完整全局安装。
- AI 协作由 OpenCode package agents 承担，Python runtime 负责确定性固化、校验和写入。
- `/wp-develop` 的 S1 不是泛澄清；必须形成需求逻辑访谈证据，包括 `question-backlog.json`、`requirement-logic-map.json` 和 S2/S3 handoff。
- `/wp-clean` 只做维护清理，不作为 workflow 执行证据；默认 dry-run，必须保护 workflow design、project-local package、managed manifest 和 active bootstrap cache。
- 产品包命令与产品包插件属于 package contract。
- 目标工作流的 commands / skills / agents / plugins 是否生成，属于 target bundle contract。
- 后续能力补齐以 OpenSpec change 为实施真源，先按 capability 边界拆分，再进入具体代码实现。
