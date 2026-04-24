## Why

The current OpenCode implementation has a working core chain: install, package commands, package plugin, runtime, target bundle generation, managed apply, layered validation, package agents, and host integration smoke.

The remaining gap is not a single missing script. It is a set of product, verification, packaging, and contract-hardening capabilities that must be designed as OpenCode-native behavior rather than copied from the ClaudeCode plugin layout.

The immediate risks are:

- `audit` is present in generated spec intent flows but not exposed as a supported product intent.
- package host visibility and target workflow host reload visibility are still separate and only the former is covered.
- agent files exist, but agentteam orchestration is not yet machine-modelled.
- host pollution from global OpenCode config, Claude assets, or oh-my-opencode assets is not diagnosed.
- release artifacts are not built from a clean, repeatable package step.
- schema versions, migrations, error codes, apply recovery, and offline/cross-platform install are not yet formal contracts.

## What Changes

- Add a gap-closure design layer to the HighLevel and LowLevel design documents.
- Define OpenSpec capability areas for the remaining implementation work.
- Split implementation into traceable spec tasks instead of a flat backlog.
- Preserve the OpenCode-only architecture boundary: package loading uses OpenCode assets; ClaudeCode assets are semantic references only.

## Capabilities

### New Capabilities

- `opencode-product-lifecycle-intents`: closes audit/evolve/orchestrate and intent contract consistency.
- `opencode-agentteam-orchestration`: separates agentteam structure from subagent execution.
- `opencode-host-isolation-and-compatibility`: diagnoses external asset pollution, OpenCode version compatibility, and reload requirements.
- `opencode-target-host-verification`: verifies generated target workflow visibility in a real OpenCode host.
- `opencode-release-and-installation`: builds clean release packages and hardens install/upgrade/uninstall/offline paths.
- `opencode-contract-hardening`: adds schema versioning, migrations, managed apply recovery, permissions, privacy, and error codes.
- `opencode-validation-depth`: adds deep validators, clarification review, fixtures, and CI coverage.

### Modified Capabilities

- `workflow-opencode-package-contract`: must include lifecycle intent consistency and package agent role metadata.
- `workflow-opencode-smoke-contract`: must distinguish package host smoke from target host reload smoke.
- `workflow-opencode-runtime-contract`: must support richer evidence, error codes, and schema versions.

## Impact

- Updates:
  - `design/opencode-v2-highlevel-design.md`
  - `design/opencode-v2-lowlevel-design.md`
  - `design/opencode-v2-implementation-plan.md`
  - `design/index.md`
- Adds:
  - `openspec/changes/complete-opencode-parity-gap-closure/*`
- Future implementation touches:
  - `package/.opencode/commands/*`
  - `package/.opencode/agents/*`
  - `package/.workflowprogram/runtime/*`
  - `package/.workflowprogram/runtime/validators/*`
  - `tools/build_package.py`
  - `dist/opencode/`

