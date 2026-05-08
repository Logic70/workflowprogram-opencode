# Design: Maintenance Cleaner

## User Model

`/wp-clean` inspects the current project and produces a plan by default. Deletion requires `--yes`.

Safe-by-default candidates:

- Python `__pycache__/` and `*.pyc`
- `.pytest_cache/`

Confirmation-required candidates:

- `dist/`
- `node_modules/`
- old `.workflowprogram/runs/<run-id>/`

Protected candidates:

- `.workflowprogram/design/**`
- `.workflowprogram/package/**` except Python cache files
- `.workflowprogram/runtime/**` except Python cache files
- `.workflowprogram/managed-files.json`
- package install manifest
- running runs
- newest run
- failed/non-pass runs unless `--include-failed-runs`

## Project Cleaner

The runtime module `cleaner.py` SHALL:

- scan candidates under `--target-root`;
- classify each candidate as `safe`, `confirm`, or `protected`;
- default to dry-run;
- write `TARGET_ROOT/.workflowprogram/maintenance/clean-report.json`;
- write `TARGET_ROOT/.workflowprogram/maintenance/clean-report.md`;
- delete only selected non-protected candidates when `--yes` is passed.

Run pruning SHALL support:

- `--runs`
- `--older-than <Nd>`
- `--keep-last <N>`
- `--include-failed-runs`

When both `--older-than` and `--keep-last` are present, the cleaner SHALL keep the union of protected/newer/latest candidates and only remove runs selected by both policies.

## Bootstrap Cache Cleaner

`package-deploy.py clean-bootstrap-cache` SHALL prune versioned package cache directories below `cache_root/packages/`.

It SHALL:

- default to dry-run;
- keep the active cache package version referenced by the bootstrap manifest;
- support `--keep-last <N>`;
- support `--remove-version <version>`;
- require `--yes` for deletion.

No new global `/wp-*` bootstrap command is added for cache cleaning.

## Audit

Cleaner reports are maintenance evidence, not workflow execution evidence. They SHALL be written under `.workflowprogram/maintenance/` and SHALL NOT affect target workflow existence checks.
