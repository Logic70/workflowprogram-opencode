---
description: Diagnose WorkflowProgram package and host readiness for the current project
---

This is a WorkflowProgram package command.

Rules:
- Treat the current working directory as `TARGET_ROOT`.
- Only call scripts from `${WORKFLOWPROGRAM_RUNTIME_ROOT}/`.
- Do not mutate target assets from the command body.

Run this first:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/doctor.py" --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --target-root "$PWD" --json
```

Then:
- Report the overall doctor verdict.
- Surface failed checks directly.
- If the doctor fails, suggest running the remediation generator or reinstalling with `--create-venv` when the failure is Python-related.
