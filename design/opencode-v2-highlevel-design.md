# OpenCode V2 架构设计说明书（HighLevel设计）

## 简介
### 目的与范围

本文档定义 WorkflowProgram OpenCode v2 的高层架构，重点回答两个问题：

1. WorkflowProgram 自身如何作为 OpenCode 产品包被宿主加载。
2. WorkflowProgram 如何为目标项目生成并交付可运行的目标工作流。

本文档覆盖：

- 系统边界与上下文
- 分层契约模型
- 关键架构元素与逻辑接口
- 运行、通信、日志、校验、部署的高层方案

本文档不覆盖：

- Claude 版兼容设计
- marketplace / npm 发布流程
- 非 OpenCode 宿主适配
- 具体脚本参数与类字段的实现级细节

### 核心架构与关键需求

本系统有两条主链路。

**链路 A：产品包加载链**

- 输入：`WP_PACKAGE_ROOT`
- 处理：OpenCode 自动发现 package commands 与 package plugin
- 输出：WorkflowProgram 产品能力被宿主加载，用户可执行 `/wp-*` 命令

**链路 B：目标工作流生成链**

- 输入：用户需求、目标项目路径、执行约束
- 处理：需求澄清 -> 设计 -> 目标 bundle 生成 -> managed apply -> 验证 -> lessons
- 输出：`TARGET_ROOT/.opencode/*`、`TARGET_ROOT/.workflowprogram/*`、`RUN_ROOT/*`

关键需求列表如下：

| 编号 | 名称 | 描述 |
|---|---|---|
| AR-01 | 产品包可加载 | OpenCode 能稳定加载 WorkflowProgram 产品包 |
| AR-02 | 产品入口确定性 | WorkflowProgram 自身入口统一由 package commands 提供 |
| AR-03 | 契约分层清晰 | 产品包契约、工作流语义契约、目标交付契约、运行证据契约必须分层 |
| AR-04 | 目标工作流可生成 | 能为目标项目生成可运行的工作流 bundle |
| AR-05 | 写入受控 | 所有目标项目写入必须走 candidate + managed apply |
| AR-06 | 运行可回放 | 每次运行都必须产出最小证据集 |
| AR-07 | 包插件可扩展 | package plugin 支持 hook 与 custom tool |
| AR-08 | 校验分层 | package/spec/target/run-state 校验职责必须独立 |
| AR-09 | 名称空间隔离 | package commands / plugins 与 target commands / plugins 不得冲突 |
| AR-10 | 最小可安装 | v1 以 `package/` 作为部署源，通过安装脚本生成宿主可发现布局，不依赖额外构建产物 |

### 架构级原则与约束

系统必须长期遵守以下原则：

- `WorkflowProgram` 自身加载形式与目标工作流加载形式必须严格分层。
- `workflow-spec.yaml` 只描述目标工作流语义，不描述 WorkflowProgram 产品包自身。
- `WP_PACKAGE_ROOT`、`TARGET_ROOT`、`RUN_ROOT` 三个根路径的职责不可混用。
- WorkflowProgram 产品命令只能定义在 `WP_PACKAGE_ROOT/.opencode/commands/*.md`。
- `opencode.json.command` 不作为 WorkflowProgram 产品命令真源。
- WorkflowProgram package plugin 是 v1 必需资产，但 target workflow 是否生成 plugin 由目标 spec 决定。
- package plugin 与 target plugin 必须具备不同逻辑标识，避免 hook 与 tool 冲突。
- target commands 必须避免复用 `/wp-*` 产品命名空间。
- `project-local` 安装允许 package commands/plugins 与 target commands/plugins 共存于同一项目根，但 package runtime 必须位于 `.workflowprogram/package/runtime/`，不得与 target runtime 共用路径。
- package runtime 的 Python 依赖必须显式声明；v1 通过 `requirements.txt` 声明，并允许安装器创建 `.workflowprogram/package/.venv` 作为专用解释器。
- 任何运行时依赖的 validator 脚本都必须随 `WP_PACKAGE_ROOT` 一起交付，不得依赖仓库根目录中的额外源码。
- 所有目标写入必须先生成 candidate，再执行 managed apply。
- 所有运行态结论都必须能够由 `RUN_ROOT` 证据回放。
- validator 不能跨层检查不属于自己的契约。
- 设计优先保证边界清晰和可验证性，不优先追求抽象复用。

## 系统模型
### 上下文模型
#### 上下文图

```mermaid
graph LR
    U["用户"] --> H["OpenCode Host"]
    H --> P["WP_PACKAGE_ROOT\nWorkflowProgram 产品包"]
    P --> R["WorkflowProgram Runtime"]
    R --> T["TARGET_ROOT\n目标项目"]
    R --> E["RUN_ROOT\n运行证据"]
    T --> G["Generated Target Workflow\n目标工作流"]
    G --> H
```

#### 外部接口描述

| 接口名 | 提供者 | 使用者 | 协议/机制 | 功能描述 |
|---|---|---|---|---|
| Package Load Interface | OpenCode Host | WorkflowProgram 产品包 | 本地目录自动发现 | 加载 package commands 与 package plugin |
| Package Command Interface | WorkflowProgram 包 | 用户 | Markdown command | 提供 `/wp-develop`、`/wp-validate` 等产品入口 |
| Package Plugin Interface | WorkflowProgram 包 | OpenCode Host | `.opencode/plugins/*.ts` | 注册 hook/custom tool |
| Runtime Entry Interface | WorkflowProgram Runtime | Package Command | 本地脚本调用 | 承接产品命令后的确定性编排 |
| Target Bundle Delivery Interface | WorkflowProgram Runtime | TARGET_ROOT | 文件系统 + managed apply | 交付目标工作流 bundle |
| Target Runtime Interface | Generated Target Workflow | OpenCode Host | 必选 `.workflowprogram/runtime/*` + 条件性 `.opencode/*` | 目标工作流自身被宿主加载与运行 |
| Evidence Interface | WorkflowProgram Runtime | validator/judge | JSON/JSONL/Markdown 文件 | 输出 state、events、report、summary |

### 关键需求模型
#### KR-01 产品包加载

```mermaid
sequenceDiagram
    participant User
    participant Host as OpenCode Host
    participant Pkg as WorkflowProgram Package
    User->>Host: 启动 OpenCode
    Host->>Pkg: 扫描 opencode.json / .opencode/commands / .opencode/plugins
    Pkg-->>Host: 注册 commands 与 plugin
    Host-->>User: WorkflowProgram 产品能力可用
```

#### KR-02 `/wp-develop` 生成目标工作流

```mermaid
sequenceDiagram
    participant User
    participant Cmd as Package Command
    participant RT as WorkflowProgram Runtime
    participant Run as RUN_ROOT
    participant Target as TARGET_ROOT
    User->>Cmd: /wp-develop <target_root>
    Cmd->>RT: 调用 workflow-entry
    RT->>Run: 初始化 context/state/events
    RT->>RT: 需求澄清与 workflow spec 生成
    RT->>Target: 生成 candidate target bundle
    RT->>Target: 执行 managed apply
    RT->>Run: 记录 validation / lessons
    RT-->>User: 返回执行摘要
```

#### KR-03 目标工作流被宿主加载

```mermaid
sequenceDiagram
    participant Host as OpenCode Host
    participant Target as TARGET_ROOT
    participant GW as Generated Target Workflow
    Host->>Target: 扫描 .opencode/* 与 .workflowprogram/runtime/*
    Target->>GW: 注册 target commands/agents/skills/plugins
    GW-->>Host: 目标工作流可用
```

#### KR-04 校验分层

```mermaid
sequenceDiagram
    participant CI as CI/Runtime
    participant PV as Package Validator
    participant SV as Spec Validator
    participant TV as Target Bundle Validator
    participant RV as Run-State Validator
    CI->>PV: 校验产品包契约
    CI->>SV: 校验工作流语义契约
    CI->>TV: 校验目标交付契约
    CI->>RV: 校验运行证据契约
    PV-->>CI: package verdict
    SV-->>CI: spec verdict
    TV-->>CI: target bundle verdict
    RV-->>CI: run-state verdict
```

## 系统架构设计模型
### 逻辑模型
#### 1层逻辑模型

```mermaid
graph TB
    A["产品包层\nPackage Layer"]
    B["设计控制层\nDesign Control Plane"]
    C["目标交付层\nTarget Bundle Layer"]
    D["证据与校验层\nEvidence & Validation Layer"]
    A --> B
    B --> C
    B --> D
    C --> D
```

#### 2层逻辑模型

```mermaid
graph TB
    A1["Package Commands"]
    A2["Package Plugin"]
    B1["Intent Router"]
    B2["Workflow Spec Engine"]
    B3["Target Bundle Generator"]
    B4["Managed Apply Engine"]
    C1["Target .opencode Assets"]
    C2["Target Runtime Wrapper"]
    C3["Target Design Assets"]
    D1["Package Validator"]
    D2["Spec Validator"]
    D3["Target Bundle Validator"]
    D4["Run-State Validator"]
    D5["Smoke Harness"]
    A1 --> B1
    A2 --> B1
    B1 --> B2
    B2 --> B3
    B3 --> B4
    B2 --> C3
    B4 --> C1
    B4 --> C2
    A1 --> D1
    A2 --> D1
    B2 --> D2
    C1 --> D3
    C2 --> D3
    C3 --> D3
    B4 --> D4
    D4 --> D5
```

#### 产品包契约（Package Contract）

产品包契约只约束 WorkflowProgram 自身被宿主加载的形式。

| 项目 | 规则 |
|---|---|
| 真源根路径 | `WP_PACKAGE_ROOT` |
| 真源命令目录 | `project-local`: `WP_PACKAGE_ROOT/.opencode/commands/`; `global`: `WP_PACKAGE_ROOT/commands/` |
| 真源插件目录 | `project-local`: `WP_PACKAGE_ROOT/.opencode/plugins/`; `global`: `WP_PACKAGE_ROOT/plugins/` |
| 真源运行时目录 | `WP_PACKAGE_ROOT/.workflowprogram/package/runtime/` |
| 部署源目录 | 仓库内 `package/.workflowprogram/runtime/` 作为安装源，不直接等同于已安装布局 |
| 产品命令命名空间 | `/wp-*` |
| 产品插件职责 | hook/custom tool/bridge |
| 产品命令定义位置 | 仅已安装 commands 目录中的 `wp-*.md` |
| 非真源位置 | `opencode.json.command` 不承载 WorkflowProgram 产品命令真源 |

#### 目标工作流交付契约（Target Bundle Contract）

目标交付契约只约束生成物如何被目标项目加载与运行。

| 项目 | 规则 |
|---|---|
| 目标根路径 | `TARGET_ROOT` |
| 目标命令目录 | `TARGET_ROOT/.opencode/commands/`（可选，由 target `workflow-spec.yaml` 决定是否生成） |
| 目标设计目录 | `TARGET_ROOT/.workflowprogram/design/` |
| 目标运行时目录 | `TARGET_ROOT/.workflowprogram/runtime/` |
| 目标写入方式 | candidate + managed apply |
| 目标插件策略 | 默认可选，由目标 `workflow-spec.yaml` 决定是否生成 |
| 目标命令命名 | 不得占用 `/wp-*` 产品命名空间 |
| 目标工作流真源 | `workflow-spec.yaml` 描述目标工作流语义与目标交付需求 |

#### 逻辑接口设计

| 接口名 | 提供者 | 使用者 | 功能描述 |
|---|---|---|---|
| `PackageCommand.Dispatch` | Package Commands | Intent Router | 接收用户产品入口并规范化参数 |
| `PluginBridge.Hook` | Package Plugin | Runtime / Host | 提供 hook 与 custom tool |
| `SpecEngine.Build` | Workflow Spec Engine | Target Bundle Generator | 生成机器可读工作流语义 |
| `TargetBundle.Emit` | Target Bundle Generator | Managed Apply Engine | 输出 target candidate bundle |
| `ManagedApply.Apply` | Managed Apply Engine | TARGET_ROOT | 受控应用候选资产 |
| `Validator.PackageCheck` | Package Validator | CI / Runtime | 校验 package contract |
| `Validator.SpecCheck` | Spec Validator | CI / Runtime | 校验 workflow semantics |
| `Validator.TargetCheck` | Target Bundle Validator | CI / Runtime | 校验 target bundle contract |
| `Validator.RunStateCheck` | Run-State Validator | CI / Runtime | 校验运行证据契约 |

#### 系统元素清单

| 元素名 | 功能描述 | 提供的逻辑接口 | 上级系统 |
|---|---|---|---|
| Package Commands | 提供 `/wp-*` 产品入口 | `PackageCommand.Dispatch` | 产品包层 |
| Package Plugin | 提供 hook/custom tool/bridge | `PluginBridge.Hook` | 产品包层 |
| Intent Router | 标准化 intent 和上下文 | `Route.Intent` | 设计控制层 |
| Workflow Spec Engine | 构建目标工作流语义 | `SpecEngine.Build` | 设计控制层 |
| Target Bundle Generator | 生成目标 bundle | `TargetBundle.Emit` | 设计控制层 |
| Managed Apply Engine | 管理 candidate/apply | `ManagedApply.Apply` | 设计控制层 |
| Package Validator | 校验产品包加载契约 | `Validator.PackageCheck` | 证据与校验层 |
| Spec Validator | 校验目标工作流语义契约 | `Validator.SpecCheck` | 证据与校验层 |
| Target Bundle Validator | 校验目标交付契约 | `Validator.TargetCheck` | 证据与校验层 |
| Run-State Validator | 校验运行证据契约 | `Validator.RunStateCheck` | 证据与校验层 |
| Smoke Harness | 运行最小真实链路验证 | `Smoke.Run` | 证据与校验层 |

### 技术模型
#### 运行框架

运行框架由三个根路径组成：

| 根路径 | 角色 | 说明 |
|---|---|---|
| `WP_PACKAGE_ROOT` | 已安装产品包根路径 | 被 OpenCode 直接加载的 WorkflowProgram 包 |
| `TARGET_ROOT` | 目标项目根路径 | 目标工作流最终落地位置 |
| `RUN_ROOT` | 运行证据根路径 | 存放 state / events / reports / outputs |

运行框架规则：

- OpenCode 只直接加载 `WP_PACKAGE_ROOT` 或 `TARGET_ROOT` 中的 OpenCode 资产。
- WorkflowProgram package runtime 在部署后位于 `WP_PACKAGE_ROOT/.workflowprogram/package/runtime/`。
- 目标工作流 runtime wrapper 位于 `TARGET_ROOT/.workflowprogram/runtime/`。
- WorkflowProgram package plugin 与 target workflow plugin 不能共享文件名、逻辑 id 或职责。

#### 通信框架

通信仅允许使用下列机制：

| 通信方向 | 机制 |
|---|---|
| 用户 -> Package Command | OpenCode Markdown command |
| Package Command -> Runtime | 本地脚本调用 |
| Package Plugin -> Host | 本地插件自动加载 |
| Runtime -> Target Bundle | 文件系统 candidate 生成 |
| Runtime -> Managed Apply | plan/result 文件契约 |
| Runtime -> Validators | JSON/YAML/Markdown 文件契约 |
| Validators -> 用户 | Markdown/JSON 报告 |

#### OM框架

生命周期、日志、状态管理统一采用：

- 生命周期：package load -> intent dispatch -> stage execution -> validate -> lessons
- 状态快照：`RUN_ROOT/state.json`
- 事件日志：`RUN_ROOT/events.jsonl`
- 阶段总结：`RUN_ROOT/outputs/stages/*.json`
- 进展摘要：`RUN_ROOT/outputs/progress/*`
- Lessons：`RUN_ROOT/outputs/stages/s6-lessons-delta.md`

#### 接口实现机制

| 机制名 | 机制说明 | 使用实例 |
|---|---|---|
| Markdown Command | OpenCode 用户入口机制 | `/wp-develop`、`/wp-validate` |
| Local Plugin Auto Load | OpenCode 本地插件机制 | `workflowprogram.ts` |
| File Contract | 用文件传递控制面语义和运行结果 | `workflow-spec.yaml`、`managed-files.json` |
| Managed Apply | 防止静默覆盖的受控写入机制 | candidate -> plan -> apply |
| Run Evidence | 把运行过程结构化落盘 | `state.json`、`events.jsonl` |
| Layered Validation | 不同 validator 校验不同契约层 | package/spec/target/run-state |

### 数据模型
#### 静态数据模型

```mermaid
erDiagram
    PACKAGE_CONTRACT ||--o{ PACKAGE_COMMAND : contains
    PACKAGE_CONTRACT ||--|| PACKAGE_PLUGIN : contains
    WORKFLOW_SPEC ||--o{ TARGET_ASSET : defines
    TARGET_BUNDLE ||--o{ TARGET_ASSET : contains
    RUN_CONTEXT ||--|| RUN_STATE : owns
    RUN_CONTEXT ||--o{ RUN_EVENT : records
    RUN_CONTEXT ||--o{ VALIDATION_REPORT : produces
```

#### 数据所有权模型

| 数据实体 | 所有者 | 读 | 写 | 无权限 |
|---|---|---|---|---|
| Package Contract | 产品包层 | Host / Package Validator | package builder | target runtime |
| Workflow Spec | Workflow Spec Engine | generator / Spec Validator | spec engine | package loader |
| Target Bundle | Target Bundle Generator | target validator / target runtime | generator / apply engine | package loader |
| Managed Manifest | Managed Apply Engine | runtime / validator | apply engine | package loader |
| Run State | Runtime Orchestrator | validators / judge | runtime | package loader |
| Validation Report | Validation Layer | user / runtime | validators | package loader |

### 代码模型

建议工程路径如下：

```text
opencode-v2/
├── design/
│   ├── opencode-v2-highlevel-design.md
│   ├── opencode-v2-lowlevel-design.md
│   └── opencode-v2-validation-matrix.md
├── package/
│   ├── opencode.json
│   ├── .opencode/
│   │   ├── commands/
│   │   ├── plugins/
│   │   ├── agents/      # optional
│   │   └── skills/      # optional
│   └── .workflowprogram/
│       └── runtime/
│           └── validators/
│               ├── package_contract_validator.py
│               ├── workflow_spec_validator.py
│               ├── target_bundle_validator.py
│               └── run_state_validator.py
└── tests/
```

### 构建模型

v1 采用 `source-as-deployment-source` 模式。

| 项目 | 结论 |
|---|---|
| `dist/opencode/` | 非 v1 前置项 |
| `build_opencode.py` | 非 v1 前置项 |
| 仓库内 `package/` 是否作为部署源 | 是，且必须自包含 runtime 与 validator |
| 是否需要安装器生成宿主可发现布局 | 是 |
| package 是否必须有 plugin metadata | 否 |

### 交付部署模型

推荐支持两种产品包部署模式：

| 模式 | 路径 | 用途 |
|---|---|---|
| project-local | `PROJECT_ROOT/.opencode/{commands,plugins}` + `PROJECT_ROOT/.workflowprogram/package/runtime/` | 当前项目内安装与直接使用 |
| global | `GLOBAL_ROOT/{commands,plugins}` + `GLOBAL_ROOT/.workflowprogram/package/runtime/` | 全局安装，供多个项目复用 |

安装规则：

- 安装器只部署 WorkflowProgram 产品命令、产品插件和 package runtime。
- `project-local` 安装允许 package commands/plugins 与后续生成的 target commands/plugins 共存于同一项目根目录。
- package runtime 固定落在 `.workflowprogram/package/runtime/`，用于与 target `.workflowprogram/runtime/` 做路径隔离。
- package runtime 依赖通过 `.workflowprogram/package/runtime/requirements.txt` 声明；安装器可选创建 `.workflowprogram/package/.venv`，并在 install manifest 中记录 `python_executable`。
- 安装器以保守合并策略更新 `opencode.json`，并写出 install manifest 以支持状态检查和卸载。

目标工作流只允许一种交付模型：

- 必选：交付到 `TARGET_ROOT/.workflowprogram/*`
- 可选：按 target spec 交付到 `TARGET_ROOT/.opencode/*`

目标工作流部署与产品包部署必须逻辑独立：

- 部署 WorkflowProgram 产品包，不代表自动部署目标工作流
- 生成目标工作流，不得回写 WorkflowProgram 产品包目录
