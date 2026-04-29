---
description: Check WorkflowProgram package and target workflow readiness without mutating target assets
---

This is a WorkflowProgram package command.

Rules:
- Treat the current working directory as `TARGET_ROOT`.
- Only call scripts from `${WORKFLOWPROGRAM_RUNTIME_ROOT}/`.
- Do not write target assets from the command body.
- Use `$ARGUMENTS` only as additional readiness context.
- Only `.workflowprogram/design/workflow-spec.yaml` means a generated target workflow exists; package install files are readiness context, not target existence proof.
- Use package agents as the AI collaboration layer after deterministic readiness evidence exists.

Run this first:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/workflow-entry.py" preflight --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --target-root "$PWD" --user-arguments "$ARGUMENTS"
```

Then:
- Report whether a generated target workflow is already present.
- Report the readiness verdict and whether findings are `PASS`, `WARN`, or `FAIL`.
- Dispatch `post-runtime` agents from `team_plan.team_plan_guide` when present.
- Do not claim package agents ran unless separate agent output exists.
- If the script exits non-zero, surface the error instead of guessing success.
