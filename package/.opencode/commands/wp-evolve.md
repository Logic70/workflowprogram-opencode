---
description: Evolve an existing generated target workflow through managed apply
---

This is a WorkflowProgram package command.

Rules:
- Treat the current working directory as `TARGET_ROOT`.
- Only call scripts from `${WORKFLOWPROGRAM_RUNTIME_ROOT}/`.
- Pass `$ARGUMENTS` to the runtime as raw evolve intent.
- Evolve requires an existing generated target workflow.
- Existing generated target workflow means `.workflowprogram/design/workflow-spec.yaml`, not `.workflowprogram/package/*`, `.workflowprogram/runtime/*`, or `.workflowprogram/runs/*` alone.
- Do not write target assets directly from the command body.
- Use the host model/package agents to produce the accepted updated `workflow-spec.yaml`; Python validates and applies it.

Optionally run the agentteam planner first:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/agent-team-planner.py" --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --intent evolve --json
```

Then dispatch `pre-runtime` agents if useful, or report `AI-DISPATCH-SKIPPED` if unavailable. Planner output and skipped dispatch are advisory only.

Run the runtime after the updated design is accepted:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/workflow-entry.py" evolve --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --target-root "$PWD" --user-arguments "$ARGUMENTS" --draft "<path-to-workflow-spec.md>" --spec "<path-to-workflow-spec.yaml>"
```

Do not use `--ai-evidence` as proof that design happened; it is a deprecated diagnostic note only.

Then:
- Report the created `RUN_ROOT`.
- Report the evolve plan and managed apply result.
- Dispatch `post-runtime` agents from `team_plan.team_plan_guide` when present.
- Do not claim package agents ran unless separate agent output exists.
- If the runtime reports conflicts or lock failures, surface them as blocking issues.
