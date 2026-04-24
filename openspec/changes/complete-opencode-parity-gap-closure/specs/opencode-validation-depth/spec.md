## ADDED Requirements

### Requirement: Deep Workflow Validators

WorkflowProgram SHALL provide validators beyond the current package/spec/target/run-state baseline for draft design, lowlevel design, generated runtime, lessons delta, and clarification review.

#### Scenario: deep validation runs

- **WHEN** `/wp-validate` or `/wp-audit` requests deep validation
- **THEN** each enabled deep validator SHALL write an independent verdict
- **AND** the validation coordinator SHALL preserve layer ownership

### Requirement: Clarification Review

WorkflowProgram SHALL review clarification artifacts before allowing high-confidence develop or evolve decisions.

#### Scenario: requirements are underspecified

- **WHEN** clarification readiness is below threshold
- **THEN** runtime SHALL emit clarification questions or assumptions
- **AND** mutating execution SHALL be blocked unless explicitly overridden by policy

### Requirement: Golden Fixtures

WorkflowProgram SHALL maintain golden fixtures for representative workflow shapes.

#### Scenario: regression suite runs

- **WHEN** CI executes validation regression
- **THEN** it SHALL run fixtures for at least a sequential workflow, a target command workflow, and a target plugin workflow

### Requirement: CI Coverage

WorkflowProgram SHALL provide a CI entry that validates code compilation, validators, install smoke, host smoke where available, and release artifact integrity.

#### Scenario: CI lacks real OpenCode host

- **WHEN** real host execution is unavailable
- **THEN** CI SHALL still run deterministic tests
- **AND** mark host-dependent checks as skipped rather than passed

