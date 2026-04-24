# Spec: OpenCode Global Bootstrap Installer

## Requirements

### GBI-01 Global Bootstrap Install

The package deployment runtime SHALL provide an action that installs a lightweight bootstrap into the OpenCode global config root.

#### Scenarios

- Given a valid source package root
- When `package-deploy.py install-bootstrap` runs
- Then the global config root contains only bootstrap commands and bootstrap runtime
- And the full WorkflowProgram package is copied to a user-level versioned cache

### GBI-02 Bootstrap Project Install

The global bootstrap runtime SHALL install the full WorkflowProgram package into the current project using project-local mode.

#### Scenarios

- Given a bootstrap manifest with a valid cached package
- When `/wp-install` invokes `bootstrap-runtime.py install`
- Then `.opencode/*` and `.workflowprogram/package/*` are materialized in the current project
- And the project install manifest records the cached package source

### GBI-03 Bootstrap Status

The deployment runtime SHALL expose status for both global bootstrap and project-local install state.

#### Scenarios

- Given a global bootstrap install
- When `package-deploy.py bootstrap-status` runs
- Then it reports command, runtime, manifest, and cache availability

### GBI-04 Upgrade And Uninstall

The bootstrap runtime SHALL support project-level upgrade and uninstall through the same project-local install manifest.

#### Scenarios

- Given an installed project-local WorkflowProgram package
- When `/wp-upgrade` runs
- Then the project is reinstalled from the bootstrap cache
- When `/wp-uninstall` runs
- Then files listed in the project install manifest are removed

### GBI-05 Isolation

The global bootstrap SHALL NOT install the full product command set, agents, or package plugin globally.

#### Scenarios

- Given a bootstrap-only global install
- Then `/wp-develop`, `/wp-validate`, and other product lifecycle commands are not globally materialized by bootstrap
- And those commands become available only after project-local installation
