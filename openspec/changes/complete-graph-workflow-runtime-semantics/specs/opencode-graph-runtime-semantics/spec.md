## ADDED Requirements

### Requirement: Optional Self-Iteration Contract

WorkflowProgram OpenCode SHALL treat self-iteration as an optional graph capability, not a mandatory workflow stage.

#### Scenario: self-iteration is selected

- **WHEN** `workflow-spec.yaml` selects a `self-iteration-loop` template
- **THEN** the template SHALL declare `max_attempts`
- **AND** the template SHALL declare `stop_conditions`
- **AND** the graph SHALL contain a retry transition from failure handling back to generation or repair work
- **AND** the graph SHALL contain a terminal handoff transition when iteration stops

### Requirement: Structured Lessons Evidence

WorkflowProgram OpenCode SHALL emit structured lessons evidence at terminal runtime handoff.

#### Scenario: mutation run completes

- **WHEN** a mutating run reaches terminal state
- **THEN** runtime SHALL write lessons with observations, failure patterns, reusable constraints, residual risks, evolve recommendations, and source verdicts
- **AND** lessons validation SHALL check structure and consistency with validation and judge verdicts

### Requirement: Lessons Feed Evolve Design

WorkflowProgram OpenCode SHALL make prior lessons available to evolve design without automatically mutating workflow semantics.

#### Scenario: evolve starts

- **WHEN** `/wp-evolve` prepares design context
- **THEN** runtime SHALL surface latest prior lessons when available
- **AND** any workflow change SHALL still require accepted `workflow-spec.md` and `workflow-spec.yaml`

### Requirement: Clarification Uses Existing Artifacts

WorkflowProgram OpenCode SHALL improve clarification method without adding a parallel artifact chain.

#### Scenario: clarification is required

- **WHEN** `/wp-develop` asks clarification questions
- **THEN** questions SHALL cover divergent workflow options, hard constraints, convergence criteria, and readback confirmation
- **AND** outputs SHALL remain the existing clarification files

### Requirement: OpenCode Hook Declarations

WorkflowProgram OpenCode SHALL represent target hook behavior through explicit target plugin declarations.

#### Scenario: target plugin is generated

- **WHEN** `workflow-spec.yaml` declares `registry.plugins`
- **THEN** each plugin SHALL declare hook intents and hook events
- **AND** generated target plugin files SHALL implement only declared OpenCode hook behavior
- **AND** validators SHALL reject target plugin declarations that conflict with package plugin identity

