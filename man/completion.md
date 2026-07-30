# Shell completion

The native launcher installs completion for Bash, Zsh, Fish, and PowerShell.

To repair or reinstall all completion adapters without changing the runtime
backend or its environments, run:

```bash
scbolt install --completions
```

For Bash, completion is installed in the standard user completion directory:

```bash
~/.local/share/bash-completion/completions/scbolt
```

After installing or updating scBOLT, restart the shell or reload the completion
manually:

```bash
source ~/.local/share/bash-completion/completions/scbolt
```

## Top-Level Completion

At the top level, completion only proposes scBOLT commands and pipeline modules:

```bash
scbolt <TAB>
```

Examples:

```text
init
config
check
dry-run
clean
progress
filtering
clustering
spec
bn-submin
```

Options are intentionally not proposed before a command or module has been
selected. This keeps the first completion level focused on what scBOLT can run.

For example:

```bash
scbolt --<TAB>
```

does not suggest global options.

## Command and Module Options

Once a command or module is selected, completion proposes supported options:

```bash
scbolt spec --<TAB>
```

Example output:

```text
--config=
--references=
--reset-target=
--trust-target=
--old-file=
--logging=
--help
--binarization-hvg-method=
--prior-knowledge=
--dorothea-api=
```

The module-specific options are generated dynamically from:

```bash
scbolt <module> help
```

This means completion uses the same public YAML-key registry as module help.
Inference contracts remain in the separate file selected by `spec_file`, so
inference modules expose `--spec-file=` when it is relevant.

Execution commands may receive several modules:

```bash
scbolt velocity potency
```

After a completed module followed by a space, completion proposes options:

```bash
scbolt potency <TAB>
```

If the next word has already started, completion can propose another module:

```bash
scbolt potency v<TAB>
```

Dash-separated CLI options use the public YAML names:

```text
--knnsc-embedding=...
--knnsc-min-cluster-size=...
--binarization-hvg-method=...
```

Condition-dependent options are expanded from the active project
configuration. For example, a project with `ctrl` and `treated` conditions
offers:

```text
--knnsc-centrality-ctrl=
--knnsc-centrality-treated=
--knnsc-periphery-ctrl=
--knnsc-periphery-treated=
```

## Target-Aware Completion

Diagnostic commands also use target-aware completion.

For example:

```bash
scbolt check spec --<TAB>
```

proposes options relevant to the `spec` module, while:

```bash
scbolt check --<TAB>
```

only proposes generic `check` options.

The same behavior applies to:

- `scbolt check <module>`
- `scbolt dry-run <module>`
- `scbolt config <module>`

## Value Completion

Some option values are completed when scBOLT can infer a useful domain.

Boolean options complete to:

```text
true
false
```

Examples:

```bash
scbolt velocity --velocity-only-hvg=<TAB>
```

File-like options use regular filesystem completion.

Examples:

```bash
scbolt binarization --binarization-file=<TAB>
scbolt macrostates --macrostate-files=<TAB>
scbolt bn-submin --old-file=<TAB>
scbolt --config=<TAB>
```

Module-list options complete to known scBOLT modules:

```bash
scbolt spec --reset-target=<TAB>
scbolt spec --trust-target=<TAB>
```

## Project Context

Dynamic module-parameter completion needs scBOLT to be able to resolve a
configuration file, because it calls:

```bash
scbolt <module> help
```

The configuration file is resolved in the usual scBOLT order:

1. `--config=<file>` if provided in the current command line;
2. `CONFIG=...` in the active `.scbolt` project locator;
3. `scbolt.yml` in the launch directory;
4. legacy `.scbolt`/`params.mk` discovery during the transition period.

If no configuration file can be resolved, completion still proposes generic command
options, but module-specific parameters may be unavailable.

## Maintenance Notes

Completion should avoid duplicating module parameter lists. Module parameters
remain defined by the workflow registry and are rendered with public YAML names by:

```bash
scbolt <module> help
```

When a new module parameter is added to the schema and workflow registry, the
generated completion manifest should pick it up automatically.
