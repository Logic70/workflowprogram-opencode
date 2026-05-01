## ADDED Requirements

### Requirement: Runtime Consumes Accepted Spec

OpenCode runtime SHALL consume an accepted `workflow-spec.yaml` for generation, validation, target runtime creation, and managed apply.

#### Scenario: mutation reaches generation

- **WHEN** a mutating intent reaches target bundle generation
- **THEN** runtime SHALL load and validate `RUN_ROOT/workflow-spec.yaml`
- **AND** generated target design files SHALL include the same accepted spec
- **AND** managed apply SHALL use the generated candidate bundle

### Requirement: Template Generation Is Not Default

Python template generation SHALL NOT be the default design path for production mutating intents.

#### Scenario: fallback is requested

- **WHEN** an explicit fallback or fixture path uses built-in templates
- **THEN** the run SHALL record that fallback was used
- **AND** the run SHALL NOT be reported as equivalent to the normal ClaudeCode-aligned design path

### Requirement: Confirmation From Evidence

Runtime SHALL derive design readiness and readback confirmation from existing evidence files.

#### Scenario: apply is requested

- **WHEN** managed apply would write target workflow assets
- **THEN** runtime SHALL require completed readiness/handoff evidence when policy requires S1 completion
- **AND** a standalone CLI confirmation flag SHALL NOT be the only source of truth

## MODIFIED Requirements

### Requirement: OpenCode Agent Planning

OpenCode agent planning SHALL remain advisory unless its outputs are converted into the standard WorkflowProgram design artifacts.

#### Scenario: team plan exists

- **WHEN** `team-plan.json` or `team-plan.md` exists
- **THEN** runtime MAY preserve it as host-dispatch guidance
- **AND** validators SHALL NOT require it for core develop success

