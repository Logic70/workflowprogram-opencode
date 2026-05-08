# WorkflowProgram OpenCode 安装执行说明

本文档给 OpenCode 自身读取并执行，用于把 WorkflowProgram 安装到当前项目。

默认方案是先安装或确认全局轻量 bootstrap，然后在当前项目中执行 `/wp-install`。只有用户明确要求一次性项目本地安装时，才跳过 bootstrap，直接执行本文后面的 project-local 安装命令。

## 适用范围

- 当前工作目录就是目标项目根目录。
- WorkflowProgram 源包路径为：
  - Windows: `D:\Code\WorkflowProgram-CN\opencode-v2\package`
  - WSL/Linux: `/mnt/d/Code/WorkflowProgram-CN/opencode-v2/package`
- 默认目标是：全局只安装 `/wp-install`、`/wp-status`、`/wp-upgrade`、`/wp-uninstall`，完整 WorkflowProgram 仍安装到当前项目。
- 如果用户明确要求不使用全局 bootstrap，才执行直接 `project-local` 安装。

## 执行原则

- 不要凭空猜测路径，先确认当前工作目录和源包路径是否存在。
- 优先创建 package 专用 `venv`。
- 安装完成后必须执行 `status` 校验。
- 安装或更新插件后，提醒用户重启 OpenCode 或重新打开项目。
- 安装完成后，`/wp-develop` 会通过 S1 需求逻辑访谈创建目标 workflow；不要把安装流程误认为已经创建了目标 workflow。
- 如果安装失败，直接报告失败原因，不要假设成功。
- 除本文档明确要求的命令外，不要额外修改其它文件。

## 步骤

### 1. 默认：安装或确认全局轻量 bootstrap

先检查全局 bootstrap 是否已安装。如果未安装，或状态异常，执行一次全局 bootstrap 安装。

Windows：

```bash
python D:\Code\WorkflowProgram-CN\opencode-v2\package\.workflowprogram\runtime\package-deploy.py install-bootstrap --source-package-root D:\Code\WorkflowProgram-CN\opencode-v2\package --force
```

bash / WSL / Linux：

```bash
python3 /mnt/d/Code/WorkflowProgram-CN/opencode-v2/package/.workflowprogram/runtime/package-deploy.py install-bootstrap --source-package-root /mnt/d/Code/WorkflowProgram-CN/opencode-v2/package --force
```

检查 bootstrap：

```bash
python3 /mnt/d/Code/WorkflowProgram-CN/opencode-v2/package/.workflowprogram/runtime/package-deploy.py bootstrap-status
```

bootstrap 可用后，在当前项目中执行：

```text
/wp-install
```

注意：

- 全局 bootstrap 不是完整 WorkflowProgram。
- 全局只应出现 `/wp-install`、`/wp-status`、`/wp-upgrade`、`/wp-uninstall`。
- `/wp-develop` 等完整产品命令只应在当前项目完成 project-local 安装后出现。

### 2. 如果跳过 bootstrap：识别平台与解释器

先判断当前 shell 环境：

- 如果是 Windows shell，优先使用 `python`
- 如果是 bash / WSL / Linux，优先使用 `python3`

同时确认以下路径存在：

- 源包路径
- 当前工作目录

### 3. 如果跳过 bootstrap：执行项目本地安装

如果当前环境是 Windows，请执行：

```bash
python D:\Code\WorkflowProgram-CN\opencode-v2\package\.workflowprogram\runtime\package-deploy.py install --mode project-local --create-venv --python python --source-package-root D:\Code\WorkflowProgram-CN\opencode-v2\package --target-root .
```

如果当前环境是 bash / WSL / Linux，请执行：

```bash
python3 /mnt/d/Code/WorkflowProgram-CN/opencode-v2/package/.workflowprogram/runtime/package-deploy.py install --mode project-local --create-venv --python python3 --source-package-root /mnt/d/Code/WorkflowProgram-CN/opencode-v2/package --target-root .
```

### 4. 如果跳过 bootstrap：执行状态检查

如果当前环境是 Windows，请执行：

```bash
python D:\Code\WorkflowProgram-CN\opencode-v2\package\.workflowprogram\runtime\package-deploy.py status --mode project-local --target-root .
```

如果当前环境是 bash / WSL / Linux，请执行：

```bash
python3 /mnt/d/Code/WorkflowProgram-CN/opencode-v2/package/.workflowprogram/runtime/package-deploy.py status --mode project-local --target-root .
```

### 5. 安装成功判定

只有同时满足以下条件，才可以报告安装成功：

- `install` 返回 `PASS` 或 `WARN`
- `status` 返回可用布局
- 当前项目中存在这些路径：
  - `.opencode/agents/workflow-designer.md`
  - `.opencode/agents/workflow-validator.md`
  - `.opencode/agents/workflow-verifier.md`
  - `.opencode/agents/logic-reviewer.md`
  - `.opencode/agents/security-reviewer.md`
  - `.opencode/agents/performance-reviewer.md`
  - `.opencode/agents/style-reviewer.md`
  - `.opencode/agents/test-scenario-generator.md`
  - `.opencode/commands/wp-audit.md`
  - `.opencode/commands/wp-clean.md`
  - `.opencode/commands/wp-develop.md`
  - `.opencode/commands/wp-doctor.md`
  - `.opencode/commands/wp-evolve.md`
  - `.opencode/commands/wp-preflight.md`
  - `.opencode/commands/wp-hotfix.md`
  - `.opencode/commands/wp-iterate.md`
  - `.opencode/commands/wp-orchestrate.md`
  - `.opencode/commands/wp-ship.md`
  - `.opencode/commands/wp-validate.md`
  - `.opencode/plugins/workflowprogram.ts`
  - `.workflowprogram/package/runtime/workflow-entry.py`
  - `.workflowprogram/package/install-manifest.json`

### 6. 完成后的用户提示

安装成功后，告诉用户：

- 重新打开当前项目的 OpenCode 会话，或者刷新命令列表
- 然后检查 `/wp-develop`、`/wp-doctor`、`/wp-clean`、`/wp-preflight`、`/wp-hotfix`、`/wp-iterate`、`/wp-audit`、`/wp-evolve`、`/wp-orchestrate`、`/wp-ship`、`/wp-validate` 是否出现
- 如需使用 package agents，可检查 `@workflow-designer`、`@workflow-validator`、`@workflow-verifier`、`@test-scenario-generator` 等是否可见
- 如果 OpenCode 仍显示旧命令列表，重启 OpenCode 或重新打开当前项目
- 如果使用的是全局 bootstrap，新项目第一次只会看到 `/wp-install` 等部署命令；完整 `/wp-develop` 等命令需要项目本地安装后刷新才会出现

## 安装后的 `/wp-develop` 使用约束

`/wp-develop` 是创建或更新目标工作流的对话式入口。OpenCode 应先完成 S1 需求逻辑访谈，再执行 runtime：

- 按 `purpose`、`object_model`、`process_model`、`decision_model`、`evidence_model`、`acceptance_model`、`boundary_model` 七个 logic lenses 澄清需求。
- 回读 workflow graph、启用/禁用能力、目标 CLI command、OpenCode plugin hook 和将写入的文件。
- 用户明确确认后，生成 accepted `workflow-spec.md` 和 `workflow-spec.yaml`，再运行 runtime。
- 成功的 develop run 会留下 `RUN_ROOT/outputs/clarification/question-backlog.json` 和 `RUN_ROOT/outputs/clarification/requirement-logic-map.json`，并镜像到 `RUN_ROOT/outputs/stages/` 供 S5 校验。
- 如果只问了泛问题或澄清轮次不足，`validate-workflow-draft.py` 会拒绝进入生成阶段。

## 故障处理

### Python 不存在

- 报告“当前环境没有可用的 Python 解释器，无法完成安装”
- 不要继续执行后续步骤

### venv 创建失败

- 报告 `package-deploy.py install --create-venv` 的原始错误
- 不要改成无 venv 安装，除非用户明确允许

### 依赖安装失败

- 报告 pip 安装错误
- 明确说明当前 runtime 至少需要 `PyYAML`

### 状态检查失败

- 报告缺失的命令、插件或 runtime 文件
- 不要把安装标记为成功

### 命令或 agent 被其它来源遮蔽

- 执行 `/wp-doctor`
- 检查 `DOC-08` 的来源路径
- 不要自动删除全局 OpenCode、Claude 或 oh-my-opencode 资产
- 把冲突路径和建议隔离方式报告给用户

### 全局 bootstrap 存在但 `/wp-install` 不出现

- 执行 `package-deploy.py bootstrap-status`
- 检查 OpenCode global config root 是否与当前 OpenCode 读取的路径一致
- 如果设置了 `OPENCODE_CONFIG_DIR`，确保安装 bootstrap 时使用的是同一个目录
- 重启 OpenCode 或重新打开项目

### 需要离线或锁定依赖安装

- 如果用户明确要求锁定依赖，可在安装命令中追加 `--use-lock`
- `--use-lock` 只在 `--create-venv` 时影响 Python 依赖安装

### 需要清理缓存或历史 runs

- 当前项目清理使用 `/wp-clean`，默认 dry-run
- 删除 Python cache 可使用 `/wp-clean --pycache --yes`
- 删除历史 runs 必须显式指定策略，例如 `/wp-clean --runs --keep-last 20 --yes`
- 不要删除 `.workflowprogram/design`、`.workflowprogram/package`、`.workflowprogram/runtime`、`.workflowprogram/managed-files.json`
- bootstrap cache 清理使用 `package-deploy.py clean-bootstrap-cache --keep-last 2 --yes`，不要手工删除 active cache
