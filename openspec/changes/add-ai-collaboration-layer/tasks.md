## 1. Revert Unnecessary DeepSeek Architecture Change

- [x] 1.1 Identify local DeepSeek commits and affected files.
- [x] 1.2 Revert engine-in-cache code and documentation changes without rewriting history.
- [x] 1.3 Remove untracked DeepSeek session artifacts from the working tree.

## 2. Design Correction

- [x] 2.1 Update HighLevel design to add the AI collaboration layer and `AR-22`.
- [x] 2.2 Update LowLevel flow diagram so OpenCode package agents appear between package command and deterministic runtime.
- [x] 2.3 Document pre-runtime and post-runtime agent dispatch rules.

## 3. Runtime And Command Implementation

- [x] 3.1 Extend agentteam planner with `timing=pre-runtime|post-runtime`.
- [x] 3.2 Add `--ai-evidence` to `workflow-entry.py`.
- [x] 3.3 Record AI evidence in `context.json` and `state.json`.
- [x] 3.4 Update mutation commands to run planner and dispatch pre-runtime agents before runtime.
- [x] 3.5 Update review/readiness commands to dispatch post-runtime agents after deterministic evidence exists.
- [x] 3.6 Add interactive clarification gate and `--confirmed` for develop.
- [x] 3.7 Block unconfirmed develop requests before target bundle generation.

## 4. Verification

- [x] 4.1 Run Python compile checks for runtime changes.
- [x] 4.2 Run package contract validator.
- [x] 4.3 Run deterministic smoke harness.
- [x] 4.4 Verify unconfirmed `/wp-develop` returns clarification-only `WARN` without target spec generation.
