## Why

The OpenCode package had a deterministic Python control plane, but the design did not explicitly place OpenCode model/agent collaboration in the workflow execution path. This made `/wp-develop` look like a Python-only generator and left stage guidance as passive evidence instead of actionable agent dispatch.

The required correction is not to copy ClaudeCode skills. OpenCode should use OpenCode-native package agents as the AI collaboration layer while keeping Python responsible for deterministic state, validation, managed apply, and rollback.

## What Changes

- Add an architecture rule that package commands call the agentteam planner before or after runtime depending on the intent.
- Add pre-runtime agent dispatch for design/mutation intents such as `develop`, `evolve`, `hotfix`, and `iterate`.
- Keep post-runtime dispatch for validation, audit, and ship-readiness review.
- Add `--ai-evidence` to `workflow-entry.py` so concise host-mediated agent evidence is recorded in `context.json` and `state.json`.
- Revert the unnecessary DeepSeek engine-in-cache architecture change because it changes install semantics without solving the AI collaboration gap.

## Impact

- Updates:
  - `design/opencode-v2-highlevel-design.md`
  - `design/opencode-v2-lowlevel-design.md`
  - `README.md`
  - `package/.opencode/commands/wp-*.md`
  - `package/.workflowprogram/runtime/agent-team-planner.py`
  - `package/.workflowprogram/runtime/workflow-entry.py`
  - `package/.workflowprogram/runtime/workflow-runner.py`
- Reverts local DeepSeek commits:
  - `4b11f3e feat(deepseek): engine-in-cache - Python runtime never copied to target project`
  - `b783a7d fix(deepseek): status validator field removed in engine-in-cache model`
