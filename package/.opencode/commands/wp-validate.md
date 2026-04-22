---
description: Validate WorkflowProgram package, target bundle, and run evidence
---

This is a WorkflowProgram package command.

Rules:
- Treat the current working directory as `TARGET_ROOT`.
- Only call scripts from `${WORKFLOWPROGRAM_RUNTIME_ROOT}/`.
- Use `$ARGUMENTS` only as extra validation context.

Run this first:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/workflow-entry.py" validate --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --target-root "$PWD" --user-arguments "$ARGUMENTS"
```

Then:
- Report the package/spec/target/run-state summary produced by the runtime.
- If some layers are still placeholders, report them as such.
- If the script exits non-zero, surface the error instead of guessing success.
