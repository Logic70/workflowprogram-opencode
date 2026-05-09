# WorkflowProgram for OpenCode

WorkflowProgram 的 OpenCode 独立版本。

这个仓库提供一套面向 OpenCode 的本地产品包，核心能力包括：

- `/wp-develop`：为当前项目生成目标工作流
- `/wp-doctor`：诊断 package、Python、OpenCode CLI 和当前项目可用状态
- `/wp-clean`：安全清理当前项目中的 Python cache、测试 cache 和可选历史 runs，不删除 workflow 设计或安装包
- `/wp-preflight`：在不修改项目的情况下做运行前检查，适合在 hotfix、evolve、ship 或提交前确认环境、spec、目标产物和宿主加载没有明显阻塞
- `/wp-hotfix`：对已有目标工作流做受控热修
- `/wp-iterate`：基于用户反馈或前次运行上下文做小步增量调整，适合修正文案、阶段、命令参数或局部生成结果
- `/wp-audit`：只读审计 package、target bundle、run-state、host 诊断和 lessons 证据
- `/wp-evolve`：基于已有 workflow、审计结果或 lessons 做版本化演进，适合较系统的能力升级或结构调整，写入仍走 managed apply
- `/wp-orchestrate`：根据自然语言请求给出推荐 `/wp-*` 入口，默认不自动执行变更型 intent
- `/wp-ship`：交付前最终检查，不新增功能；汇总验证、审计、host 加载和交付清单，判断当前目标工作流是否适合提交或发布
- `/wp-validate`：对 package、spec、target bundle、run-state 做分层校验
- package agent pack：WorkflowProgram 随包安装的 OpenCode 角色定义，例如 `@workflow-designer`、`@workflow-validator`、`@workflow-verifier`、`@logic-reviewer`、`@security-reviewer`、`@performance-reviewer`、`@style-reviewer`、`@test-scenario-generator`
- `project-local` 安装
- 全局轻量 bootstrap：`/wp-install`、`/wp-status`、`/wp-upgrade`、`/wp-uninstall`
- 可选 package 专用 Python `venv`
- runtime smoke、真实 OpenCode package host integration smoke、target host reload smoke
- 设计源血缘：`design_refs`、S1/S2/S3 设计源、acceptance tests、traceability matrix 与 S5 结构校验
- 需求逻辑访谈：S1 生成 `question-backlog.json`、`requirement-logic-map.json`，按七个 logic lenses 校验澄清深度
- 节点循环策略：`nodes[*].loop_policy`、`node_loop_execution` capability、loop prompt package 与 loop evidence 校验
- controlled change policy：`/wp-evolve`、`/wp-iterate`、`/wp-hotfix` 在写入前校验变更请求、确认状态、base spec hash 和声明写入范围

它不是 ClaudeCode 版的兼容层，也不是从 Claude 版复制后简单替换路径的 adapter。这里的目标是维护一个 **OpenCode only** 的独立实现。

## 仓库结构

```text
.
├── package/
│   ├── opencode.json
│   ├── .opencode/
│   │   ├── commands/
│   │   ├── agents/
│   │   └── plugins/
│   └── .workflowprogram/
│       └── runtime/
├── design/
├── INSTALL_WITH_OPENCODE.md
└── CHANGELOG.md
```

- `package/`
  - 可安装的 WorkflowProgram deployment source
- `design/`
  - HighLevel / LowLevel / Validation Matrix / 实施计划
- `INSTALL_WITH_OPENCODE.md`
  - 给 OpenCode 读取并按步骤执行的安装说明

## 依赖

- OpenCode
- Python 3
- `PyYAML`

推荐安装方式是使用 package 自带的 `venv`，这样不需要你手工安装 Python 依赖到系统环境。

## 安装

### 方式一：让 OpenCode 读取安装说明执行安装

推荐。

在 OpenCode 中输入：

```text
请读取 <repo-root>/INSTALL_WITH_OPENCODE.md，并严格按默认步骤安装 WorkflowProgram。
```

安装说明的默认路径是：先安装或确认全局轻量 bootstrap，然后在当前项目中执行 `/wp-install` 完成 project-local 部署。这样以后每个新项目只需要打开 OpenCode 后执行 `/wp-install`。

### 方式二：手动安装全局轻量 bootstrap 后在项目中部署

先执行一次：

```bash
python3 <repo-root>/package/.workflowprogram/runtime/package-deploy.py install-bootstrap --source-package-root <repo-root>/package --force
```

然后在任意新项目中打开 OpenCode，执行：

```text
/wp-install
```

这个全局 bootstrap 只负责部署当前项目，不会把完整 `/wp-develop`、agents 或 package plugin 全局安装。完整 WorkflowProgram 仍会被物化到当前项目的 `.opencode/*` 和 `.workflowprogram/package/*`。

可检查全局 bootstrap：

```bash
python3 <repo-root>/package/.workflowprogram/runtime/package-deploy.py bootstrap-status
```

### 方式三：直接执行项目本地安装脚本

在目标项目中执行：

```bash
python3 <repo-root>/package/.workflowprogram/runtime/package-deploy.py install --mode project-local --create-venv --python python3 --source-package-root <repo-root>/package --target-root <target-project-root>
```

Windows 示例：

```bash
python D:\Code\workflowprogram-opencode\package\.workflowprogram\runtime\package-deploy.py install --mode project-local --create-venv --python python --source-package-root D:\Code\workflowprogram-opencode\package --target-root D:\Code\your-project
```

安装后检查：

```bash
python3 <repo-root>/package/.workflowprogram/runtime/package-deploy.py status --mode project-local --target-root <target-project-root>
```

`status` 中有两个需要分开看的字段：

- `project_package_installed`：当前项目是否已安装 WorkflowProgram 产品包。
- `target_workflow_exists`：当前项目是否已有生成的目标工作流，只以 `.workflowprogram/design/workflow-spec.yaml` 为准。

这种方式适合一次性安装、CI 或不想使用全局 bootstrap 的场景；日常新项目推荐方式一或方式二。

## 使用

安装完成后，在目标项目根目录打开 OpenCode。

命令列表里应出现：

- `/wp-develop`
- `/wp-doctor`
- `/wp-clean`
- `/wp-preflight`
- `/wp-hotfix`
- `/wp-iterate`
- `/wp-audit`
- `/wp-evolve`
- `/wp-orchestrate`
- `/wp-ship`
- `/wp-validate`

可用 package agents：

- `@workflow-designer`
- `@workflow-validator`
- `@workflow-verifier`
- `@logic-reviewer`
- `@security-reviewer`
- `@performance-reviewer`
- `@style-reviewer`
- `@test-scenario-generator`

package agents 是 WorkflowProgram 随包安装到 `.opencode/agents/*.md` 的 OpenCode 角色定义。它们用于设计、校验、验证和专项评审，可以被 WorkflowProgram 的编排逻辑引用，也可以由用户按 OpenCode 的方式显式 `@` 调用。它们不是 agentteam 本身；agentteam 是运行时生成的团队计划和阶段职责，package agent 是其中可被调用的单个执行角色。

推荐入口策略：natural-language workflow request 先使用 `/wp-orchestrate`，由它判断应该 develop、validate、preflight、hotfix、iterate、ship、audit 还是 evolve。直接执行 `/wp-develop`、`/wp-evolve`、`/wp-hotfix`、`/wp-iterate` 属于显式专家入口，适合你已经明确生命周期阶段、已有接受设计、并准备让 runtime 进入校验和写入链路的场景。

`/wp-develop`、`/wp-evolve`、`/wp-hotfix`、`/wp-iterate` 的正常路径是 OpenCode host/model 先完成设计回读，形成 `workflow-spec.md` 和已接受的 `workflow-spec.yaml`；Python runtime 只负责读取该 spec、生成 target bundle、执行 managed apply 与验证。agentteam planner 只是可选调度建议，不是成功条件。

对已有目标工作流的修改还会经过 controlled change policy。`/wp-evolve`、`/wp-iterate`、`/wp-hotfix` 会在 managed apply 前记录 `RUN_ROOT/outputs/change-policy/change-context.json` 和 `change-policy-summary.json`，校验具体变更请求、用户确认、当前 base spec hash、候选文件是否落在声明写入范围内。这个门禁解决的是“语义授权”，managed apply 继续负责真实文件冲突和回滚证据。

`/wp-develop` 默认是对话式入口。OpenCode 应先询问目标对象、交付物、工具边界、graph 形态、自迭代、目标 CLI command 和 OpenCode plugin hook 等问题，并在你确认设计回读后才执行 runtime 生成目标工作流；未确认时 runtime 只会返回阻塞问题，不会写入目标 `.workflowprogram/design/workflow-spec.yaml`。package agent 证据只能辅助设计，不能替代用户确认。

S1 不是泛泛问“输入输出和边界”。OpenCode 版会按 `purpose`、`object_model`、`process_model`、`decision_model`、`evidence_model`、`acceptance_model`、`boundary_model` 七个 logic lenses 形成需求逻辑访谈证据。就绪的 develop run 会留下 `RUN_ROOT/outputs/clarification/question-backlog.json`、`RUN_ROOT/outputs/clarification/requirement-logic-map.json`，并镜像到 `RUN_ROOT/outputs/stages/` 供 S5 校验；只有泛问题或澄清轮次不足的 draft 会被 `validate-workflow-draft.py` 拦截。

运行时会在 `RUN_ROOT/outputs/team-plan.json` 和 `RUN_ROOT/outputs/team-plan.md` 生成 agentteam 调度建议。这个文件只是调度指南，不代表 subagent 已经执行；只有 OpenCode 实际调用 `@workflow-designer` 等 agent 并留下响应或调度记录后，才能认为该 agent 参与了运行。`--ai-evidence` 仅保留为 legacy 诊断字段，不能作为设计已发生或可写入目标的验收证据。

典型流程：

1. 执行 `/wp-develop <你的需求>`，先回答澄清问题并确认设计回读，再让它生成目标工作流
2. 需要先诊断环境时执行 `/wp-doctor`
3. 需要清理本地缓存或历史 runs 时执行 `/wp-clean`；默认 dry-run，不会删除文件
4. 在准备 hotfix、evolve、ship 或提交前，想先做不写文件的运行前检查时执行 `/wp-preflight`
5. 对已有工作流做明确缺陷修复时执行 `/wp-hotfix`
6. 对已有工作流做小步反馈迭代时执行 `/wp-iterate`
7. 需要基于审计或 lessons 做较系统的版本化演进时执行 `/wp-evolve`
8. 需要只读审计时执行 `/wp-audit`
9. 不确定该用哪个入口时执行 `/wp-orchestrate`
10. 准备提交或发布当前目标工作流前执行 `/wp-ship`
11. 需要分层校验当前状态时执行 `/wp-validate`

## 清理策略

`/wp-clean` 用于当前项目维护，默认只生成清理计划和 `.workflowprogram/maintenance/clean-report.md`。只有显式传入 `--yes` 才删除。

- 安全清理：`/wp-clean --pycache --yes` 或 `/wp-clean --all-safe --yes` 清理 `__pycache__`、`*.pyc`、`.pytest_cache`。
- 历史 runs：`/wp-clean --runs --keep-last 20 --yes` 或 `/wp-clean --runs --older-than 30d --yes` 只清理符合策略的旧 run。
- 需要确认：`--dist`、`--node-modules`、`--runs` 都不会默认执行删除。
- 永久保护：`.workflowprogram/design/`、`.workflowprogram/package/`、`.workflowprogram/runtime/`、`.workflowprogram/managed-files.json`、install manifest、最新 run 和 running run。
- bootstrap cache 清理不走 `/wp-clean`，使用 deploy 层：`package-deploy.py clean-bootstrap-cache --keep-last 2 --yes`。该命令会保护当前 bootstrap manifest 指向的 active cache。

## Doctor 常见结果

- `DOC-04` 失败
  - 说明当前 Python 环境缺少 `PyYAML`，优先重新安装并使用 `--create-venv`
- `DOC-05` 失败
  - 说明当前 shell 里没有可用的 `opencode` CLI，OpenCode 宿主集成无法验证
- `DOC-06` 失败
  - 说明当前项目目录不可写，`develop/hotfix/iterate` 这类写入型命令无法正常工作
- `DOC-07` 失败
  - 说明当前项目还没有生成目标工作流，先执行 `/wp-develop`
- `DOC-08` 失败
  - 说明存在命令、agent、skill 或 plugin 命名遮蔽风险，通常来自全局 OpenCode 配置、Claude 目录或 oh-my-opencode
- `DOC-10` 失败
  - 说明 OpenCode 版本或 CLI 探测异常，需要检查当前 shell 中的 `opencode --version`
- `DOC-11`
  - 提示安装或更新 plugin 后，如果命令/hook 行为没有刷新，需要重启 OpenCode 或重新打开项目

## 安装后的目录布局

`project-local` 安装后，目标项目中会出现：

```text
<target-project-root>/
├── .opencode/
│   ├── commands/
│   │   ├── wp-develop.md
│   │   ├── wp-doctor.md
│   │   ├── wp-clean.md
│   │   ├── wp-preflight.md
│   │   ├── wp-hotfix.md
│   │   ├── wp-iterate.md
│   │   ├── wp-audit.md
│   │   ├── wp-evolve.md
│   │   ├── wp-orchestrate.md
│   │   ├── wp-ship.md
│   │   └── wp-validate.md
│   └── plugins/
│       └── workflowprogram.ts
└── .workflowprogram/
    └── package/
        ├── install-manifest.json
        ├── .venv/                  # optional
        └── runtime/
```

注意：

- package runtime 位于 `.workflowprogram/package/runtime/`
- 生成的目标工作流 runtime 位于 `.workflowprogram/runtime/`
- 这两个路径是刻意隔离的，避免产品包和生成物互相覆盖
- 生成的目标工作流存在性只以 `.workflowprogram/design/workflow-spec.yaml` 为准；`.workflowprogram/package/*`、`.workflowprogram/runtime/*` 或 `.workflowprogram/runs/*` 单独存在时不能作为 evolve/iterate/hotfix/ship 的依据

## 当前状态

目前已经完成并验证：

- package 部署与卸载
- `project-local` 安装
- 可选 `venv` 创建与依赖安装
- runtime 级 `develop -> validate` 闭环
- package/spec/target/run-state 分层校验
- audit/evolve/orchestrate 产品 intent 契约
- agent role metadata 与 team-plan evidence
- managed apply lock 与 rollback manifest
- clean release package build
- design lineage 与 node loop policy 契约
- controlled change policy：hotfix/iterate/evolve 在写入前校验变更请求、确认状态、base spec hash 和声明写入范围
- entry exposure contract：`/wp-orchestrate` 是自然语言推荐入口，直接 `/wp-*` 是专家入口

本地验证过：

- `py_compile`
- source package validator
- `install -> status -> develop -> validate -> uninstall`
- `--create-venv` 下的 `PyYAML` 导入与 runtime 执行
- develop 设计流回归，包括 `design_refs`、traceability、node loop evidence 和缺失 `node_loop_execution` 的失败用例
- change-policy 回归，包括空变更请求、过期 base spec、未声明写入范围、合法 evolve 和入口暴露文档检查

当前仓库已经有真实 OpenCode 宿主的自动化集成 smoke，但它和 runtime smoke 的含义不同。runtime smoke 追求确定性闭环；host integration smoke 会真实调用 `opencode run --command ...`，因此在 provider/API 未就绪时允许返回 `ENVIRONMENT-SKIP`，而不是假装通过。
当前已经补上四类 smoke：

- `runtime smoke`
  - 直接调用 Python runtime，验证 `install -> develop -> preflight -> hotfix -> iterate -> audit -> evolve -> orchestrate -> ship -> validate`
- `host integration smoke`
  - 真实调用 `opencode run --command ...`
  - 检查 OpenCode CLI、package commands、package plugin、命令发现、以及运行时是否真正进入 bash/tool 阶段
  - 在 provider/API 未就绪时允许返回 `ENVIRONMENT-SKIP`
- `target host reload smoke`
  - 检查已生成 target command/plugin 的静态可见性
  - 真实 OpenCode 可用时尝试通过 target command 进入目标 runtime
  - provider/API 不可用时只返回 `ENVIRONMENT-SKIP`，不伪造 `PASS`
- `global bootstrap smoke`
  - 验证 `install-bootstrap -> bootstrap-status -> bootstrap-runtime install -> bootstrap-runtime status`
  - 保证全局只安装部署器，完整 package 仍安装到项目本地

手工运行 host integration smoke：

```bash
python3 package/.workflowprogram/runtime/host-integration-smoke.py --package-root <installed-project-root> --target-root <installed-project-root> --timeout-seconds 15 --json
```

手工运行 target host reload smoke：

```bash
python3 package/.workflowprogram/runtime/target-host-smoke.py --target-root <target-project-root> --timeout-seconds 15 --json
```

构建干净 release 包：

```bash
python3 tools/build_package.py --source-package-root package --output-root dist/opencode --clean --json
```

结果解释：

- `PASS`
  - 宿主加载、命令发现和运行链都通过
- `ENVIRONMENT-SKIP`
  - 宿主层至少已确认 CLI、package commands、package plugin 可见，但 provider/API 或执行阶段未在超时窗口内进入 runtime
- `FAIL`
  - 更偏向结构或集成问题，例如 commands/plugin 未被宿主发现

## 设计文档

- [设计索引](./design/index.md)
- [ClaudeCode 到 OpenCode 适配通用指南（GitHub Pages）](https://logic70.github.io/workflowprogram-opencode/claudecode-to-opencode-adaptation.html)
- [ClaudeCode 到 OpenCode 适配通用指南（仓库内 HTML）](./design/claudecode-to-opencode-adaptation.html)
- [HighLevel 设计](./design/opencode-v2-highlevel-design.md)
- [LowLevel 设计](./design/opencode-v2-lowlevel-design.md)
- [Validation Matrix](./design/opencode-v2-validation-matrix.md)
- [实施计划](./design/opencode-v2-implementation-plan.md)

## 和 ClaudeCode 版的关系

这个仓库保留了 WorkflowProgram 的核心思路：

- `spec-first`
- AI/user graph design + Python validation/apply
- `RUN_ROOT`
- managed apply
- runner / layered validation

但 OpenCode 的入口模型、安装布局、插件边界和运行时调用方式都是独立设计的。

## License

Apache-2.0. See [LICENSE](./LICENSE).
