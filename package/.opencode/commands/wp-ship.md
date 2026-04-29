---
description: Confirm ship readiness for an existing generated target workflow
---

This is a WorkflowProgram package command.

Rules:
- Treat the current working directory as `TARGET_ROOT`.
- Only call scripts from `${WORKFLOWPROGRAM_RUNTIME_ROOT}/`.
- Do not mutate target assets from the command body.
- Ship requires an existing generated target workflow.
- Existing generated target workflow means `.workflowprogram/design/workflow-spec.yaml`, not `.workflowprogram/package/*`, `.workflowprogram/runtime/*`, or `.workflowprogram/runs/*` alone.
- Use package agents as the AI collaboration layer after deterministic ship-readiness evidence exists.

Run this first:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/workflow-entry.py" ship --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --target-root "$PWD" --user-arguments "$ARGUMENTS"
```

Then:
- Report whether ship readiness is confirmed or blocked.
- Dispatch `post-runtime` agents from `team_plan.team_plan_guide` when present.
- Do not claim package agents ran unless separate agent output exists.
- Surface validation blockers directly instead of paraphrasing them away.
- If the script exits non-zero, report failure explicitly.
