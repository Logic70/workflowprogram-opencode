# Proposal: Add OpenCode Requirement Logic Interview

## Why

Claude upstream now enforces S1 as a requirement-logic interview instead of generic clarification. OpenCode currently has an interactive clarification gate, but it does not produce the same design-consequential evidence or reject shallow drafts deterministically.

## What Changes

- Add OpenCode-native S1 requirement-logic interview evidence.
- Generate `question-backlog.json` and `requirement-logic-map.json`.
- Validate seven logic lenses before a ready develop run can claim S1 completion.
- Make S5 judge and run-state validation check clarification handoff evidence.
- Keep AgentTeam as host-mediated dispatch, but require evidence language that distinguishes a team plan from actual subagent execution.

## Impact

- `/wp-develop` template fallback and accepted-spec flows produce richer S1 evidence.
- Shallow drafts with generic questions fail deterministic draft validation.
- Capability parity documentation changes "clarification package" from generic implemented to requirement-logic implemented.
