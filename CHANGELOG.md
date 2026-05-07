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
