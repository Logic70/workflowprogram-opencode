---
description: Audit an existing WorkflowProgram target workflow without mutating files
---

This is a WorkflowProgram package command.

Rules:
- Treat the current working directory as `TARGET_ROOT`.
- Only call scripts from `${WORKFLOWPROGRAM_RUNTIME_ROOT}/`.
- Pass `$ARGUMENTS` to the runtime as raw audit context.
- Audit is read-only and must not write target assets.
- Only `.workflowprogram/design/workflow-spec.yaml` means a generated target workflow exists; package files and run history are audit context, not target existence proof.
- Use package agents as the AI collaboration layer after deterministic audit evidence exists.

Run this first:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/workflow-entry.py" audit --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --target-root "$PWD" --user-arguments "$ARGUMENTS"
```

Then:
- Report the created `RUN_ROOT`.
- Summarize package, target bundle, run-state, host visibility, and lessons findings.
- Dispatch `post-runtime` agents from `team_plan.team_plan_guide` when present.
- Do not claim package agents ran unless separate agent output exists.
- If the runtime reports missing target assets, surface that as an audit finding rather than guessing success.
