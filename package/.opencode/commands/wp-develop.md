---
description: Design or update a target workflow with WorkflowProgram
---

This is a WorkflowProgram package command.

Rules:
- Treat the current working directory as `TARGET_ROOT`.
- Only call scripts from `${WORKFLOWPROGRAM_RUNTIME_ROOT}/`.
- Pass `$ARGUMENTS` to the runtime as raw user intent.
- Do not write target assets directly from the command body.
- This command creates or updates the generated target workflow; it is the first-time path when `.workflowprogram/design/workflow-spec.yaml` is absent.
- Use the host model/package agents to design the workflow first; Python runtime validates, packages, and applies the accepted design.
- Default mode is interactive. If the user has not already answered clarification questions and confirmed the design readback, ask the questions first and stop; do not run the runtime yet.

Interactive clarification gate:
- For broad requests like "create a reverse engineering workflow", use a brainstorm -> constrain -> converge -> readback flow. Ask about plausible workflow shapes, target object, expected deliverables, allowed tools/boundaries, validation signals, retry/stop conditions, graph nodes/transitions or branch points, and target command/plugin hook needs.
- After the user answers, summarize the proposed workflow graph and ask for explicit confirmation.
- Only after confirmation, write the accepted design as `workflow-spec.md` and `workflow-spec.yaml`, then continue below and append `--confirmed` to the runtime command.
- If `$ARGUMENTS` already contains `--confirmed` or the user explicitly confirms in this turn, continue below.
- Pre-runtime package agent evidence helps design the workflow, but it is not a substitute for user confirmation.

Optionally run the agentteam planner after the interactive gate:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/agent-team-planner.py" --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --intent develop --json
```

If used:
- Dispatch every `recommended_dispatch` item with `timing=pre-runtime` using the agent named by the `agent` field.
- If agent dispatch is unavailable, report `AI-DISPATCH-SKIPPED`; do not treat the skip as design evidence.
- Treat planner output as advisory routing context, not acceptance evidence.

Run the runtime after the accepted design exists:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/workflow-entry.py" develop --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --target-root "$PWD" --user-arguments "$ARGUMENTS" --confirmed --draft "<path-to-workflow-spec.md>" --spec "<path-to-workflow-spec.yaml>"
```

Only run this command after the interactive gate is complete and `workflow-spec.yaml` is the accepted machine-readable design.
Do not run the runtime without `--confirmed` unless you are intentionally testing the runtime guard.
Do not use `--ai-evidence` as proof that design happened; it is a deprecated diagnostic note only.

Then:
- Report the created `RUN_ROOT`.
- Report whether runtime bootstrap succeeded.
- Dispatch `post-runtime` agents from `team_plan.team_plan_guide` when present.
- Do not claim package agents ran unless separate agent output exists.
- If the runtime returns `Interactive clarification required`, show the blocking questions and stop; do not claim the workflow was created.
- If the script exits non-zero, surface the error instead of guessing success.
