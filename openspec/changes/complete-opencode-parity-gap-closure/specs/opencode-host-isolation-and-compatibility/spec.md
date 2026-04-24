## ADDED Requirements

### Requirement: Host Source Inventory

WorkflowProgram doctor SHALL inventory host-visible asset sources that can affect OpenCode discovery.

#### Scenario: external assets are visible

- **WHEN** doctor runs in a project
- **THEN** it SHALL report project-local OpenCode assets, global OpenCode config assets, potential ClaudeCode assets, and known third-party packs such as oh-my-opencode when detectable
- **AND** it SHALL classify risks without deleting user assets

### Requirement: Namespace Shadowing Detection

WorkflowProgram doctor SHALL detect namespace shadowing across commands, agents, skills, and plugins.

#### Scenario: duplicate command exists

- **WHEN** a non-WorkflowProgram asset defines a command or role that shadows a WorkflowProgram asset
- **THEN** doctor SHALL emit a `namespace_shadowing` finding
- **AND** remediation SHALL identify the source path and suggested isolation step

### Requirement: OpenCode Compatibility Matrix

WorkflowProgram SHALL maintain a compatibility matrix for OpenCode versions and plugin API assumptions.

#### Scenario: host version is unsupported

- **WHEN** doctor detects an unsupported or unknown OpenCode version
- **THEN** it SHALL return a compatibility warning
- **AND** host smoke SHALL avoid reporting false PASS for plugin behavior

### Requirement: Reload Guidance

WorkflowProgram SHALL document and diagnose when OpenCode requires restart, project reopen, or cache cleanup after package/plugin changes.

#### Scenario: package plugin changed

- **WHEN** installed plugin source differs from the last recorded manifest
- **THEN** doctor SHALL indicate that a host reload may be required

