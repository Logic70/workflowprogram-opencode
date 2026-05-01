## Design

### Self-Iteration

Self-iteration remains an optional capability template. If selected, the accepted `workflow-spec.yaml` must make the retry loop auditable:

- the `self-iteration-loop` template declares `max_attempts`
- the template declares `stop_conditions`
- graph transitions include a retry edge back to generation or repair work
- graph transitions include a terminal handoff edge

The runtime may still execute one pass in this change. The validator proves that the design is explicit enough for future execution.

### Lessons

Lessons are terminal evidence, not an automatic rule writer. The runtime emits a structured lessons summary with:

- `observations`
- `failure_patterns`
- `reusable_constraints`
- `residual_risks`
- `evolve_recommendations`
- `source_verdicts`

The lessons validator checks shape and consistency with the validation / judge verdicts. `/wp-evolve` can read the latest lessons and present them as design context, but any resulting workflow change still requires an accepted draft and `workflow-spec.yaml`.

### Clarification Method

Clarification keeps the current artifact chain:

- `clarification-record.json`
- `open-questions.json`
- `design-readiness-report.json`
- `clarification-challenge-report.json`
- `clarification-handoff.json`
- `clarification-evidence.json`
- `assumption-log.md`

The method is strengthened to ask questions in four groups: divergent workflow options, hard constraints, convergence criteria, and readback confirmation. This borrows the useful discipline from brainstorming skills without adding a new runtime artifact.

### OpenCode Plugin Hooks

Hook capability is represented as OpenCode target plugin behavior. If `registry.plugins` declares a target plugin, each plugin entry must declare:

- `hook_intents`
- `hook_events`

Generated target plugins remain lightweight and use OpenCode plugin hooks. Package plugin hooks remain host bridge behavior and are not target workflow semantics.

