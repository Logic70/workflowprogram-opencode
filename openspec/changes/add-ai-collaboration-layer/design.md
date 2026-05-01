## Context

Supersession note: `align-opencode-design-flow-with-claude` keeps the useful
host-dispatch assets from this change but replaces the core design contract.
Normal mutation now consumes an accepted `workflow-spec.yaml`; `--ai-evidence`
is legacy diagnostic context only.

WorkflowProgram for OpenCode has three separate execution responsibilities:

- OpenCode host and package agents provide AI reasoning and review.
- Python runtime provides deterministic orchestration, state, validation, managed apply, and rollback.
- Generated target workflow assets provide the project-local workflow bundle.

The previous runtime-first command design hid the first responsibility. As a result, model behavior could skip package agents and treat stage evidence as optional documentation.

## Design

### AI Collaboration Layer

Package commands SHALL use OpenCode package agents as the AI collaboration layer. This layer is host-mediated: Python does not call OpenCode subagents directly.

The command flow SHALL be:

1. Run an interactive clarification gate for develop requests that have not been explicitly confirmed by the user.
2. Ask blocking questions and stop until the user answers and confirms the design readback.
3. Run `agent-team-planner.py` for the product intent.
4. Dispatch `recommended_dispatch` entries with `timing=pre-runtime` before `workflow-entry.py`.
5. Pass a concise summary of useful pre-runtime agent findings to `workflow-entry.py --ai-evidence`.
6. Run deterministic runtime with `--confirmed`.
7. Dispatch `timing=post-runtime` entries after `RUN_ROOT` exists.
8. Report skipped dispatch as `AI-DISPATCH-SKIPPED`; never claim an agent ran without a separate response or trace.

### Runtime Evidence

`workflow-entry.py --ai-evidence` SHALL record host-mediated AI evidence in run context and state. The runtime treats this as evidence, not as authority to bypass validators or user confirmation.

For `develop`, `workflow-entry.py` SHALL also support `--confirmed`. When the request is not confirmed, runtime SHALL emit blocking clarification questions and SHALL NOT generate target workflow assets. Pre-runtime AI evidence SHALL NOT substitute for `--confirmed`.

### Boundary Rules

- Agentteam is a role/stage plan, not a subagent execution proof.
- Package agents may produce design or review evidence but must not write target files.
- Python remains authoritative for target writes, validation, locks, and rollback.
- The engine-in-cache approach is rejected for this change because it changes deployment semantics and does not address `.opencode` package assets or skipped agent dispatch.

## Risks

- OpenCode provider/API limits can prevent real agent dispatch. Commands must report skipped dispatch instead of pretending success.
- Agent evidence is model-produced and must remain advisory. Validators and managed apply remain deterministic gates.
