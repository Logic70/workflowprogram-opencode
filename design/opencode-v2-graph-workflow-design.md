# OpenCode V2 Graph Workflow Design

This document records the target workflow model after removing fixed S1-S6 stage slots.

## Goal

WorkflowProgram should let AI define the workflow graph for each request, while the framework keeps the spec shape, validation, generation, and managed apply deterministic.

## Target Model

The workflow spec should be organized around three layers:

1. Graph primitives
   - nodes
   - transitions
   - shared context
   - evidence

2. Capability templates
   - clarification loop
   - self-iteration loop
   - validation loop
   - merge / fan-in
   - handoff

3. Request-specific instance graph
   - AI chooses which templates to use
   - AI expands the templates into the request graph
   - AI defines node names, transition conditions, and flow order

## Spec Shape

`workflow-spec.yaml` should keep a fixed outer schema, but its graph contents should be request-specific.

Recommended top-level sections:

- `meta`
- `nodes`
- `transitions`
- `templates`
- `context_contract`
- `outputs`
- `runtime_contract`
- `generated_runtime_contract`

## Context Semantics

`context_contract` should describe business semantics only:

- shared inputs
- shared outputs
- authoritative sources
- derived data

Access control is deferred. This change does not define stage-based, agent-based, or hybrid read/write policy.

## Validation

Validation should focus on:

- node schema completeness
- transition validity and reachability
- template expansion correctness
- deterministic derivation of `workflow-view.md` and `workflow-lowlevel.md`
- runtime / target bundle consistency with the accepted graph

## Migration Rule

Fixed stage-slot logic is not part of the target design.
Reusable behaviors may remain as templates, but only as optional inputs selected by AI for the request at hand.
