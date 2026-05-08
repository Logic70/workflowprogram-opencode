---
description: Safely clean WorkflowProgram local cache and historical run evidence
---

This is a WorkflowProgram package command.

Rules:
- Treat the current working directory as `TARGET_ROOT`.
- Only call `${WORKFLOWPROGRAM_RUNTIME_ROOT}/cleaner.py`.
- Default behavior is dry-run. Do not delete anything unless the user explicitly passes `--yes`.
- Never delete `.workflowprogram/design`, `.workflowprogram/package`, `.workflowprogram/runtime`, `.workflowprogram/managed-files.json`, install manifests, running runs, or the newest run.
- Historical runs are audit evidence. Prune them only when the user passes `--runs` plus a policy such as `--keep-last 20` or `--older-than 30d`.

Run:

```bash
"${WORKFLOWPROGRAM_PYTHON}" "${WORKFLOWPROGRAM_RUNTIME_ROOT}/cleaner.py" --package-root "${WORKFLOWPROGRAM_PACKAGE_ROOT}" --target-root "$PWD" $ARGUMENTS --json
```

Then:
- Report the clean plan summary.
- If `dry_run=true`, tell the user no files were deleted and point to `.workflowprogram/maintenance/clean-report.md`.
- If files were deleted, list the deleted paths and report protected paths that were skipped.
- If the user asks to clean bootstrap cache, explain that this is deploy-layer maintenance and should use `package-deploy.py clean-bootstrap-cache`.
