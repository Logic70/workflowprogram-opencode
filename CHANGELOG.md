# Changelog

## Unreleased

### Added

- OpenCode-only WorkflowProgram package layout
- `project-local` and `global` install model
- `package-deploy.py` install, status, uninstall flow
- package runtime isolation at `.workflowprogram/package/runtime/`
- optional package-local Python `venv`
- explicit runtime dependency file `requirements.txt`
- layered validators for package, spec, target bundle, and run-state
- `INSTALL_WITH_OPENCODE.md` for agent-assisted installation
- S1 requirement logic interview evidence for OpenCode `develop`
- `question-backlog.json` and `requirement-logic-map.json` generation and S5 validation
- deterministic shallow draft rejection in `validate-workflow-draft.py`
- `/wp-clean` project maintenance command with dry-run-first cache and run pruning
- `package-deploy.py clean-bootstrap-cache` for versioned bootstrap cache pruning
- controlled change policy for `/wp-hotfix`, `/wp-iterate`, and `/wp-evolve`
- `resolve-change-context.py` and `validate-change-policy.py` runtime gates before managed apply
- change-policy evidence under `RUN_ROOT/outputs/change-policy/` and S5/run-state validation
- entry exposure contract: `/wp-orchestrate` is the recommended natural-language entry while direct `/wp-*` commands remain expert entries
- package contract checks for entry strategy and controlled-change command documentation

### Changed

- Host integration smoke now treats OpenCode native invocation timeouts as `ENVIRONMENT-SKIP` instead of product failure when package structure checks passed.
- Local CI now runs design-flow and change-policy regression checks before build and smoke validation.
