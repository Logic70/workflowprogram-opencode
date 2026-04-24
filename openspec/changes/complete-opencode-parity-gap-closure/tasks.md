## 1. Product Lifecycle Intents

- [x] 1.1 Define `intent-contract.json` or equivalent runtime registry covering `develop`, `validate`, `preflight`, `hotfix`, `iterate`, `ship`, `audit`, `evolve`, and `orchestrate`.
- [x] 1.2 Add `/wp-audit`, `/wp-evolve`, and `/wp-orchestrate` package commands.
- [x] 1.3 Extend `SUPPORTED_PACKAGE_INTENTS`, `workflow-entry.py`, and `workflow-runner.py` with deterministic handlers.
- [x] 1.4 Ensure generated `workflow-spec.yaml` `intent_flows` references only supported intents and stages.
- [x] 1.5 Add regression tests for command/runtime/spec intent consistency.

## 2. Agentteam Orchestration

- [x] 2.1 Define the package agent role schema fields and allowed values.
- [x] 2.2 Add role metadata to existing package agents without breaking OpenCode frontmatter.
- [x] 2.3 Add `test-scenario-generator` package agent.
- [x] 2.4 Implement `agent-team-planner.py` to produce `team-plan.json`.
- [x] 2.5 Add fan-out/fan-in and quorum evidence to run outputs.
- [x] 2.6 Add validation that agentteam role references resolve to installed package agents.

## 3. Host Isolation And Compatibility

- [x] 3.1 Extend doctor with host source inventory for project `.opencode`, global OpenCode config, Claude assets, and oh-my-opencode assets.
- [x] 3.2 Add namespace shadowing detection for commands, agents, skills, and plugins.
- [x] 3.3 Add OpenCode version and plugin API compatibility checks.
- [x] 3.4 Add plugin reload/restart guidance to remediation output.
- [x] 3.5 Add WSL/Windows path diagnostics and normalized path reporting.

## 4. Target Host Verification

- [x] 4.1 Define target host reload smoke contract separately from package host smoke.
- [x] 4.2 Add fixtures that request target command generation and target plugin generation.
- [x] 4.3 Implement target reload smoke using real `opencode` when available.
- [x] 4.4 Classify outcomes as `PASS`, `FAIL`, or `ENVIRONMENT-SKIP`.
- [x] 4.5 Add CI-safe deterministic fallback that validates target host-visible files without claiming host execution.

## 5. Release And Installation

- [x] 5.1 Add `tools/build_package.py` to produce a clean `dist/opencode/` and/or archive.
- [x] 5.2 Exclude `.workflowprogram/runs`, `__pycache__`, `node_modules`, local lock files, logs, and secrets from build output.
- [x] 5.3 Emit release manifest with source commit, file list, checksums, and excluded patterns.
- [x] 5.4 Add install smoke against release output.
- [x] 5.5 Add upgrade, repeated install, uninstall, and status regression tests.
- [x] 5.6 Add offline dependency lock support for runtime Python dependencies.

## 6. Contract Hardening

- [x] 6.1 Add `schema_version` to workflow spec, managed manifest, run-state, and install manifest.
- [x] 6.2 Add migration engine and migration reports.
- [x] 6.3 Add managed apply lock file, idempotent diff, rollback manifest, and recover/rollback diagnostics.
- [x] 6.4 Define unified error code taxonomy and wire it through runtime, validators, doctor, smoke, and plugin hook logs.
- [x] 6.5 Define permission policy for write operations, shell execution, and dry-run/confirm behavior.
- [x] 6.6 Add privacy redaction for logs, reports, environment variables, and provider outputs.

## 7. Validation Depth And Fixtures

- [x] 7.1 Add workflow draft validator.
- [x] 7.2 Add lowlevel design validator.
- [x] 7.3 Add generated runtime validator.
- [x] 7.4 Add lessons delta validator.
- [x] 7.5 Add clarification review generator/validator.
- [x] 7.6 Add golden fixtures for sequential workflow, target command workflow, and target plugin workflow.
- [x] 7.7 Add CI entry that runs py_compile, unit/regression validators, package install smoke, target host smoke where available, and release package integrity checks.

## 8. Documentation And Traceability

- [x] 8.1 Add ClaudeCode-to-OpenCode capability parity matrix.
- [x] 8.2 Update README with audit/evolve/orchestrate, target host smoke, isolation diagnostics, and release install path.
- [x] 8.3 Update installation markdown with reload/restart and offline/WSL guidance.
- [x] 8.4 Update design index to link this OpenSpec change.
- [x] 8.5 Add acceptance mapping from `GC-*` goals to OpenSpec tasks.

## 9. GC Goal To Spec Task Mapping

| Goal | Spec Area | Task Ranges |
|---|---|---|
| GC-01 Lifecycle intent closure | `opencode-product-lifecycle-intents` | 1.1 - 1.5 |
| GC-02 Agentteam orchestration | `opencode-agentteam-orchestration` | 2.1 - 2.6 |
| GC-03 Test scenario generator | `opencode-agentteam-orchestration` / `opencode-validation-depth` | 2.3, 7.6 |
| GC-04 Host isolation and compatibility | `opencode-host-isolation-and-compatibility` | 3.1 - 3.5 |
| GC-05 Target host reload smoke | `opencode-target-host-verification` | 4.1 - 4.5 |
| GC-06 Release build | `opencode-release-and-installation` | 5.1 - 5.4 |
| GC-07 Schema version and migration | `opencode-contract-hardening` | 6.1 - 6.2 |
| GC-08 Managed apply hardening | `opencode-contract-hardening` | 6.3 |
| GC-09 Error code and permission/privacy policy | `opencode-contract-hardening` | 6.4 - 6.6 |
| GC-10 Deep validation and fixtures | `opencode-validation-depth` | 7.1 - 7.7 |
| GC-11 Installation lifecycle hardening | `opencode-release-and-installation` | 5.5 - 5.6 |
| GC-12 Capability parity matrix | documentation / traceability | 8.1 - 8.5 |
