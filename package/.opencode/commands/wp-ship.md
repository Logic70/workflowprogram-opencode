---
description: Confirm ship readiness for an existing generated target workflow
---

This is a WorkflowProgram package command.

Rules:
- Treat the current working directory as `TARGET_ROOT`.
- Only call scripts from `${WORKFLOWPROGRAM_RUNTIME_ROOT}/`.
- Do not mutate target assets from the command body.
- Ship requires an existing generated target workflow.

Run this first:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/workflow-entry.py" ship --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --target-root "$PWD" --user-arguments "$ARGUMENTS"
```

Then:
- Report whether ship readiness is confirmed or blocked.
- Surface validation blockers directly instead of paraphrasing them away.
- If the script exits non-zero, report failure explicitly.
