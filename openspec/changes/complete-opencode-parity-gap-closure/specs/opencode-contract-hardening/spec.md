## ADDED Requirements

### Requirement: Schema Versions

WorkflowProgram SHALL include `schema_version` in workflow spec, managed manifest, run-state, and install manifest files.

#### Scenario: validator reads a versioned file

- **WHEN** a validator reads a versioned contract file
- **THEN** it SHALL check compatibility before applying current validation rules

### Requirement: Migration Reports

WorkflowProgram SHALL provide explicit migration reports for supported schema upgrades.

#### Scenario: migration succeeds

- **WHEN** migration changes a contract file
- **THEN** it SHALL write a migration report with from-version, to-version, changed files, backup location, and warnings

### Requirement: Managed Apply Recovery

Managed apply SHALL support locking, idempotency, rollback metadata, and recoverable failure states.

#### Scenario: concurrent apply is attempted

- **WHEN** another active apply lock exists for the target root
- **THEN** managed apply SHALL refuse or wait according to policy
- **AND** it SHALL not partially overwrite target files

#### Scenario: apply fails mid-write

- **WHEN** managed apply fails after writing at least one file
- **THEN** it SHALL leave enough rollback or recovery metadata for doctor to explain the next safe action

### Requirement: Unified Error Codes

Runtime, validators, doctor, smoke, and plugin hook logs SHALL use a shared error code taxonomy.

#### Scenario: failure is reported

- **WHEN** any component reports a failure
- **THEN** the result SHALL include a stable error code, failure class, human summary, and remediation hint

### Requirement: Permission And Privacy Policy

WorkflowProgram SHALL define write, shell, log, and redaction policy for all product intents.

#### Scenario: evidence is written

- **WHEN** runtime writes logs or reports
- **THEN** configured secrets, provider tokens, and sensitive environment variables SHALL be redacted

