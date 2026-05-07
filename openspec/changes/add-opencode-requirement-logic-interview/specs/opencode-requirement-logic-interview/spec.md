## ADDED Requirements

### Requirement: OpenCode SHALL enforce S1 requirement-logic interview evidence

OpenCode `develop` runs SHALL produce requirement-logic evidence that is equivalent in product behavior to Claude upstream S1 while using OpenCode-native package/runtime files.

#### Scenario: ready develop run records logic lenses

- **WHEN** `/wp-develop` runs after accepted readback
- **THEN** the run SHALL include `question-backlog.json`
- **AND** the run SHALL include `requirement-logic-map.json`
- **AND** the logic map SHALL contain `purpose`, `object_model`, `process_model`, `decision_model`, `evidence_model`, `acceptance_model`, and `boundary_model`
- **AND** the evidence SHALL be available under both `outputs/clarification/` and `outputs/stages/`

#### Scenario: shallow draft is rejected

- **WHEN** a `workflow-spec.md` draft lacks required S1 sections, has fewer than two clarification rounds, or only asks generic questions
- **THEN** `validate-workflow-draft.py` SHALL fail
- **AND** it SHALL report deterministic failed checks instead of relying on host model judgment

#### Scenario: S5 validates handoff

- **WHEN** a develop run reaches S5
- **THEN** S5 SHALL check that S2 and S3 handoff evidence references the logic map and question backlog
- **AND** ready runs SHALL require readback confirmation plus `logic_map_ready`, `s2_handoff_ready`, and `s3_handoff_ready`

#### Scenario: team plan is not subagent proof

- **WHEN** AgentTeam planner emits recommended dispatch
- **THEN** the planner output SHALL remain advisory
- **AND** the run SHALL NOT claim subagent execution unless host-mediated dispatch leaves separate evidence
