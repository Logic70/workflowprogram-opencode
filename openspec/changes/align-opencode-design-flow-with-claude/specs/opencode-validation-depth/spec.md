## MODIFIED Requirements

### Requirement: Deep Workflow Validators

Deep validation SHALL prioritize existing WorkflowProgram artifact relationships over OpenCode-specific collaboration markers.

#### Scenario: develop run is validated

- **WHEN** a completed develop run is validated
- **THEN** validators SHALL check `workflow-spec.md` draft quality when present
- **AND** validators SHALL check clarification package and handoff evidence when S1 is complete
- **AND** validators SHALL check `workflow-spec.yaml`
- **AND** validators SHALL check deterministic derivation of `workflow-view.md` and `workflow-lowlevel.md`
- **AND** validators SHALL check generated runtime and managed apply evidence

### Requirement: Host Smoke Is Visibility Evidence

Host smoke SHALL prove OpenCode host visibility only, not workflow semantic correctness.

#### Scenario: host smoke passes

- **WHEN** OpenCode can discover package or target commands/plugins
- **THEN** host smoke SHALL record host visibility PASS
- **AND** workflow success SHALL still depend on design, spec, generated artifact, validation, and managed apply checks

### Requirement: No New Core Validation Domain

OpenCode SHALL NOT introduce a new core validation domain solely for AI design participation.

#### Scenario: AI participation is inspected

- **WHEN** validation needs to reason about AI or agent participation
- **THEN** the check SHALL attach to draft design, clarification evidence, spec validation, or run-state evidence
- **AND** validation SHALL NOT introduce `AI-DESIGN-*` as a separate product concept

