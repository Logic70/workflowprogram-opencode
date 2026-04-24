## ADDED Requirements

### Requirement: Target Host Reload Smoke

WorkflowProgram SHALL provide a smoke test that validates generated target workflow assets in a real OpenCode host when the environment supports it.

#### Scenario: target command is generated

- **WHEN** a target bundle declares generated target commands
- **THEN** target host reload smoke SHALL verify that OpenCode can discover the generated target command
- **AND** it SHALL keep this verdict separate from package command discovery

#### Scenario: target plugin is generated

- **WHEN** a target bundle declares generated target plugins
- **THEN** target host reload smoke SHALL verify that OpenCode can discover or execute the target plugin bridge when host support is available

### Requirement: Host Smoke Outcome Classification

Host smoke SHALL classify environment limitations separately from product defects.

#### Scenario: provider credentials are unavailable

- **WHEN** `opencode` exists but provider/API execution cannot complete
- **THEN** smoke SHALL return `ENVIRONMENT-SKIP` for provider-dependent execution
- **AND** static discovery failures SHALL still be reported as `FAIL`

### Requirement: Deterministic Target Fixture Fallback

WorkflowProgram SHALL provide deterministic target fixture validation for CI environments without real host execution.

#### Scenario: CI lacks OpenCode host

- **WHEN** OpenCode CLI is unavailable
- **THEN** CI SHALL validate target host-visible files and contracts
- **AND** it SHALL NOT claim real host execution passed

