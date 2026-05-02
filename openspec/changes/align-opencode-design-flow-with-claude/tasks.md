## 1. Design And Spec Alignment

- [x] 1.1 Update design docs so the adopted model is "AI/user graph design + Python validation/apply".
- [x] 1.2 Remove `workflow-view.md` and `workflow-lowlevel.md` from the core design artifact chain.
- [x] 1.3 Document that `workflow-spec.md` is the human-readable accepted design and `workflow-spec.yaml` is the only machine-readable semantic source.
- [x] 1.4 Document that `workflow-spec.proposed.yaml`, `design-brief.md`, `ai-design-source.json`, and `AI-DESIGN-*` are not part of the product model.
- [x] 1.5 Keep historical OpenCode host-dispatch work only as optional assistance; do not use it as acceptance evidence.

## 2. `/wp-develop` Interaction Gate

- [x] 2.1 Update `package/.opencode/commands/wp-develop.md` so broad requests ask clarification questions before runtime execution.
- [x] 2.2 Keep the first clarification round concise, then ask follow-ups only when answers are still too broad.
- [x] 2.3 Add explicit self-iteration questions: retry conditions, reflection/rework behavior, maximum attempts, and human handoff.
- [x] 2.4 Split trigger questions into CLI command and OpenCode plugin hook; do not collapse hook needs into CLI needs.
- [x] 2.5 Ask for graph-shape needs: sequence, branch, parallelism, fan-in/fan-out, manual checkpoints, and shared context.

## 3. Design Readback And Confirmation

- [x] 3.1 Require readback of nodes, edges, shared context, capability decisions, disabled capabilities, and files to be written.
- [x] 3.2 Require explicit confirmation before adding `--confirmed` or running runtime generation/apply.
- [x] 3.3 Treat vague continuation as insufficient unless the user clearly confirms writing `workflow-spec.md`, writing `workflow-spec.yaml`, and running runtime.
- [x] 3.4 Ensure pre-runtime agent output can influence the design only by being reflected in the accepted spec.

## 4. Runtime Contract Correction

- [x] 4.1 Ensure runtime consumes accepted `workflow-spec.yaml` and never generates hidden workflow semantics from fixed S1-S6 templates on the production path.
- [x] 4.2 Keep reusable flows such as self-iteration as optional templates selected and expanded by AI into the accepted graph.
- [x] 4.3 Generate target commands only when `workflow-spec.yaml` declares CLI assets.
- [x] 4.4 Generate target plugins/hooks only when `workflow-spec.yaml` declares plugin hook assets.
- [x] 4.5 Remove `--ai-evidence` and `state.ai_collaboration` from success gating; preserve them only as legacy diagnostics if still present.

## 5. Validator Updates

- [x] 5.1 Validate graph shape: node completeness, edge references, reachability, branch/fan-in consistency, and context references.
- [x] 5.2 Validate capability declarations for self-iteration, CLI assets, plugin hook assets, agent assistance, validation, and handoff.
- [x] 5.3 Validate that target runtime and generated assets match `workflow-spec.yaml`.
- [x] 5.4 Stop requiring deterministic `workflow-view.md` / `workflow-lowlevel.md` derivation for core success.
- [x] 5.5 Validate clarification/readback evidence using existing clarification artifacts rather than new AI evidence files.

## 6. Regression Coverage And Manual Verification

- [x] 6.1 Add a develop fixture that asks clarification, reads back a graph, confirms, writes `workflow-spec.md`, writes `workflow-spec.yaml`, and applies generated assets.
- [x] 6.2 Add a fixture where hook is requested independently of CLI command and generated only when declared.
- [x] 6.3 Add a fixture where self-iteration is requested and appears as graph nodes/edges, not as a mandatory fixed slot.
- [x] 6.4 Add a negative fixture where runtime is called without accepted spec/confirmation and must not apply target assets.
- [x] 6.5 Add a negative fixture where `--ai-evidence` exists without accepted design artifacts and must not pass.
- [x] 6.6 Run focused validators and a host smoke that reports host visibility separately from workflow semantic success.

Verification note:
- Focused runtime regressions passed locally via `python tests/test_design_flow_runtime.py`.
- Runtime host timeout cleanup passed via `python tests/test_runtime_host_timeout.py`; timeout now terminates spawned child processes that keep stdio pipes open.
- Package install conflict regression passed via `python tests/test_package_deploy_install.py`; an existing package-managed venv is not treated as an unmanaged conflict.
- `target-host-smoke.py` was rerun with a generated target workflow and `--timeout-seconds 2`. It returned in 5.8s with target spec/command discovery `PASS`, plugin discovery `WARN` because the test spec did not request a plugin, and host execution `ENVIRONMENT-SKIP` because OpenCode invocation timed out. No lingering `opencode` process remained.

## 7. Deferred Context Access Policy

- [x] 7.1 Keep context read/write permissions out of this implementation.
- [x] 7.2 Track stage-based, agent-based, and hybrid context access policy as deferred OpenSpec work.
- [ ] 7.3 Add enforcement only after a concrete conflict or security boundary requires it.
