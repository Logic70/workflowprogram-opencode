## ADDED Requirements

### Requirement: Product Intent Contract Consistency

WorkflowProgram OpenCode SHALL maintain a single product intent contract that maps each supported intent to its command file, runtime id, runtime handler, mutation policy, evidence outputs, and optional target spec flow.

#### Scenario: supported intent is added

- **WHEN** a new product intent is introduced
- **THEN** the command file, runtime supported intent list, runtime handler, validation expectations, and documentation SHALL be updated in the same change
- **AND** contract validation SHALL fail if any mapping is missing

#### Scenario: spec contains unsupported flow

- **WHEN** generated `workflow-spec.yaml` contains an `intent_flows` entry
- **THEN** the spec validator SHALL verify that the flow maps to a supported product or target intent
- **AND** `audit` SHALL NOT appear as a dangling flow without `/wp-audit` and runtime support

### Requirement: Audit Intent

WorkflowProgram OpenCode SHALL provide a non-mutating `audit` intent exposed as `/wp-audit`.

#### Scenario: user runs audit

- **WHEN** the user invokes `/wp-audit`
- **THEN** runtime SHALL inspect package contract, target bundle, run-state evidence, lessons, and host visibility evidence
- **AND** runtime SHALL emit an audit report without modifying target files

### Requirement: Evolve Intent

WorkflowProgram OpenCode SHALL provide an `evolve` intent exposed as `/wp-evolve` for managed improvements based on audit, validation, or lessons evidence.

#### Scenario: user runs evolve

- **WHEN** the user invokes `/wp-evolve`
- **THEN** runtime SHALL require an existing target workflow
- **AND** runtime SHALL create an evolve plan before mutation
- **AND** any write SHALL go through managed apply

### Requirement: Orchestrate Intent

WorkflowProgram OpenCode SHALL provide `/wp-orchestrate` as a routing entry for natural-language product actions.

#### Scenario: route confidence is low

- **WHEN** route intent confidence is below the configured threshold
- **THEN** runtime SHALL produce clarification questions
- **AND** runtime SHALL NOT execute a mutating intent

