## Design

OpenCode WorkflowProgram keeps the ClaudeCode artifact model, but the workflow itself is no longer a fixed slot pipeline. The target model is a graph-shaped workflow that AI defines per request inside a fixed spec shape.

The corrected mutation flow is:

1. OpenCode command runs the WorkflowProgram design conversation for the requested intent.
2. The design conversation writes `RUN_ROOT/workflow-spec.md`.
3. Existing clarification scripts derive and validate:
   - `outputs/stages/clarification-record.json`
   - `outputs/stages/open-questions.json`
   - `outputs/stages/assumption-log.md`
   - `outputs/stages/design-readiness-report.json`
   - `outputs/stages/clarification-challenge-report.json`
   - `outputs/stages/clarification-handoff.json`
   - `outputs/stages/clarification-evidence.json`
4. The command/model produces `RUN_ROOT/workflow-spec.yaml` from the accepted design.
   The YAML schema is fixed, but its graph content is AI-shaped:
   - stage nodes are request-specific
   - transitions are request-specific
   - reusable capability templates may be included when the request needs them
5. Python validates `workflow-spec.yaml`.
6. Python deterministically generates `workflow-view.md`, `workflow-lowlevel.md`, target runtime assets, and any spec-requested target OpenCode assets.
7. Python applies the candidate bundle through managed apply.

## Artifact Rules

- `workflow-spec.md` is the human-readable design draft and clarification carrier.
- `workflow-spec.yaml` is the only machine-readable source of workflow semantics.
- `workflow-view.md` and `workflow-lowlevel.md` are generated read-only views from `workflow-spec.yaml`.
- `clarification-*.json` and `assumption-log.md` are the evidence chain for readiness, challenge, handoff, and readback confirmation.
- `--ai-evidence`, `state.ai_collaboration`, and `team-plan` are supplemental evidence only and must not be required to prove that workflow design occurred.
- Fixed `S1-S6` slots are not part of the target model.
- Reusable behaviors such as clarification, validation, self-iteration, merge, and handoff belong in optional capability templates or subgraphs.
- Shared context semantics should be defined before any access-control policy.
- Read/write permissions are intentionally deferred to a later OpenSpec task.

## Historical Change Handling

Historical OpenCode work should be superseded selectively:

- Keep OpenCode command files, package agents, validators, install/smoke work, managed apply, and host diagnostics when they still fit this flow.
- Keep `agent-team-planner.py` only as optional host-dispatch assistance.
- Deprecate `--ai-evidence` from the main path instead of expanding it.
- Replace fixed-slot workflow generation with graph-shaped spec generation.
- Model reusable capabilities as templates or subgraphs that AI may select and expand.
- Defer context access-control policy to a later OpenSpec task.
- Do not revert whole prior changes unless a specific file-level change conflicts with the corrected flow.

## Conflict Avoidance

This change intentionally avoids new intermediate artifacts and new validation domains. Any added check must attach to an existing WorkflowProgram validator family or a graph-capability derivation rule:

- draft design validation
- clarification evidence validation
- spec validation
- view/lowlevel deterministic derivation validation
- generated runtime validation
- target bundle validation
- managed apply validation
- run-state validation

## User Experience

The user-facing experience stays as one command:

```text
/wp-develop <request>
```

Internal OpenCode command steps may call package agents or scripts, but the user must not need to understand prepare/resume phases, proposed specs, or design-source envelopes.
