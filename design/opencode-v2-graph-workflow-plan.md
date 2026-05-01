# OpenCode V2 Graph Workflow Implementation Plan

This plan implements the graph-shaped workflow model described in `opencode-v2-graph-workflow-design.md`.

## Scope

- Remove fixed S1-S6 stage-slot assumptions from the target model.
- Allow AI to define request-specific stage nodes and transitions.
- Treat clarification, validation, self-iteration, merge, and handoff as optional capability templates or subgraphs.
- Define `context_contract` as business semantics only.
- Defer access-control policy to a later OpenSpec task.

## Implementation Steps

1. Update the OpenSpec workflow flow requirements so the target model is a graph, not a fixed slot pipeline.
2. Introduce a graph-oriented `workflow-spec.yaml` shape with:
   - `meta`
   - `nodes`
   - `transitions`
   - `templates`
   - `context_contract`
   - `outputs`
   - `runtime_contract`
   - `generated_runtime_contract`
3. Update the runtime generator so it can emit graph-shaped specs and derive views from them.
4. Update validation so it checks graph completeness, transition reachability, template expansion, and output derivation.
5. Update command docs so `/wp-develop` describes AI graph design instead of fixed-slot stage completion.
6. Update the user-facing docs and design index to point at the graph workflow model.

## Decision Rules

- Fixed stage slots are not part of the target design.
- Templates are optional and request-driven.
- Context semantics are part of the design; access control is not.
- Existing fixed-slot code paths should be treated as transitional implementation details until removed.

## Validation Exit Criteria

- A request can produce a valid AI-shaped graph spec without any S1-S6 requirement.
- `workflow-view.md` and `workflow-lowlevel.md` are deterministic derivations of the accepted graph spec.
- Runtime and target bundle generation succeed from the graph-shaped spec.
- The validation stack no longer depends on fixed stage-slot names for the target path.
