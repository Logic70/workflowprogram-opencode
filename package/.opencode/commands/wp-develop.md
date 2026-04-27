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

Run this first:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/workflow-entry.py" develop --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --target-root "$PWD" --user-arguments "$ARGUMENTS"
```

Then:
- Report the created `RUN_ROOT`.
- Report whether runtime bootstrap succeeded.
- Report `team_plan.team_plan_guide` when present as the stage/agent dispatch guide; do not claim package agents ran unless separate agent output exists.
- If the script exits non-zero, surface the error instead of guessing success.
