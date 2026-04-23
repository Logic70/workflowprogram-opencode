# WorkflowProgram for OpenCode

WorkflowProgram 的 OpenCode 独立版本。

这个仓库提供一套面向 OpenCode 的本地产品包，核心能力包括：

- `/wp-develop`：为当前项目生成目标工作流
- `/wp-doctor`：诊断 package、Python、OpenCode CLI 和当前项目就绪度
- `/wp-preflight`：做 package 和目标工作流就绪度检查
- `/wp-hotfix`：对已有目标工作流做受控热修
- `/wp-iterate`：基于已有工作流和前次运行上下文做迭代
- `/wp-ship`：确认已有目标工作流的交付就绪度
- `/wp-validate`：对 package、spec、target bundle、run-state 做分层校验
- package agent pack：`@workflow-designer`、`@workflow-validator`、`@workflow-verifier`、`@logic-reviewer`、`@security-reviewer`、`@performance-reviewer`、`@style-reviewer`
- `project-local` / `global` 安装
- 可选 package 专用 Python `venv`
- runtime smoke 与真实 OpenCode host integration smoke

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

### 方式一：直接执行安装脚本

推荐。

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

### 方式二：让 OpenCode 读取安装说明自行执行

可行，但它本质上仍然是“agent 按文档执行命令”，不是替代安装脚本的原生安装机制。

让 OpenCode 读取：

- [INSTALL_WITH_OPENCODE.md](./INSTALL_WITH_OPENCODE.md)

例如在 OpenCode 中输入：

```text
请读取 <repo-root>/INSTALL_WITH_OPENCODE.md，并严格按步骤执行安装。
```

如果你要稳定、可重复的安装结果，仍然建议优先直接执行 `package-deploy.py`。

## 使用

安装完成后，在目标项目根目录打开 OpenCode。

命令列表里应出现：

- `/wp-develop`
- `/wp-doctor`
- `/wp-preflight`
- `/wp-hotfix`
- `/wp-iterate`
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

典型流程：

1. 执行 `/wp-develop <你的需求>`
2. 需要先诊断环境时执行 `/wp-doctor`
3. 需要先检查就绪度时执行 `/wp-preflight`
4. 对已有工作流修复或增量调整时执行 `/wp-hotfix` 或 `/wp-iterate`
5. 准备最终确认时执行 `/wp-ship`
6. 执行 `/wp-validate`

## Doctor 常见结果

- `DOC-04` 失败
  - 说明当前 Python 环境缺少 `PyYAML`，优先重新安装并使用 `--create-venv`
- `DOC-05` 失败
  - 说明当前 shell 里没有可用的 `opencode` CLI，OpenCode 宿主集成无法验证
- `DOC-06` 失败
  - 说明当前项目目录不可写，`develop/hotfix/iterate` 这类写入型命令无法正常工作
- `DOC-07` 失败
  - 说明当前项目还没有生成目标工作流，先执行 `/wp-develop`

## 安装后的目录布局

`project-local` 安装后，目标项目中会出现：

```text
<target-project-root>/
├── .opencode/
│   ├── commands/
│   │   ├── wp-develop.md
│   │   ├── wp-doctor.md
│   │   ├── wp-preflight.md
│   │   ├── wp-hotfix.md
│   │   ├── wp-iterate.md
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

## 当前状态

目前已经完成并验证：

- package 部署与卸载
- `project-local` 安装
- 可选 `venv` 创建与依赖安装
- runtime 级 `develop -> validate` 闭环
- package/spec/target/run-state 分层校验

本地验证过：

- `py_compile`
- source package validator
- `install -> status -> develop -> validate -> uninstall`
- `--create-venv` 下的 `PyYAML` 导入与 runtime 执行

当前仓库已经有真实 OpenCode 宿主的自动化集成 smoke，但它和 runtime smoke 的含义不同。runtime smoke 追求确定性闭环；host integration smoke 会真实调用 `opencode run --command ...`，因此在 provider/API 未就绪时允许返回 `ENVIRONMENT-SKIP`，而不是假装通过。
当前已经补上两层 smoke：

- `runtime smoke`
  - 直接调用 Python runtime，验证 `install -> develop -> preflight -> hotfix -> iterate -> ship -> validate`
- `host integration smoke`
  - 真实调用 `opencode run --command ...`
  - 检查 OpenCode CLI、package commands、package plugin、命令发现、以及运行时是否真正进入 bash/tool 阶段
  - 在 provider/API 未就绪时允许返回 `ENVIRONMENT-SKIP`

手工运行 host integration smoke：

```bash
python3 package/.workflowprogram/runtime/host-integration-smoke.py --package-root <installed-project-root> --target-root <installed-project-root> --timeout-seconds 15 --json
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
- [HighLevel 设计](./design/opencode-v2-highlevel-design.md)
- [LowLevel 设计](./design/opencode-v2-lowlevel-design.md)
- [Validation Matrix](./design/opencode-v2-validation-matrix.md)
- [实施计划](./design/opencode-v2-implementation-plan.md)

## 和 ClaudeCode 版的关系

这个仓库保留了 WorkflowProgram 的核心思路：

- `spec-first`
- `S0..S6`
- `RUN_ROOT`
- managed apply
- runner / layered validation

但 OpenCode 的入口模型、安装布局、插件边界和运行时调用方式都是独立设计的。

## License

Apache-2.0. See [LICENSE](./LICENSE).
