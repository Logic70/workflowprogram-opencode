## Why

The graph workflow model now removes fixed S1-S6 semantics from the target `workflow-spec.yaml`, but several runtime semantics are still under-specified:

- self-iteration can be expressed as a template, but validators do not require retry and stop conditions
- lessons are emitted as a placeholder and the lessons validator only checks file existence
- `/wp-evolve` does not surface prior lessons as design input
- clarification asks generic questions instead of using a repeatable brainstorming / convergence method
- target plugin hooks are generated only as a bridge, not as an explicit spec-declared hook contract

This change closes those semantics without introducing new design artifacts or copying Claude hook names into OpenCode.

## What Changes

- Keep self-iteration optional, but validate it when selected.
- Replace placeholder lessons with structured lessons evidence.
- Make lessons available as `/wp-evolve` design context while keeping AI/user design as the only way to change `workflow-spec.yaml`.
- Improve clarification guidance using a brainstorm -> constraint -> convergence -> readback method while writing the same existing clarification artifacts.
- Require target plugin declarations to include explicit OpenCode hook intent when plugins are generated.

## Non-Goals

- Do not make every target workflow self-iterating.
- Do not add new artifacts such as `brainstorm-source.json` or `ai-design-source.json`.
- Do not automatically mutate `workflow-spec.yaml` from lessons.
- Do not introduce Claude `.claude/settings` hook concepts as OpenCode product terms.
- Do not implement automatic multi-pass retry execution in runtime in this change.

