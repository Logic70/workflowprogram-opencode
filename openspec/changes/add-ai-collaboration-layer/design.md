## Context

WorkflowProgram for OpenCode has three separate execution responsibilities:

- OpenCode host and package agents provide AI reasoning and review.
- Python runtime provides deterministic orchestration, state, validation, managed apply, and rollback.
- Generated target workflow assets provide the project-local workflow bundle.

The previous runtime-first command design hid the first responsibility. As a result, model behavior could skip package agents and treat stage evidence as optional documentation.

## Design

### AI Collaboration Layer

Package commands SHALL use OpenCode package agents as the AI collaboration layer. This layer is host-mediated: Python does not call OpenCode subagents directly.

The command flow SHALL be:

1. Run `agent-team-planner.py` for the product intent.
2. Dispatch `recommended_dispatch` entries with `timing=pre-runtime` before `workflow-entry.py`.
3. Pass a concise summary of useful pre-runtime agent findings to `workflow-entry.py --ai-evidence`.
4. Run deterministic runtime.
5. Dispatch `timing=post-runtime` entries after `RUN_ROOT` exists.
6. Report skipped dispatch as `AI-DISPATCH-SKIPPED`; never claim an agent ran without a separate response or trace.

### Runtime Evidence

`workflow-entry.py --ai-evidence` SHALL record host-mediated AI evidence in run context and state. The runtime treats this as evidence, not as authority to bypass validators.

### Boundary Rules

- Agentteam is a role/stage plan, not a subagent execution proof.
- Package agents may produce design or review evidence but must not write target files.
- Python remains authoritative for target writes, validation, locks, and rollback.
- The engine-in-cache approach is rejected for this change because it changes deployment semantics and does not address `.opencode` package assets or skipped agent dispatch.

## Risks

- OpenCode provider/API limits can prevent real agent dispatch. Commands must report skipped dispatch instead of pretending success.
- Agent evidence is model-produced and must remain advisory. Validators and managed apply remain deterministic gates.
