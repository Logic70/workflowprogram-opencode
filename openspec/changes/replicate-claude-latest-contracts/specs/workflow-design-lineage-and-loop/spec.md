# workflow-design-lineage-and-loop Specification

## ADDED Requirements

### Requirement: Design source refs use OpenCode run evidence paths

`workflow-spec.yaml.design_refs` MAY reference design-source artifacts and MUST use safe relative paths under `outputs/stages/`. `node_designs` entries MUST stay under `outputs/stages/node-designs/`.

#### Scenario: Design ref escapes run evidence root

- **GIVEN** a spec declares `design_refs.design_lowlevel: ../secret.md`
- **WHEN** spec validation runs
- **THEN** validation MUST fail.

### Requirement: S5 validates declared design lineage

When `design_refs` are declared, S5 SHALL verify referenced files exist, node-design ids reference declared `nodes[*].id`, and requirement ids appear in `traceability-matrix.json`.

#### Scenario: Requirement is not mapped

- **GIVEN** `s1-requirements.yaml` contains `REQ-001`
- **AND** `traceability-matrix.json` does not reference `REQ-001`
- **WHEN** S5 validates the run
- **THEN** S5 MUST fail the lineage check.

### Requirement: OpenCode nodes SHALL support bounded loop policy declarations

`workflow-spec.yaml.nodes[*].loop_policy` MAY declare a Ralph-style loop for that OpenCode target graph node. When declared, the loop policy MUST be bounded, evidence-backed, and safe to validate deterministically.

#### Scenario: Loop policy is enabled

- **GIVEN** a node declares `loop_policy.enabled=true`
- **WHEN** spec validation runs
- **THEN** validation MUST require bounded iterations, structured feedback commands, safe prompt paths, safe evidence paths, and explicit stop conditions.

### Requirement: Node loop requires runtime capability

If any node declares `loop_policy.enabled=true`, `generated_runtime_contract.runtime_capabilities` MUST include `node_loop_execution`.

#### Scenario: Runtime capability is missing

- **GIVEN** a node declares an enabled loop policy
- **AND** runtime capabilities do not include `node_loop_execution`
- **WHEN** spec validation runs
- **THEN** validation MUST fail.

### Requirement: Loop PASS requires verifier evidence

An enabled loop node MUST NOT pass based only on model self-report.

#### Scenario: Final verdict passes without verifier

- **GIVEN** `final-verdict.json` declares `status: PASS`
- **AND** `verifier_passed` is false or missing
- **WHEN** S5 validates loop evidence
- **THEN** S5 MUST fail.
