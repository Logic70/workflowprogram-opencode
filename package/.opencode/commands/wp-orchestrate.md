---
description: Route a WorkflowProgram request to the safest product intent
---

This is a WorkflowProgram package command.

Rules:
- Treat the current working directory as `TARGET_ROOT`.
- Only call scripts from `${WORKFLOWPROGRAM_RUNTIME_ROOT}/`.
- Pass `$ARGUMENTS` to the runtime as the request to route.
- Do not execute mutating work from this command unless the runtime explicitly does so.

Run this first:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/workflow-entry.py" orchestrate --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --target-root "$PWD" --user-arguments "$ARGUMENTS"
```

Then:
- Report the recommended intent and confidence.
- If the runtime asks for clarification, ask the user before running another `/wp-*` command.
- If the runtime recommends a mutating intent, do not perform it automatically.

