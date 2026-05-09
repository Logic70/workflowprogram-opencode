---
description: Design or update a target workflow with WorkflowProgram
---

This is a WorkflowProgram package command.

Entry strategy:
- For natural-language requests where the right lifecycle step is unclear, prefer `/wp-orchestrate` first.
- This direct command is an explicit expert entry for first-time workflow creation or intentional full design refresh.

Rules:
- Treat the current working directory as `TARGET_ROOT`.
- Only call scripts from `${WORKFLOWPROGRAM_RUNTIME_ROOT}/`.
- Pass `$ARGUMENTS` to the runtime as raw user intent.
- Do not write target assets directly from the command body.
- This command creates or updates the generated target workflow; it is the first-time path when `.workflowprogram/design/workflow-spec.yaml` is absent.
- Use the host model/package agents to design the workflow first; Python runtime validates, packages, and applies the accepted design.
- Default mode is interactive. If the user has not already answered clarification questions and confirmed the design readback, ask the questions first and stop; do not run the runtime yet.

Interactive clarification gate:
- For broad requests like "create a reverse engineering workflow", use a requirement logic interview before runtime execution.
- Cover these seven logic lenses before design readback: purpose, object_model, process_model, decision_model, evidence_model, acceptance_model, and boundary_model.
- Questions must be design-consequential: different answers should change graph nodes, branch decisions, evidence requirements, acceptance scenarios, or stop boundaries.
- Generic questions like "any other edge cases?" cannot be the primary evidence for a complex workflow.
- Keep the first clarification round concise; group these decisions into at most five questions when possible:
  - target object and final deliverables
  - graph shape: sequence, branch, parallelism, fan-in/fan-out, manual checkpoints, and shared context
  - allowed tools, write boundaries, external side effects, privacy, and execution limits
  - validation signals, stop conditions, human handoff, and optional self-iteration retry/rework rules
  - target CLI command needs and, as a separate trigger decision, OpenCode plugin hook needs
- After the user answers, summarize the proposed workflow graph before runtime execution. The readback must include nodes, edges, shared context, enabled capabilities, disabled capabilities, and files that will be written.
- Only after explicit confirmation, write the accepted design as `workflow-spec.md` and `workflow-spec.yaml`, then continue below and append `--confirmed` to the runtime command.
- `$ARGUMENTS` containing `--confirmed` is not enough by itself; it is valid only when the accepted `workflow-spec.md` and `workflow-spec.yaml` also exist and the current turn clearly confirms writing and runtime execution.
- Pre-runtime package agent evidence helps design the workflow, but it is not a substitute for user confirmation.
- A valid develop run must produce requirement-logic evidence such as `question-backlog.json` and `requirement-logic-map.json` under RUN_ROOT outputs; shallow drafts can be rejected by deterministic validators.

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

Only run this command after the interactive gate is complete, `workflow-spec.md` is the accepted human-readable design, and `workflow-spec.yaml` is the accepted machine-readable design.
Do not run the runtime without `--confirmed` unless you are intentionally testing the runtime guard.
Do not use `--ai-evidence` as proof that design happened; it is a deprecated diagnostic note only.

Then:
- Report the created `RUN_ROOT`.
- Report whether runtime bootstrap succeeded.
- Dispatch `post-runtime` agents from `team_plan.team_plan_guide` when present.
- Do not claim package agents ran unless separate agent output exists.
- If the runtime returns `Interactive clarification required`, show the blocking questions and stop; do not claim the workflow was created.
- If the script exits non-zero, surface the error instead of guessing success.
