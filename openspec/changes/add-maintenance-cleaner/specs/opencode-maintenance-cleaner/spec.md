## ADDED Requirements

### Requirement: Project cleaner SHALL default to dry-run and protect workflow state

WorkflowProgram OpenCode SHALL provide a project-local cleaner that plans cleanup by default and deletes only with explicit confirmation.

#### Scenario: Default clean is dry-run

- **WHEN** `/wp-clean` or `cleaner.py` runs without `--yes`
- **THEN** it SHALL report candidate cleanup items
- **AND** it SHALL NOT delete files or directories

#### Scenario: Protected workflow state is present

- **GIVEN** `.workflowprogram/design/`, `.workflowprogram/package/`, `.workflowprogram/runtime/`, `.workflowprogram/managed-files.json`, or an install manifest exists
- **WHEN** the cleaner scans the project
- **THEN** those paths SHALL be classified as protected
- **AND** the cleaner SHALL NOT delete them

### Requirement: Project cleaner SHALL support explicit cache and run pruning

The cleaner SHALL support safe cache deletion and explicit historical run pruning.

#### Scenario: Safe cache is deleted with confirmation

- **GIVEN** Python cache files exist
- **WHEN** the cleaner runs with `--pycache --yes`
- **THEN** the cache files SHALL be deleted
- **AND** a maintenance report SHALL be written

#### Scenario: Runs are pruned conservatively

- **GIVEN** multiple `.workflowprogram/runs/*` directories exist
- **WHEN** the cleaner runs with `--runs --keep-last 1 --yes`
- **THEN** older eligible runs SHALL be deleted
- **AND** the newest run SHALL be protected
- **AND** running runs SHALL be protected

### Requirement: Bootstrap cache cleaner SHALL preserve active cache

WorkflowProgram OpenCode SHALL provide deploy-layer bootstrap cache pruning without expanding global bootstrap commands.

#### Scenario: Active bootstrap cache is preserved

- **GIVEN** the bootstrap manifest references a cache package version
- **WHEN** `package-deploy.py clean-bootstrap-cache --keep-last 0 --yes` runs
- **THEN** the active version SHALL NOT be deleted

#### Scenario: Cache cleaner defaults to dry-run

- **WHEN** `package-deploy.py clean-bootstrap-cache` runs without `--yes`
- **THEN** it SHALL report cache candidates
- **AND** it SHALL NOT delete cache directories
