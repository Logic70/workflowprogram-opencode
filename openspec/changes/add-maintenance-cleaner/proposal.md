# Proposal: Add Maintenance Cleaner

## Why

WorkflowProgram OpenCode creates useful runtime evidence and local caches, but users need a safe way to distinguish disposable cache from audit evidence and protected workflow/package state.

## What Changes

- Add a project-local `/wp-clean` command backed by deterministic runtime cleanup.
- Add a `cleaner.py` runtime that defaults to dry-run and protects design/package/managed state.
- Add bootstrap cache pruning to `package-deploy.py` without adding another global bootstrap command.
- Document safe, confirmation-required, and protected cleanup categories.
- Add regression coverage for dry-run, protected paths, runs pruning, and active bootstrap cache protection.

## Impact

- Users can reclaim local cache space without accidentally deleting generated workflow design or package installs.
- Historical `runs/` remain audit evidence unless explicitly pruned.
- Global bootstrap remains minimal; cache maintenance stays in the deploy/runtime layer.
