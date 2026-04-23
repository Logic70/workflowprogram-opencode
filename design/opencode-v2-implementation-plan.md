# OpenCode V2 实施计划

## 1. 目的与范围

本文档基于以下三份当前真源：

- `opencode-v2-highlevel-design.md`
- `opencode-v2-lowlevel-design.md`
- `opencode-v2-validation-matrix.md`

目标是把 OpenCode v2 从“设计成立”推进到“最小可运行产品包成立”，并确保实施顺序与契约分层一致。

本文档只规划 v1：

- OpenCode only
- `source-as-deployment-source`
- package command + package plugin + runtime 主链
- 安装脚本生成宿主可发现布局
- target bundle 生成、受控写入与分层校验

本文档不覆盖：

- Claude 兼容实现
- marketplace / npm 发布
- `dist/opencode/` 打包链
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

- target plugin 复杂模式
- target host-visible agents / skills 扩展
- packager / release 流程

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

## 8. 建议执行顺序

1. 完成 P1，先让 package 能被宿主识别
2. 完成 P2，先让 `/wp-develop` 能进入 runtime
3. 完成 P3，先生成最小 target design assets
4. 完成 P4，形成最小 target bundle 与 managed apply
5. 完成 P5，建立 `/wp-validate` 的分层校验能力
6. 完成 P6，建立 smoke 闭环

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
