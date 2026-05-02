## ADDED Requirements

### Requirement: AI-Guided Workflow Graph Design

WorkflowProgram OpenCode SHALL let AI define the workflow graph for a request, while the framework enforces a fixed spec shape and deterministic execution.

#### Scenario: user runs develop

- **WHEN** the user invokes `/wp-develop`
- **THEN** the command SHALL drive design and clarification into `RUN_ROOT/workflow-spec.md`
- **AND** the accepted machine workflow SHALL be represented by `RUN_ROOT/workflow-spec.yaml`
- **AND** the workflow graph SHALL be expressed as AI-defined stage nodes and transitions within the allowed spec shape
- **AND** Python SHALL validate and execute from the accepted spec rather than generating workflow semantics from a hidden fixed-stage template

### Requirement: Interactive Clarification Gate

`/wp-develop` SHALL clarify broad requests before runtime execution.

#### Scenario: broad develop request is received

- **WHEN** the user invokes `/wp-develop` with a broad workflow request
- **THEN** the command SHALL ask clarification questions before running runtime generation
- **AND** the questions SHALL cover graph shape, self-iteration need, CLI command need, plugin hook need, and enough business context to design the workflow
- **AND** the first clarification round SHOULD stay concise and defer secondary questions until needed

### Requirement: Graph Design Readback

The command SHALL read back the accepted workflow design before apply.

#### Scenario: clarification answers are available

- **WHEN** the command has enough information to propose a design
- **THEN** it SHALL summarize nodes, edges, shared context, enabled capabilities, disabled capabilities, and files that will be written
- **AND** it SHALL ask for explicit confirmation before adding `--confirmed` or running runtime generation/apply
- **AND** vague continuation SHALL NOT be treated as confirmation unless the user clearly confirms writing artifacts and running runtime

### Requirement: Single Machine Source

`workflow-spec.yaml` SHALL be the only machine-readable source of workflow semantics.

#### Scenario: generated artifacts are produced

- **WHEN** target runtime files or target OpenCode assets are generated
- **THEN** they SHALL be derived from `workflow-spec.yaml`
- **AND** they SHALL NOT introduce semantic fields that are absent from `workflow-spec.yaml`
- **AND** `workflow-view.md` and `workflow-lowlevel.md` SHALL NOT be required as core design artifacts

### Requirement: Existing Draft And Clarification Artifacts

OpenCode SHALL reuse the existing draft and clarification evidence chain instead of adding parallel AI design artifacts.

#### Scenario: design evidence is required

- **WHEN** validation needs to prove that design and readback occurred
- **THEN** it SHALL inspect `workflow-spec.md` and the existing `clarification-*` evidence files
- **AND** it SHALL NOT require `workflow-spec.proposed.yaml`, `design-brief.md`, `workflow-view.md`, `workflow-lowlevel.md`, or `ai-design-source.json`

### Requirement: Template Capabilities Are Optional

Reusable workflow capabilities MAY be offered as templates or subgraphs, but they SHALL be optional design inputs rather than fixed stage slots.

#### Scenario: a request needs self-iteration or clarification loops

- **WHEN** the request benefits from a reusable capability such as self-iteration, clarification, validation, or handoff
- **THEN** AI MAY include the capability template in the workflow graph
- **AND** the framework SHALL NOT force a fixed slot layout such as S1-S6
- **AND** the chosen template SHALL still be expanded into the accepted workflow graph for this request

## MODIFIED Requirements

### Requirement: AI Collaboration Evidence

AI or package-agent participation MAY be recorded as supplemental evidence, but it SHALL NOT be the acceptance signal for completed workflow design.

#### Scenario: ai evidence exists without accepted design artifacts

- **WHEN** a run contains `ai_evidence`, `state.ai_collaboration`, or `team-plan` output
- **AND** the run lacks accepted `workflow-spec.md`, clarification handoff evidence, or `workflow-spec.yaml`
- **THEN** validation SHALL NOT treat the run as a completed design flow

### Requirement: Context Semantics First

The workflow spec SHALL define shared context semantics before access control.

#### Scenario: context is designed

- **WHEN** the workflow graph defines shared inputs, outputs, authoritative sources, or derived data
- **THEN** the spec SHALL describe those business semantics explicitly
- **AND** it SHALL NOT require a read/write permission model in this change
- **AND** access control policies SHALL be tracked as deferred work in OpenSpec
