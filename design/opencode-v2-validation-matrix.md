# OpenCode V2 Validation Matrix

## 1. 目的与范围

本矩阵用于把 OpenCode v2 的校验职责分层收口，避免以下问题：

- package validator 去检查 target workflow 语义
- spec validator 去检查 WorkflowProgram 产品包加载形式
- target validator 去检查 `RUN_ROOT` 运行证据
- run-state validator 去推断 package contract

本矩阵把校验分为四类：

1. `Package Validator`
2. `Workflow Spec Validator`
3. `Target Bundle Validator`
4. `Run-State Validator`

另有一个补充层：

5. `Smoke Harness`

## 2. 校验边界总表

| 校验层 | 校验对象 | 主要输入 | 主要输出 | 不负责 |
|---|---|---|---|---|
| Package Validator | `WP_PACKAGE_ROOT` | `opencode.json`、已安装 commands/plugins 目录、对应 runtime `validators/` | package verdict | target bundle、run-state |
| Workflow Spec Validator | `workflow-spec.yaml` | 语义 spec | spec verdict | package load、plugin auto-load |
| Target Bundle Validator | `TARGET_ROOT` 交付物 | `.workflowprogram/*`、条件性 `.opencode/*` | target verdict | package contract、runtime event 语义 |
| Run-State Validator | `RUN_ROOT` | `state.json`、`events.jsonl`、reports | run-state verdict | package 结构、spec schema |
| Smoke Harness | 真实最小链路 | package + target + runtime | smoke verdict | 替代静态 validator |

## 3. Package Validator 检查项

| ID | 检查项 | 输入 | 规则 | 失败分类 |
|---|---|---|---|---|
| PKG-01 | package root 存在 | `WP_PACKAGE_ROOT` | 根目录必须存在 | package_structure |
| PKG-02 | `opencode.json` 存在 | `WP_PACKAGE_ROOT/opencode.json` | 必需文件存在 | package_structure |
| PKG-03 | package command 目录存在 | `project-local .opencode/commands/` 或 `global commands/` | 已安装 package 的命令目录必须存在 | package_structure |
| PKG-04 | WorkflowProgram package plugin 存在 | `.opencode/plugins/workflowprogram.ts` | 必需文件存在 | package_structure |
| PKG-05 | 产品命令命名空间正确 | 已安装 commands 目录中的 `wp-*.md` | WorkflowProgram 产品命令必须保留在 `wp-*` 命名空间 | package_contract |
| PKG-06 | 产品命令真源位置正确 | 已安装 commands 目录 + `opencode.json.command` | WorkflowProgram 产品命令必须以文件方式存在，且不得仅通过 `opencode.json.command` 提供 | package_contract |
| PKG-07 | 产品命令真源唯一 | `wp-*.md` 与 `opencode.json.command` | WorkflowProgram 同名产品命令不能双写 | package_contract |
| PKG-08 | plugin metadata 非必需 | `.opencode/plugins/` | 不要求 `plugin.json` / `marketplace.json` | none |
| PKG-09 | runtime 根目录存在 | `source .workflowprogram/runtime/` 或 `deployed .workflowprogram/package/runtime/` | 主运行脚本目录必须存在 | package_structure |
| PKG-10 | runtime validators 自包含 | `*/validators/` | 可部署 package 必须自包含 validator 脚本 | package_structure |
| PKG-11 | package 与 target 标识隔离 | 命令名、插件文件名、插件逻辑标识 | 不得与 target 命名策略冲突 | namespace_conflict |
| PKG-12 | package agents 目录存在 | `project-local .opencode/agents/` 或 `global agents/` | 已安装 package 的 agents 目录必须存在 | package_structure |
| PKG-13 | package agents 完整 | 已安装 agents 目录中的 `*.md` | v1 必需 agent 集必须齐全 | package_contract |

## 4. Workflow Spec Validator 检查项

| ID | 检查项 | 输入 | 规则 | 失败分类 |
|---|---|---|---|---|
| SPEC-01 | spec 可解析 | `workflow-spec.yaml` | YAML 可解析 | design |
| SPEC-02 | 必需键存在 | `meta`、`stages`、`intent_flows` 等 | 关键字段必须齐全 | design |
| SPEC-03 | stage flow 合法 | `intent_flows` | 必须引用已定义 stage | design |
| SPEC-04 | failure kind 合法 | `runtime_contract.failure_kinds` | 必须来自允许枚举 | design |
| SPEC-05 | write boundaries 合法 | `runtime_contract.write_boundaries` | 边界规则必须完整 | design |
| SPEC-06 | target deliverables 可推导 | registry / outputs | spec 必须能推导目标交付物 | design |
| SPEC-07 | target plugin 语义可选 | target plugin 配置 | 未声明时不得被强制要求 | design |
| SPEC-08 | 不含 package contract 字段 | spec 全文 | 不得写入 WorkflowProgram package 自身加载规则 | layering |
| SPEC-09 | target command 不占用 `/wp-*` | target command 定义 | 不得与产品命名空间冲突 | namespace_conflict |

## 5. Target Bundle Validator 检查项

| ID | 检查项 | 输入 | 规则 | 失败分类 |
|---|---|---|---|---|
| TGT-01 | target 设计目录存在 | `.workflowprogram/design/` | 必需目录存在 | bundle_structure |
| TGT-02 | target runtime 目录存在 | `.workflowprogram/runtime/` | 必需目录存在 | bundle_structure |
| TGT-03 | target bundle 与 spec 对齐 | target assets + spec | 交付物必须与 spec 一致 | bundle_mismatch |
| TGT-04 | target managed manifest 合法 | `.workflowprogram/managed-files.json` | 文件存在且结构合法 | bundle_state |
| TGT-05 | target command 命名合法 | `.opencode/commands/*.md` | 若生成 target commands，则不得占用 `/wp-*` 命名空间 | namespace_conflict |
| TGT-06 | target command 仅在 spec 要求时检查 | `.opencode/commands/*` | spec 未要求时不得强制失败 | bundle_policy |
| TGT-07 | target plugin 仅在 spec 要求时检查 | `.opencode/plugins/*` | spec 未要求则不得强制失败 | bundle_policy |
| TGT-08 | target plugin 标识隔离 | target plugin 文件名、逻辑标识 | 若生成 target plugin，不得与 package plugin 冲突 | namespace_conflict |
| TGT-09 | runtime wrapper 文件存在 | `.workflowprogram/runtime/*` | wrapper 必需文件齐全 | bundle_structure |

## 6. Run-State Validator 检查项

| ID | 检查项 | 输入 | 规则 | 失败分类 |
|---|---|---|---|---|
| RUN-01 | `context.json` 存在 | `RUN_ROOT` | 必需证据存在 | evidence_missing |
| RUN-02 | `state.json` 存在 | `RUN_ROOT` | 必需证据存在 | evidence_missing |
| RUN-03 | `events.jsonl` 存在 | `RUN_ROOT` | 必需证据存在 | evidence_missing |
| RUN-04 | 阶段 summary 存在 | `outputs/stages/*.json` | 至少有阶段级摘要 | evidence_missing |
| RUN-05 | verdict 合法 | `state.json` / report | verdict 必须在允许枚举内 | state_invalid |
| RUN-06 | failure_kind 合法 | `state.json` / report | failure_kind 必须在允许枚举内 | state_invalid |
| RUN-07 | 证据链闭合 | state / events / report | run-id、intent、target_root 必须可互相对应 | evidence_inconsistent |
| RUN-08 | 进展资产存在 | `outputs/progress/*` | 最小进展证据齐全 | evidence_missing |
| RUN-09 | diagnostics 资产存在 | `outputs/diagnostics/*` | host capabilities、probe、doctor、remediation 必须齐全 | evidence_missing |
| RUN-10 | diagnostics 内容合法 | diagnostics JSON/MD | diagnostics 必须包含最小字段集 | evidence_inconsistent |
| RUN-11 | clarification 资产存在 | `outputs/clarification/*` | `develop` 运行必须落 clarification package | evidence_missing |
| RUN-12 | clarification 内容合法 | clarification JSON/MD | clarification package 必须包含 record、questions、readiness、assumption log | evidence_inconsistent |

## 7. Smoke Harness 检查项

| ID | 场景 | 目标 | 通过条件 |
|---|---|---|---|
| SMK-01 | install + package load smoke | 部署后产品包能被宿主发现 | 已安装 package commands 与 plugin 可见，runtime 路径正确 |
| SMK-02 | `/wp-develop` smoke | 产品命令可进入 runtime | 进入 `workflow-entry.py` 主链 |
| SMK-03 | generate smoke | 能生成 target candidate bundle | candidate 目录完整 |
| SMK-04 | managed apply smoke | 能安全写入目标项目 | plan/result 正常，未静默覆盖 |
| SMK-05 | validation smoke | 能输出多层校验摘要 | validation summary 存在 |
| SMK-06 | host integration smoke | WorkflowProgram 产品包在真实 OpenCode 宿主中的最小可发现性成立 | package commands/plugin 至少可被宿主发现；若 provider/API 未就绪可返回 `ENVIRONMENT-SKIP` |

## 8. 需求到校验追踪矩阵

| 需求 | 对应检查 |
|---|---|
| AR-01 产品包可加载 | PKG-01 ~ PKG-04, PKG-12 ~ PKG-13, SMK-01 |
| AR-02 产品入口确定性 | PKG-05 ~ PKG-07, SMK-02 |
| AR-03 契约分层清晰 | SPEC-08, TGT-06 |
| AR-04 目标工作流可生成 | SPEC-06, TGT-01 ~ TGT-04, SMK-03 |
| AR-05 写入受控 | TGT-04, SMK-04 |
| AR-06 运行可回放 | RUN-01 ~ RUN-12 |
| AR-07 包插件可扩展 | PKG-04, PKG-08, SMK-01 |
| AR-08 校验分层 | 全矩阵 |
| AR-09 名称空间隔离 | PKG-11, SPEC-09, TGT-05, TGT-08 |
| AR-10 最小可安装 | PKG-01 ~ PKG-10, SMK-01 |

## 9. 建议执行顺序

静态校验顺序：

1. Package Validator
2. Workflow Spec Validator
3. Target Bundle Validator
4. Run-State Validator

动态校验顺序：

1. Package Load Smoke
2. `/wp-develop` Smoke
3. Generate / Apply Smoke
4. Target Load Smoke

## 10. 通过标准

v1 最小通过标准建议为：

- Package Validator: PASS
- Workflow Spec Validator: PASS
- Target Bundle Validator: PASS
- Run-State Validator: PASS
- Smoke Harness: 至少 `SMK-01 ~ SMK-04` PASS

若真实 OpenCode 环境不可用，可接受：

- 静态 validator 全 PASS
- smoke 标记为 `ENVIRONMENT-SKIP`
