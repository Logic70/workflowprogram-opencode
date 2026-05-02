## ADDED Requirements

### Requirement: Runtime Consumes Accepted Spec

OpenCode runtime SHALL consume an accepted `workflow-spec.yaml` for generation, validation, target runtime creation, and managed apply.

#### Scenario: mutation reaches generation

- **WHEN** a mutating intent reaches target bundle generation
- **THEN** runtime SHALL load and validate `RUN_ROOT/workflow-spec.yaml`
- **AND** generated target design files SHALL include the same accepted spec
- **AND** managed apply SHALL use the generated candidate bundle

### Requirement: Runtime Does Not Consume Design Views

Runtime SHALL NOT require generated design views as semantic inputs.

#### Scenario: mutation reaches generation

- **WHEN** runtime generates target assets
- **THEN** it SHALL use `workflow-spec.yaml` as the semantic input
- **AND** it SHALL NOT require `workflow-view.md`, `workflow-lowlevel.md`, `workflow-spec.proposed.yaml`, `design-brief.md`, or `ai-design-source.json`

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
- **THEN** runtime SHALL require completed readiness/handoff evidence when policy requires clarification/readback completion
- **AND** a standalone CLI confirmation flag SHALL NOT be the only source of truth
- **AND** `--confirmed` SHALL only be valid when paired with accepted `workflow-spec.md`, accepted `workflow-spec.yaml`, and readback evidence

## MODIFIED Requirements

### Requirement: OpenCode Agent Planning

OpenCode agent planning SHALL remain advisory unless its outputs are converted into the standard WorkflowProgram design artifacts.

#### Scenario: team plan exists

- **WHEN** `team-plan.json` or `team-plan.md` exists
- **THEN** runtime MAY preserve it as host-dispatch guidance
- **AND** validators SHALL NOT require it for core develop success
