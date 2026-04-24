## ADDED Requirements

### Requirement: Clean Release Build

WorkflowProgram SHALL provide a repeatable build step that emits a clean OpenCode package artifact.

#### Scenario: release package is built

- **WHEN** the build script runs
- **THEN** it SHALL copy only release-eligible package files
- **AND** it SHALL exclude runtime runs, caches, local dependency trees, logs, and secrets
- **AND** it SHALL write a release manifest with source commit, checksums, included files, and excluded patterns

### Requirement: Release Install Smoke

WorkflowProgram SHALL validate installation from the release artifact, not only from the development `package/` directory.

#### Scenario: release artifact is tested

- **WHEN** install smoke runs against release output
- **THEN** package commands, package agents, package plugin, runtime, validators, and venv behavior SHALL be checked

### Requirement: Upgrade And Uninstall Lifecycle

WorkflowProgram installation SHALL support repeated install, upgrade, status, and uninstall verification.

#### Scenario: repeated install is requested

- **WHEN** the same package version is installed twice
- **THEN** install SHALL be idempotent
- **AND** it SHALL not duplicate config entries or corrupt managed manifests

### Requirement: Offline Dependency Path

WorkflowProgram installation SHALL support a documented offline or locked dependency path for Python runtime dependencies.

#### Scenario: network is unavailable

- **WHEN** install cannot reach package indexes
- **THEN** installer SHALL either use the locked/offline dependency path or report a typed remediation

