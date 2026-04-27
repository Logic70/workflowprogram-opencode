---
description: Validate WorkflowProgram package, target bundle, and run evidence
---

This is a WorkflowProgram package command.

Rules:
- Treat the current working directory as `TARGET_ROOT`.
- Only call scripts from `${WORKFLOWPROGRAM_RUNTIME_ROOT}/`.
- Use `$ARGUMENTS` only as extra validation context.
- Only `.workflowprogram/design/workflow-spec.yaml` means a generated target workflow exists; package install files are validated separately.

Run this first:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/workflow-entry.py" validate --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --target-root "$PWD" --user-arguments "$ARGUMENTS"
```

Then:
- Report the package/spec/target/run-state summary produced by the runtime.
- Report `team_plan.team_plan_guide` when present as the stage/agent dispatch guide; do not claim package agents ran unless separate agent output exists.
- If some layers are still placeholders, report them as such.
- If the script exits non-zero, surface the error instead of guessing success.
