## Context

OpenCode v2 is an independent WorkflowProgram product package. It is not a compatibility layer inside the ClaudeCode plugin.

The correct mapping is:

- WorkflowProgram package loading is handled by OpenCode project/global assets.
- Generated target workflow loading is controlled by the generated target bundle contract.
- ClaudeCode assets are references for product capability parity, not source paths or runtime dependencies.

## Goals / Non-Goals

**Goals:**

- Make all remaining change goals explicit and traceable.
- Group goals by OpenSpec capability area.
- Add HighLevel and LowLevel implementation design for each capability group.
- Keep package contract, target bundle contract, runtime evidence contract, and host smoke contract separate.

**Non-Goals:**

- Implement all capabilities in this change.
- Recreate `.claude-plugin`, Claude hooks, or Claude skills as OpenCode loading primitives.
- Require real OpenCode provider connectivity for every deterministic test.

## Decisions

### 1. Remaining work SHALL be grouped by capability boundary

The implementation backlog SHALL be split into these capability specs:

- product lifecycle intents
- agentteam orchestration
- host isolation and compatibility
- target host verification
- release and installation
- contract hardening
- validation depth

Rationale:

- The earlier confusion came from mixing package load, target load, and generated workflow semantics.
- Capability boundaries make implementation and review smaller and less error-prone.

### 2. Intent consistency SHALL be a hard package contract

Every product intent SHALL have a consistent entry across:

- command markdown file
- runtime supported intent list
- runtime handler
- expected evidence outputs
- optional generated spec `intent_flows`

Rationale:

- A spec-only `audit` flow without a `/wp-audit` command and runtime handler is a design defect.

### 3. Agentteam SHALL be modelled separately from subagent execution

Agentteam describes roles, stages, handoffs, quorum, and fan-in. OpenCode subagents are one execution mechanism for roles in that plan.

Rationale:

- A one-stage-one-agent mapping is too rigid.
- Some stages need no subagent, some need parallel reviewers, and some need a fan-in verifier.

### 4. Host integration smoke SHALL have two layers

The smoke contract SHALL distinguish:

- package host smoke: WorkflowProgram package command/plugin/agent visibility
- target host reload smoke: generated target workflow command/plugin visibility

Rationale:

- Passing package smoke does not prove the generated target workflow can be loaded by OpenCode.

### 5. Host isolation SHALL be diagnostic-first

Doctor and remediation SHALL report global OpenCode, ClaudeCode, and oh-my-opencode pollution risks, but SHALL NOT delete or rewrite user global assets by default.

Rationale:

- Host configuration is user-owned and may be shared across projects.

### 6. Release build SHALL produce a clean artifact

The build path SHALL exclude local runtime state, Python caches, Node dependency trees, and provider secrets.

Rationale:

- The source package is convenient for development, but GitHub releases and reproducible installs need clean artifacts.

### 7. Contract hardening SHALL be validator-visible

Schema versions, migrations, error codes, apply locks, rollback metadata, permission policy, and privacy redaction SHALL be checked by validators or smoke.

Rationale:

- A design-only safety rule is not enough; the runtime needs machine-checkable evidence.

## Risks / Trade-offs

- [More specs may feel heavier] -> Keep each spec tied to a concrete implementation slice and acceptance checks.
- [Target host smoke can be environment-dependent] -> Keep deterministic runtime smoke as baseline and classify host failures as environment vs product defects.
- [Release build may duplicate install logic] -> Release build creates a clean source artifact; install still owns host placement.
- [Agent role schema may conflict with OpenCode or oh-my-opencode conventions] -> Treat role metadata as WorkflowProgram-owned fields and keep OpenCode-required frontmatter valid.

