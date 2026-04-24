# Proposal: Lightweight Global Bootstrap Installer

## Problem

Project-local installation gives WorkflowProgram good isolation, but it is not friendly for new projects because users must remember and rerun a long `package-deploy.py install` command in every project.

Installing the full WorkflowProgram package globally would make first use easier, but it reintroduces the exact problems the OpenCode design tries to avoid:

- global `/wp-*` command pollution
- project-to-project version drift
- ClaudeCode, oh-my-opencode, and OpenCode global asset shadowing
- harder rollback and reproduction

## Goal

Provide a small global bootstrap that can deploy the full WorkflowProgram package into the current project while preserving project-local isolation for the real product commands, agents, plugin, runtime, venv, and install manifest.

## Non-Goals

- Do not make the full WorkflowProgram package a global-only install.
- Do not silently mutate projects without a manifest and status output.
- Do not implement marketplace/npm distribution in this change.
- Do not remove existing direct `project-local` install support.

## Proposed Shape

- Add a global bootstrap install action to `package-deploy.py`.
- Install only `/wp-install`, `/wp-status`, `/wp-upgrade`, and `/wp-uninstall` into the OpenCode global command directory.
- Cache a clean copy of the full package under a user-level cache directory.
- Let the global bootstrap runtime materialize the full package into the current project using the existing project-local install path.
- Keep full `/wp-develop`, `/wp-validate`, `/wp-audit`, `/wp-evolve`, and related product commands project-local after installation.

## Acceptance

- A user can install the bootstrap once globally.
- A new project can run `/wp-install` and receive a project-local WorkflowProgram install.
- Bootstrap status reports global command availability and cache availability.
- Smoke tests cover bootstrap install and bootstrap-driven project install.
