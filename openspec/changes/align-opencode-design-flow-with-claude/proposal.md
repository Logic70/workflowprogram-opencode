## Why

The current OpenCode implementation records AI collaboration as side evidence, but the default mutation path still lets Python generate the workflow specification from fixed templates. This diverges from the ClaudeCode WorkflowProgram model, where AI/user design work produces the design draft and machine specification, while Python validates, derives generated files, runs deterministic runtime steps, and applies managed writes.

The correction is to align OpenCode with the existing WorkflowProgram artifact model instead of adding a new AI pipeline. OpenCode should adapt host-specific command, plugin, and agent mechanics only where required. WorkflowProgram stage semantics, design artifacts, evidence files, validators, and managed apply rules should remain consistent with the ClaudeCode version.

## What Changes

- Make `/wp-develop` follow the ClaudeCode design flow:
  - produce `workflow-spec.md` during S1 design and clarification
  - produce `workflow-spec.yaml` as the single machine-readable source
  - generate `workflow-view.md` and `workflow-lowlevel.md` from `workflow-spec.yaml`
  - generate target runtime assets from `workflow-spec.yaml`
  - apply target assets only through managed apply
- Remove `--ai-evidence` from the main success path and deprecate `state.ai_collaboration` as a core acceptance signal.
- Demote `agent-team-planner.py` and `team-plan` to optional OpenCode host-dispatch assistance, not core WorkflowProgram semantics.
- Prevent Python template generation from acting as the default design path.
- Preserve useful historical work without reverting the whole change set.

## Non-Goals

- Do not introduce `workflow-spec.proposed.yaml`.
- Do not introduce `design-brief.md`.
- Do not introduce `ai-design-source.json`.
- Do not introduce `AI-DESIGN-*` as a product validation domain.
- Do not add prepare/resume runtime phases visible to users.
- Do not require target command or target plugin generation unless `workflow-spec.yaml` explicitly asks for those assets.

## Impact

Updates are expected in:

- `design/opencode-v2-highlevel-design.md`
- `design/opencode-v2-lowlevel-design.md`
- `design/opencode-v2-implementation-plan.md`
- `design/opencode-v2-validation-matrix.md`
- `package/.opencode/commands/wp-develop.md`
- `package/.opencode/commands/wp-evolve.md`
- `package/.opencode/commands/wp-hotfix.md`
- `package/.opencode/commands/wp-iterate.md`
- `package/.workflowprogram/runtime/workflow-entry.py`
- `package/.workflowprogram/runtime/workflow-runner.py`
- `package/.workflowprogram/runtime/validators/*`
- `package/.workflowprogram/runtime/*clarification*`
- `package/.workflowprogram/runtime/*workflow-spec*`
- `package/.workflowprogram/runtime/*workflow-view*`
- `package/.workflowprogram/runtime/*workflow-lowlevel*`
- `tests/` fixtures and smoke coverage

