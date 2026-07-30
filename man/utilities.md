# Utilities

scBOLT utility commands help inspect, validate, preview, and clean a project
without running the full workflow.

| Command | Main use |
| ------- | -------- |
| `init` | Project initialization |
| `help` | Documentation |
| `version` | Version and source revision |
| `config` | Configuration inspection |
| `progress` | Workflow state |
| `check` | Requirement validation |
| `diagnostics` | Installation and reproducibility diagnostics |
| `dry-run` | Build preview |
| `clean` | Cache, log, and output cleanup |
| `install` | Runtime backend installation |
| `completion` | Shell completion generation |

## `help`

The global help lists available commands and pipeline modules. Module help
shows the module description, expected outputs, dependencies, and relevant
parameters.

```bash
scbolt help
scbolt <module> help
```

## `version`

The version command prints the scBOLT release version and the Git commit used
by the installed source tree.

```bash
scbolt version
scbolt --version
```

## `config`

The configuration is resolved from the active `scbolt.yml`. The default view
is designed for users and groups settings by project, workflow, methods,
execution, and target-specific values. The raw view prints internal parameter
names for debugging and migration.

```bash
scbolt config
scbolt config <module>
```

Use `--raw` to print the internal parameter listing.

## `progress`

A module is completed only when the workflow engine considers its outputs up to date. Modules
outside the selected workflow are hidden by default, even if their outputs
exist. This makes the reported progress reflect the current workflow rather
than every file present on disk.

See [`states.md`](states.md) for the exact `DONE`, `STALE`,
`UNTRACKED`, and `PENDING` state semantics.

```bash
scbolt progress
scbolt progress <module...>
```

Modes:

- `scbolt progress`: inspect the default Boolean inference workflows.
- `scbolt progress <module...>`: inspect only workflows ending at selected modules.
- `scbolt progress --all`: also show modules outside the current workflow.

## `check`

The check is target-aware: it only validates parameters, files, AnnData
metadata, conda environments, and commands required by the selected workflow
segment. It is useful before running long or machine-dependent steps.

```bash
scbolt check <module>
```

## `dry-run`

This shows what the workflow engine would rebuild for the selected module without executing
recipes. It is useful before using `--reset-target` or `--trust-target`.

```bash
scbolt dry-run <module>
```

## `clean`

The default mode is interactive and only asks about cache and logs.
Module-specific cleaning removes generated outputs for selected modules without
deleting upstream data.
Stale cleaning removes stale outputs explicitly; after removal, these modules
become pending until they are rebuilt. It does not remove untracked outputs,
because files without scBOLT metadata may still be valid restored or historical
outputs.

```bash
scbolt clean
scbolt clean <module...>
scbolt clean --stale
scbolt clean --all
```

Modes:

- `scbolt clean`: ask before removing cache and log files.
- `scbolt clean <module...>`: remove outputs produced by selected modules.
- `scbolt clean --stale`: ask before removing stale tracked outputs.
- `scbolt clean --all`: ask before removing every generated module output.

## Common Options

| Option | Effect |
| ------ | ------ |
| `--config=<file>` | Select the project configuration file. |
| `--references=<condition...>` | Restrict the command to selected references. |
| `--reset-target=<module...>` | Rebuild from selected modules. |
| `--trust-target=<module...>` | Trust selected outputs and skip rebuilding them. |
| `--old-file=<file>` | Trust one existing scBOLT DAG file. |

See [`rebuilds.md`](rebuilds.md) for the difference between
`--reset-target`, `--trust-target`, `--trust-existing`, and `--old-file`.
