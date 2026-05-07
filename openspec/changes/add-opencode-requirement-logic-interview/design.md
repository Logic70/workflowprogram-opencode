# Design: OpenCode Requirement Logic Interview

## Goal

OpenCode must preserve the Claude upstream S1 product behavior without copying Claude host structures. The host/model still conducts the conversation; Python records, validates, and gates the accepted evidence.

## Runtime Evidence

For `develop`, runtime writes the existing clarification evidence plus two mandatory requirement-logic artifacts:

- `outputs/clarification/question-backlog.json`
- `outputs/clarification/requirement-logic-map.json`
- mirrored copies under `outputs/stages/` for S5 and design-source lineage checks

The logic map records seven lenses:

- `purpose`
- `object_model`
- `process_model`
- `decision_model`
- `evidence_model`
- `acceptance_model`
- `boundary_model`

Each backlog item must explain why the answer changes graph design, evidence, acceptance, or boundaries. Generic questions are allowed only as secondary prompts, not as primary evidence for M+ requests.

## Roles

`requirement-clarification-lead` is the only user-facing role. `scenario-extractor`, `assumption-auditor`, and `constraint-reviewer` remain internal challenge roles and must not claim direct user contact.

## Validation

`validate-workflow-draft.py` validates:

- required draft sections;
- clarification rounds `>= 2`;
- all seven logic lenses;
- shallow generic-only questions fail;
- stage clarification evidence exists when a run root is provided.

`run_state_validator.py` validates the package content and handoff readiness.

`workflow-s5-judge.py` validates:

- all S1 requirement-logic artifacts exist;
- logic lenses are complete;
- question backlog is design-consequential;
- review roles are internal-only;
- S2/S3 handoff references logic map and question backlog;
- ready runs have confirmed readback and ready handoff evidence.

## AgentTeam Boundary

AgentTeam remains a team topology and dispatch guide. It does not execute subagents by itself. A subagent is considered executed only when OpenCode host dispatch leaves a separate agent response or dispatch trace.
