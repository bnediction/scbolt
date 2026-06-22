# Bash Completion

scBOLT provides a Bash completion script for the `scbolt` command.

The completion is installed by `./install` in the standard user completion
directory:

```bash
~/.local/share/bash-completion/completions/scbolt
```

The installed file is a symbolic link to:

```bash
bin/completion.bash
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
--params=
--references=
--reset-target=
--trust-target=
--old-file=
--logging=
--help
--spec-file=
--spec-only-hvg=
--bin-hvg-flavor=
--prior-knowledge=
--dorothea-api=
```

The module-specific options are generated dynamically from:

```bash
scbolt <module> help
```

This means the completion uses the same parameter registry as the module help
page. If a module help page lists `SPEC_FILE`, the completion exposes:

```bash
--spec-file=
```

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

Dash-separated CLI options are translated to Make parameters by replacing
dashes with underscores and uppercasing the name:

```text
--knnsc-embedding=...  ->  KNNSC_EMBEDDING=...
--knnsc-min-cluster-size=...  ->  KNNSC_MIN_CLUSTER_SIZE=...
--bin-hvg-flavor=...   ->  BIN_HVG_FLAVOR=...
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
scbolt spec --spec-only-hvg=<TAB>
scbolt velocity --velocity-only-hvg=<TAB>
```

File-like options use regular filesystem completion.

Examples:

```bash
scbolt spec --spec-file=<TAB>
scbolt binarization --binarization-file=<TAB>
scbolt macrostates --macrostate-files=<TAB>
scbolt bn-submin --old-file=<TAB>
scbolt --params=<TAB>
```

Module-list options complete to known scBOLT modules:

```bash
scbolt spec --reset-target=<TAB>
scbolt spec --trust-target=<TAB>
```

## Project Context

Dynamic module-parameter completion needs scBOLT to be able to resolve a
parameter file, because it calls:

```bash
scbolt <module> help
```

The parameter file is resolved in the usual scBOLT order:

1. `--params=<file>` if provided in the current command line;
2. the active `.scbolt` project configuration;
3. `params.mk` in the launch directory.

If no parameter file can be resolved, completion still proposes generic command
options, but module-specific parameters may be unavailable.

## Maintenance Notes

The completion script should avoid duplicating module parameter lists. Module
parameters should remain defined in the Make registry used by:

```bash
scbolt <module> help
```

When a new module parameter is added to the Make help registry, Bash completion
should pick it up automatically.
