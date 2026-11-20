# Utilities

| Command | Effect |
| --- | --- |
| `scbolt init [<file>]` | Initialize a project or select its configuration. |
| `scbolt init --show` | Show the active project configuration. |
| `scbolt init --remove` | Remove the project locator. |
| `scbolt help` | List commands and modules. |
| `scbolt <module> help` | Show module inputs, outputs, dependencies, and parameters. |
| `scbolt version` | Show the release and source revision. |
| `scbolt config [<module>]` | Show effective global or module settings. |
| `scbolt progress [<module...>]` | Show workflow state, optionally for selected targets. |
| `scbolt progress --all` | Include modules outside the current workflow. |
| `scbolt check <module>` | Validate target parameters, inputs, runtime, and reproducibility. |
| `scbolt dry-run <module>` | Print commands that would execute. |
| `scbolt install <backend>` | Install or replace a runtime backend. |
| `scbolt clean` | Ask before removing cache and logs. |
| `scbolt clean <module...>` | Remove outputs from selected modules. |
| `scbolt clean --stale` | Ask before removing stale tracked outputs. |
| `scbolt clean --all` | Ask before removing every generated module output. |

See [states.md](states.md) for progress states and
[rebuilds.md](rebuilds.md) for rebuild and trust controls.

## Common Options

| Option | Effect |
| --- | --- |
| `--config=<file>` | Select the project configuration file (default: `scbolt.yml`). |
| `--project-dir=<dir>` | Override the generated-output directory (default: `project`). |
| `--resources-dir=<dir>` | Override the external-resource directory (default: `resources`). |
| `--references=<condition...>` | Restrict the command to selected references. |
| `--reset-target=<module...>` | Rebuild from selected modules. |
| `--trust-target=<module...>` | Trust selected outputs and skip rebuilding them. |
| `--trust-existing` | Trust every known workflow output already present. |
| `--old-file=<file>` | Trust one existing scBOLT output file. |
| `--<parameter>=<value>` | Override one public configuration value for the command. |
| `--help` | Display command-specific help. |
