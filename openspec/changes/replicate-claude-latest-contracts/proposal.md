# Replicate Claude Latest Workflow Contracts

## Summary

Port the latest portable Claude WorkflowProgram semantics to the OpenCode package without copying Claude-specific plugin packaging.

## Motivation

Claude upstream added two workflow-level contracts that affect generated workflow quality:

- Design source lineage: `workflow-spec.yaml` can reference S1/S2/S3 design artifacts and S5 checks the requirement-to-evidence chain.
- Node loop policy: individual workflow graph nodes can declare bounded Ralph-style iteration with structured verifier/test evidence.

OpenCode already uses an independent flattened graph schema (`nodes`, `transitions`, `templates`, `intent_routes`). The port must preserve that schema and map the new semantics to OpenCode-native fields.

## Non-Goals

- Do not copy Claude `.claude/**` paths or Claude plugin release tooling.
- Do not make WorkflowProgram package loading depend on generated target workflow fields.
- Do not treat model self-report as loop success evidence.

