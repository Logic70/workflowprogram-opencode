## 1. Design And Scope Alignment

- [x] 1.1 Update `design/opencode-v2-lowlevel-design.md` so the adopted model is "AI/user design + Python validation/apply", not "Python generates all workflow semantics".
- [x] 1.2 Update `design/opencode-v2-highlevel-design.md` to state that OpenCode adapts host mechanics only; WorkflowProgram artifact semantics remain ClaudeCode-aligned.
- [x] 1.3 Update `design/opencode-v2-implementation-plan.md` to make `/wp-develop` main-chain acceptance depend on `workflow-spec.md`, clarification evidence, `workflow-spec.yaml`, generated views, target runtime generation, and managed apply.
- [x] 1.4 Update `design/opencode-v2-validation-matrix.md` to remove `ai_evidence` / `state.ai_collaboration` as core acceptance signals.
- [x] 1.5 Mark `add-ai-collaboration-layer` semantics as superseded by this change in documentation; do not revert its useful host-dispatch assets.

## 2. Command Flow Correction

- [x] 2.1 Update `package/.opencode/commands/wp-develop.md` to follow the ClaudeCode flow: design draft, clarification evidence, YAML spec, deterministic generation, managed apply.
- [x] 2.2 Update `wp-evolve.md`, `wp-hotfix.md`, and `wp-iterate.md` so mutating paths require an existing accepted `workflow-spec.yaml` or a completed design/update draft before managed apply.
- [x] 2.3 Remove command instructions that treat `--ai-evidence` as proof that design happened.
- [x] 2.4 Keep `agent-team-planner.py` usage optional and advisory; command success must depend on the WorkflowProgram artifacts, not `team-plan`.
- [x] 2.5 Do not introduce user-visible prepare/resume steps.

## 3. Runtime Main Path Correction

- [x] 3.1 Modify `workflow-entry.py` so `--ai-evidence` is deprecated or ignored for success gating.
- [x] 3.2 Modify `workflow-runner.py` so production `/wp-develop` does not call `_build_workflow_spec()` as the default semantic generator.
- [x] 3.3 Move `_build_workflow_spec()` behind an explicit fixture/fallback path that records a WARN verdict and cannot be mistaken for the normal design path.
- [x] 3.4 Add or reuse a runtime path that reads `RUN_ROOT/workflow-spec.yaml`, validates it, and uses it as the machine source for generation.
- [x] 3.5 Ensure runtime blocks mutating apply when `workflow-spec.md` or clarification handoff evidence is required but missing.
- [x] 3.6 Ensure readback confirmation comes from `clarification-evidence.json` / `design-readiness-report.json`, not from a standalone CLI truth source.

## 4. Artifact Generation Alignment

- [x] 4.1 Reuse the existing `workflow-spec.md` draft format instead of adding `workflow-spec.proposed.yaml`.
- [x] 4.2 Reuse existing clarification package and review scripts instead of adding `ai-design-source.json`.
- [x] 4.3 Generate `workflow-view.md` only from `workflow-spec.yaml`.
- [x] 4.4 Generate `workflow-lowlevel.md` only from `workflow-spec.yaml`.
- [x] 4.5 Generate target runtime assets only from `workflow-spec.yaml`.
- [x] 4.6 Generate target `.opencode/commands/*` and `.opencode/plugins/*` only when `workflow-spec.yaml` explicitly declares them.

## 5. Validator And Acceptance Updates

- [x] 5.1 Update package/run-state validators so `context.ai_evidence` and `state.ai_collaboration` are not required for PASS.
- [x] 5.2 Reuse or port the ClaudeCode draft validator for `workflow-spec.md`.
- [x] 5.3 Require clarification package files when the develop path claims S1 is complete.
- [x] 5.4 Validate that `workflow-view.md` and `workflow-lowlevel.md` are deterministic derivations of `workflow-spec.yaml`.
- [x] 5.5 Validate that persistent `TARGET_ROOT/.workflowprogram/design/workflow-spec.yaml` matches the accepted `RUN_ROOT/workflow-spec.yaml` for the develop run.
- [x] 5.6 Validate that target runtime assets match `workflow-spec.yaml`.
- [x] 5.7 Keep host smoke as host visibility evidence only; do not use it as workflow semantic success.

## 6. Fixture And Regression Coverage

- [x] 6.1 Add a fixture where `/wp-develop` completes via `workflow-spec.md` -> clarification evidence -> `workflow-spec.yaml` -> generated assets -> managed apply.
- [x] 6.2 Add a fixture where Python-only template generation is attempted without explicit fallback and must fail or warn before apply.
- [x] 6.3 Add a fixture where `--ai-evidence` is supplied but `workflow-spec.md` / clarification handoff is missing; the run must not pass as a valid design flow.
- [x] 6.4 Add a fixture where target command generation is absent from spec and no target command is generated.
- [x] 6.5 Add a fixture where target command/plugin generation is explicitly declared in spec and generated assets pass target bundle validation.
- [x] 6.6 Add regression coverage proving `workflow-view.md` and `workflow-lowlevel.md` cannot be edited as semantic sources.

## 7. Historical Compatibility And Cleanup

- [x] 7.1 Keep existing installed-package and host-isolation behavior unless it conflicts with the corrected design flow.
- [x] 7.2 Keep package agents and role metadata, but remove any validator requirement that treats agentteam evidence as mandatory for core develop success.
- [x] 7.3 Preserve backwards compatibility for existing runs where possible, but classify old `ai_evidence`-only runs as legacy evidence rather than valid design-source runs.
- [x] 7.4 Remove or deprecate documentation that presents `AI-DISPATCH-SKIPPED` as an acceptable successful mutation path.
- [x] 7.5 Keep global bootstrap and release tasks separate from workflow design semantics.

## 8. Final Verification

- [x] 8.1 Run Python compile checks for changed runtime and validator files.
- [x] 8.2 Run spec validator on at least one accepted `workflow-spec.yaml`.
- [x] 8.3 Run draft/clarification validators on at least one accepted `workflow-spec.md`.
- [x] 8.4 Run target bundle validator on a generated target workflow without target command/plugin assets.
- [x] 8.5 Run target bundle validator on a generated target workflow with spec-declared target command/plugin assets.
- [ ] 8.6 Run smoke harness and ensure host-only skips are reported as skips, not semantic passes.
- [x] 8.7 Document residual gaps if any ClaudeCode behavior is still not matched.

Residual verification note:
- Full `smoke-harness.py` was attempted locally after switching it to `sys.executable`, but timed out after 244 seconds in this environment. Focused runtime, spec, draft, run-state, and target-bundle validations passed.

## 9. Graph Workflow Migration

- [ ] 9.1 Replace fixed `S1-S6` stage slots in the workflow spec model with AI-defined stage nodes and transitions.
- [ ] 9.2 Define reusable capability templates or subgraphs for common behaviors such as clarification, validation, self-iteration, merge, and handoff.
- [ ] 9.3 Add an explicit `context_contract` section that describes shared inputs, outputs, authoritative sources, and derived data without access-control policy.
- [ ] 9.4 Update workflow generation so templates are optional inputs selected by AI, not mandatory stage slots.
- [ ] 9.5 Update validators so graph structure, transitions, and template expansion are validated without depending on fixed slot names.
- [ ] 9.6 Update `workflow-view.md` and `workflow-lowlevel.md` generation to render the graph-shaped spec and the selected capability templates.
- [ ] 9.7 Add a deferred OpenSpec task for context access-control policy design, covering stage-based, agent-based, and hybrid options.
