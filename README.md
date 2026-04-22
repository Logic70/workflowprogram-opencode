# WorkflowProgram for OpenCode

WorkflowProgram 的 OpenCode 独立版本。

这个仓库提供一套面向 OpenCode 的本地产品包，核心能力包括：

- `/wp-develop`：为当前项目生成目标工作流
- `/wp-validate`：对 package、spec、target bundle、run-state 做分层校验
- `project-local` / `global` 安装
- 可选 package 专用 Python `venv`

它不是 ClaudeCode 版的兼容层，也不是从 Claude 版复制后简单替换路径的 adapter。这里的目标是维护一个 **OpenCode only** 的独立实现。

## 仓库结构

```text
.
├── package/
│   ├── opencode.json
│   ├── .opencode/
│   │   ├── commands/
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
- `/wp-validate`

典型流程：

1. 执行 `/wp-develop <你的需求>`
2. 查看生成的目标工作流和 run evidence
3. 执行 `/wp-validate`

## 安装后的目录布局

`project-local` 安装后，目标项目中会出现：

```text
<target-project-root>/
├── .opencode/
│   ├── commands/
│   │   ├── wp-develop.md
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

当前仓库内还没有真实 OpenCode 宿主的自动化集成测试，因为本地验证环境里没有可用的 `opencode` CLI / API。也就是说，安装脚本和 runtime 主链已验证，但命令是否被你的宿主正确发现，仍需要你在本机 OpenCode 环境中确认。

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
