# Design

## Scope

This change covers two related but separate concerns:

- Controlled change policy: a mutation authorization contract for existing target workflows.
- Entry exposure contract: documentation and package validation that make `/wp-orchestrate` the natural-language entry while preserving direct expert commands.

It does not change OpenCode plugin loading, target workflow plugin generation, or the package/target isolation model.

## Controlled Change Policy

The policy applies to mutating intents that require an existing generated target workflow:

- `/wp-evolve`
- `/wp-iterate`
- `/wp-hotfix`

`/wp-develop` is excluded because it is the create path. If `/wp-develop` updates an existing workflow, it still uses accepted design plus managed apply, but the normal user guidance should route existing-workflow changes through orchestrate and then one of the three mutation intents above.

### Change Context

Runtime writes a resolved context file:

```text
RUN_ROOT/outputs/change-policy/change-context.json
```

Shape:

```json
{
  "schema_version": "opencode-v2.1",
  "intent": "evolve",
  "target_workflow_exists": true,
  "base_spec_path": ".workflowprogram/design/workflow-spec.yaml",
  "base_spec_sha256": "...",
  "change_request": "add verifier gate",
  "change_mode": "incremental",
  "declared_write_scope": [
    ".workflowprogram/design/**",
    ".workflowprogram/runtime/**",
    ".opencode/commands/**"
  ],
  "allowed_target_files": [
    ".workflowprogram/design/workflow-spec.md",
    ".workflowprogram/design/workflow-spec.yaml"
  ],
  "requires_user_confirmation": true,
  "confirmed": true
}
```

`change_mode` values:

- `incremental`: small scoped update; default for iterate/hotfix.
- `redesign`: larger workflow restructure; default for evolve when request text contains redesign/evolve/upgrade language.
- `repair`: defect correction; default for hotfix.

### Policy Validation

Runtime validates the change context before candidate generation:

- Existing target workflow must be proven by `.workflowprogram/design/workflow-spec.yaml`.
- `change_request` must be non-empty and more specific than a bare command name.
- Existing workflow mutations must be confirmed through the direct command or accepted design gate.
- `base_spec_sha256` must match the current base spec at validation time.
- Candidate relative paths must be covered by `declared_write_scope`.
- Candidate writes must remain inside managed target workflow paths.

Validation output:

```text
RUN_ROOT/outputs/change-policy/change-policy-summary.json
RUN_ROOT/outputs/stages/s3-change-policy.json
```

Failure categories:

- `missing_change_context`
- `missing_change_request`
- `stale_change_context`
- `undeclared_write`
- `unconfirmed_change`

## Entry Exposure Contract

OpenCode should keep all direct slash commands because they are useful expert entries and because OpenCode command discovery is project-local. The contract is therefore not "hide direct commands"; it is:

- README and command docs must state that natural-language workflow requests should start with `/wp-orchestrate`.
- Direct mutating commands must state they are explicit expert entries and require accepted design/change context before runtime writes.
- `/wp-orchestrate` must remain read-only and must not auto-run mutating intents.
- Package validation checks the README and command docs for this entry strategy.

This differs from Claude upstream, where entry consolidation includes marketplace command exposure details and removal of command-* skills. Those parts are not copied because OpenCode does not load WorkflowProgram as Claude skills.

## Control-Plane Contract Refinement

The existing `host-capabilities.json`, `capability-probe.json`, and `team-plan.json` remain advisory evidence. This change adds only enough structure to make mutation authorization explicit:

- `change_context` records what is allowed to change.
- `team_plan` may recommend pre-runtime agents, but agent output is not change authorization.
- `managed apply` remains the filesystem conflict gate.

## Self Review

### Pass 1 Findings

- Risk: confusing WorkflowProgram package loading with generated target workflow loading.
- Decision: controlled change policy belongs to target workflow mutation runtime, not package plugin schema.

### Pass 2 Findings

- Risk: treating `/wp-orchestrate` consolidation as a reason to remove OpenCode expert commands.
- Decision: keep all `/wp-*` commands; validate documentation that natural language starts with `/wp-orchestrate`.

### Pass 3 Findings

- Risk: duplicating managed apply conflict checks.
- Decision: change policy checks semantic authorization and declared scope before candidate apply; managed apply still checks actual filesystem conflicts.

### Pass 4 Findings

- Risk: requiring complex user-authored JSON before every change would be unfriendly.
- Decision: runtime resolves a default change context from intent, request text, existing spec, and candidate file list; users only need to provide a concrete request and confirmation through the normal command flow.

### Final Decision

No new design issue remains that blocks implementation. The change is scoped, OpenCode-native, and does not mix Claude plugin mechanics with OpenCode package/runtime contracts.
