# Proposal: Add Controlled Change And Entry Contract

## Why

Claude upstream added a controlled workflow change policy and consolidated user-facing entry exposure. OpenCode already has accepted-spec gates and managed apply, but mutating intents still lack an explicit change-context authorization step. This leaves room for `/wp-evolve`, `/wp-iterate`, and `/wp-hotfix` to treat an existing target spec as sufficient permission to rewrite a workflow.

OpenCode also exposes many `/wp-*` commands, which is correct for expert use, but natural-language usage should consistently start from `/wp-orchestrate` so the host/model does not pick a mutation path only because `.workflowprogram` exists.

## What Changes

- Add an OpenCode-native controlled change policy for mutating intents.
- Require existing-workflow mutation intents to resolve and validate a change context before candidate generation.
- Record change-policy evidence under `RUN_ROOT/outputs/change-policy/` and mirror the summary into staged evidence.
- Add validator and S5 checks for missing, stale, or undeclared mutation context.
- Clarify that `/wp-orchestrate` is the recommended natural-language entry, while direct `/wp-*` commands remain explicit expert entries.
- Add package contract checks so command docs and README do not drift away from the entry strategy.
- Document which Claude upstream changes are intentionally not copied because they are Claude plugin exposure mechanics.

## Impact

- `/wp-evolve`, `/wp-iterate`, and `/wp-hotfix` become safer: a user/model must provide an explicit mutation request and declared write scope before runtime applies changes.
- `/wp-develop` remains the first-time creation path and does not require an existing change context.
- `/wp-orchestrate` becomes the documented default for natural-language routing, without removing OpenCode slash commands.
- Existing managed apply conflict checks remain in place; the new policy is a semantic authorization gate before managed apply.
