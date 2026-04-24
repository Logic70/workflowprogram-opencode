## ADDED Requirements

### Requirement: Agent Role Schema

WorkflowProgram OpenCode package agents SHALL include machine-readable role metadata that remains compatible with OpenCode agent frontmatter.

#### Scenario: package agent is validated

- **WHEN** package validation scans `.opencode/agents/*.md`
- **THEN** each required WorkflowProgram agent SHALL declare role identity, stage affinity, capability tags, trigger policy, and priority
- **AND** validation SHALL fail when a required role is missing or malformed

### Requirement: Agentteam Is A Planning Model

WorkflowProgram SHALL treat agentteam as a workflow planning model, not as a synonym for one OpenCode subagent.

#### Scenario: a stage needs multiple reviews

- **WHEN** a stage requires logic, security, performance, and style review
- **THEN** the team planner MAY dispatch multiple subagents in parallel
- **AND** a fan-in verifier SHALL summarize and resolve the review outputs

#### Scenario: a stage needs no specialist

- **WHEN** a stage can be handled by deterministic runtime validation
- **THEN** the team planner SHALL allow zero subagent dispatch for that stage

### Requirement: Test Scenario Generator Role

WorkflowProgram OpenCode SHALL include a `test-scenario-generator` package agent.

#### Scenario: audit or validate needs scenario coverage

- **WHEN** audit or validate requests scenario analysis
- **THEN** the test scenario generator SHALL produce structured test scenario evidence
- **AND** validators SHALL be able to find the evidence in `RUN_ROOT`

