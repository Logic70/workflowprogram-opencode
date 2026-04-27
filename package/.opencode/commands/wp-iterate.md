---
description: Iterate an existing generated target workflow using prior run evidence and managed apply
---

This is a WorkflowProgram package command.

Rules:
- Treat the current working directory as `TARGET_ROOT`.
- Only call scripts from `${WORKFLOWPROGRAM_RUNTIME_ROOT}/`.
- Pass `$ARGUMENTS` to the runtime as raw iterate intent.
- Iterate requires an existing generated target workflow.
- Existing generated target workflow means `.workflowprogram/design/workflow-spec.yaml`, not `.workflowprogram/package/*`, `.workflowprogram/runtime/*`, or `.workflowprogram/runs/*` alone.

Run this first:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/workflow-entry.py" iterate --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --target-root "$PWD" --user-arguments "$ARGUMENTS"
```

Then:
- Report the created `RUN_ROOT`.
- Report whether prior run context was detected.
- Report `team_plan.team_plan_guide` when present as the stage/agent dispatch guide; do not claim package agents ran unless separate agent output exists.
- If the runtime reports missing target assets or managed conflicts, surface that clearly.
