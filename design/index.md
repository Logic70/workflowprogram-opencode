# OpenCode V2 Design Index

## 目的

本索引用于声明 OpenCode v2 的当前设计真源与文档分工。

## 当前生效真源

- [opencode-v2-highlevel-design.md](opencode-v2-highlevel-design.md)
- [opencode-v2-lowlevel-design.md](opencode-v2-lowlevel-design.md)
- [opencode-v2-validation-matrix.md](opencode-v2-validation-matrix.md)
- [opencode-v2-implementation-plan.md](opencode-v2-implementation-plan.md)

## 文档分工

| 文档 | 作用 |
|---|---|
| `opencode-v2-highlevel-design.md` | 定义系统边界、分层契约、架构模型、部署与交付规划 |
| `opencode-v2-lowlevel-design.md` | 定义特性拆分、use case、模块接口、story 依赖与实现约束 |
| `opencode-v2-validation-matrix.md` | 定义 package/spec/target/run-state/smoke 的分层校验矩阵 |
| `opencode-v2-implementation-plan.md` | 定义实施阶段、优先级、文件级改造清单与风险收口顺序 |

## 当前设计结论

- OpenCode v2 是 **OpenCode only** 的产品路径。
- WorkflowProgram 自身加载形式与生成目标工作流加载形式必须严格分层。
- v1 采用 `source-as-deployment-source` 模式，不以前置构建产物为设计前提。
- 产品包命令与产品包插件属于 package contract。
- 目标工作流的 commands / skills / agents / plugins 是否生成，属于 target bundle contract。
