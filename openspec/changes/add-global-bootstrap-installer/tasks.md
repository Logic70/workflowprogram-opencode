## 1. Design

- [x] 1.1 Document the global bootstrap + user cache + project-local install architecture.
- [x] 1.2 Define bootstrap command scope and explicitly exclude full global product installation.
- [x] 1.3 Define bootstrap manifest and cache layout.
- [x] 1.4 Update HighLevel, LowLevel, validation matrix, and implementation plan.

## 2. Runtime

- [x] 2.1 Add cache root discovery.
- [x] 2.2 Add `bootstrap-runtime.py`.
- [x] 2.3 Add `package-deploy.py install-bootstrap`.
- [x] 2.4 Add `package-deploy.py bootstrap-status`.
- [x] 2.5 Add `package-deploy.py uninstall-bootstrap`.
- [x] 2.6 Ensure cache copy excludes runs, node_modules, pycache, lock files, logs, and pyc files.

## 3. Bootstrap Commands

- [x] 3.1 Generate global `/wp-install`.
- [x] 3.2 Generate global `/wp-status`.
- [x] 3.3 Generate global `/wp-upgrade`.
- [x] 3.4 Generate global `/wp-uninstall`.
- [x] 3.5 Ensure global bootstrap commands call only bootstrap runtime.

## 4. Validation

- [x] 4.1 Add smoke coverage for bootstrap install.
- [x] 4.2 Add smoke coverage for bootstrap-driven project install.
- [x] 4.3 Add smoke coverage for bootstrap project status.
- [x] 4.4 Keep package contract validation focused on full package installs, not bootstrap-only global layout.

## 5. Documentation

- [x] 5.1 Update README with global bootstrap usage.
- [x] 5.2 Update install markdown with global bootstrap instructions.
- [x] 5.3 Add HTML summary of ClaudeCode-to-OpenCode adaptation concerns, difficulties, and solutions.
