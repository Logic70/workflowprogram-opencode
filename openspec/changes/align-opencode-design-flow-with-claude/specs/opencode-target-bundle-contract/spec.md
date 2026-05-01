## ADDED Requirements

### Requirement: Spec-Selected Target OpenCode Assets

Target OpenCode command and plugin assets SHALL be generated only when selected by `workflow-spec.yaml`.

#### Scenario: spec does not request target command or plugin

- **WHEN** `workflow-spec.yaml` has no target command or target plugin registry entry
- **THEN** target bundle generation SHALL NOT create `.opencode/commands/*` or `.opencode/plugins/*`
- **AND** target bundle validation SHALL NOT fail because those assets are absent

#### Scenario: spec requests target command or plugin

- **WHEN** `workflow-spec.yaml` declares target command or plugin assets
- **THEN** target bundle generation SHALL create only those declared assets
- **AND** validators SHALL verify that generated target OpenCode assets match the spec and do not occupy package `/wp-*` names

### Requirement: Generated Runtime Matches Spec

Target runtime assets SHALL be generated from `workflow-spec.yaml` and validated against it.

#### Scenario: target runtime is validated

- **WHEN** target runtime validation runs
- **THEN** it SHALL verify that runtime manifest, entry, runner, and validator assets correspond to the accepted workflow spec
- **AND** it SHALL NOT treat a merely reachable wrapper as sufficient semantic proof

