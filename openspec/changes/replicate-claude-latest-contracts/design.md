# Design

## Layer Mapping

Claude upstream uses `workflow_graph.nodes[*].loop_policy`. OpenCode v2 already flattened the target graph, so the equivalent field is:

```yaml
nodes:
  - id: iterate-on-failures
    loop_policy:
      enabled: true
      mode: ralph
      max_iterations: 2
```

`design_refs` remains a top-level optional field because it references run evidence and design-source artifacts rather than one node.

## Design Source Lineage

OpenCode runtime writes structural design-source artifacts under `RUN_ROOT/outputs/stages/`:

- `s1-requirements.yaml`
- `s2-context-findings.yaml`
- `s3-design-highlevel.md`
- `s3-design-lowlevel.md`
- `s3-implementation-plan.md`
- `acceptance-tests.yaml`
- `traceability-matrix.json`
- optional `node-designs/<node-id>.md`

`workflow-spec.yaml.design_refs` points to those safe relative paths. S5 validates existence, node-design projection, and requirement ids appearing in the traceability matrix.

## Node Loop Policy

An enabled node loop must be bounded, machine-verifiable, and evidence-backed:

```yaml
loop_policy:
  enabled: true
  mode: ralph
  goal_source: model_subgoal
  parent_goal_ref: intent.develop.validation_feedback
  max_iterations: 2
  fresh_context_each_iteration: true
  prompt_package: .workflowprogram/loops/iterate-on-failures/prompt-package.md
  feedback_commands:
    - id: run_layered_validation
      kind: validator
      argv: [python3, .workflowprogram/runtime/validate-run-state.py, --run-root, "${RUN_ROOT}"]
      timeout_seconds: 120
      failure_effect: feedback
  stop_conditions:
    success: [verifier_passed]
    max_iterations: warn
    no_progress_iterations: 2
    hard_fail_on: [managed_conflict]
  evidence_outputs:
    - outputs/stages/loops/iterate-on-failures/loop-plan.json
    - outputs/stages/loops/iterate-on-failures/iteration-summary.jsonl
    - outputs/stages/loops/iterate-on-failures/final-verdict.json
```

If any node enables loop execution, `generated_runtime_contract.runtime_capabilities` must include `node_loop_execution`.

## Evidence And Validation

The runner emits deterministic structural loop evidence for generated or accepted specs that declare enabled loop nodes. S5 checks:

- loop evidence files exist;
- `LoopStart`, `LoopIterationStart`, `LoopFeedbackCommandCompleted`, `LoopAgentCompleted`, `LoopVerifierCompleted`, and `LoopStop` events exist;
- observed iterations do not exceed `max_iterations`;
- `PASS` verdict requires verifier/test success;
- `goal_source=model_subgoal` includes `parent_goal_ref`;
- TDD loops record test-first behavior.

This is a contract/evidence check, not a direct OpenCode subagent invocation. OpenCode host/model remains responsible for real AI work; Python records and validates the accepted contract.

