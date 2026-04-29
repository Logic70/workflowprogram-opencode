---
description: Design or update a target workflow with WorkflowProgram
---

This is a WorkflowProgram package command.

Rules:
- Treat the current working directory as `TARGET_ROOT`.
- Only call scripts from `${WORKFLOWPROGRAM_RUNTIME_ROOT}/`.
- Pass `$ARGUMENTS` to the runtime as raw user intent.
- Do not write target assets directly from the command body.
- This command creates or updates the generated target workflow; it is the first-time path when `.workflowprogram/design/workflow-spec.yaml` is absent.
- Use package agents as the AI collaboration layer; Python runtime is the deterministic control plane, not the only designer.

Run the agentteam planner first:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/agent-team-planner.py" --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --intent develop --json
```

Then:
- Dispatch every `recommended_dispatch` item with `timing=pre-runtime` using the named `@agent`.
- If agent dispatch is unavailable, continue only after reporting `AI-DISPATCH-SKIPPED`.
- Summarize useful pre-runtime agent findings as concise AI evidence.

Run the runtime after pre-runtime agent dispatch:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/workflow-entry.py" develop --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --target-root "$PWD" --user-arguments "$ARGUMENTS"
```

If concise AI evidence exists, append `--ai-evidence "<summary>"` to the runtime command.

Then:
- Report the created `RUN_ROOT`.
- Report whether runtime bootstrap succeeded.
- Dispatch `post-runtime` agents from `team_plan.team_plan_guide` when present.
- Do not claim package agents ran unless separate agent output exists.
- If the script exits non-zero, surface the error instead of guessing success.
