# Bash completion

scBOLT installs its Bash completion in the standard user directory:

```text
~/.local/share/bash-completion/completions/scbolt
```

The installed file is a symbolic link to `bin/completion.bash`. Restart the
shell after installation, source the file directly, or repair the link with:

```bash
scbolt install --completions
```

## Commands and modules

An empty top-level completion intentionally proposes pipeline modules only:

```bash
scbolt <TAB>
```

This keeps the common execution path compact. Once a prefix is typed,
completion also finds matching utility commands such as `diagnostics`,
`progress`, and `install`.

After selecting a command or module, completion proposes its supported options:

```bash
scbolt spec --<TAB>
scbolt diagnostics --<TAB>
```

Module options are read dynamically from `scbolt <module> help`, so help and
completion share the same parameter registry. Public YAML keys are exposed as
dash-separated command-line options:

```text
analysis_hvg_method       -> --analysis-hvg-method=
knnsc_min_cluster_size    -> --knnsc-min-cluster-size=
max_clauses               -> --max-clauses=
```

Execution commands may receive several modules. After a complete module and a
space, completion proposes options; after a partial word, it can propose the
next matching module.

## Conditional values

Condition-dependent YAML mappings generate options from the active project
configuration. For example:

```yaml
conditions: [ctrl, treated]
knnsc_centrality:
  ctrl: [Prom1, Prom2]
  treated: [Prom1]
```

adds:

```text
--knnsc-centrality-ctrl=
--knnsc-centrality-treated=
```

The same rule applies when conditions are inferred from suffixed keys. No
condition name is hard-coded in the completion script.

## Value completion

Closed-value parameters complete to their supported choices. Examples include:

```text
--backend=                  conda mamba micromamba docker
--organism=                 mouse human
--analysis-hvg-method=      loess binning
--dorothea-api=             modern legacy
--clingo-mode-seed=         opt optN ignore
--clingo-strategy-seed=     bb bb,lin bb,hier bb,inc bb,dec
                            usc usc,oll usc,one usc,k usc,pmres
```

Boolean options complete to `true` and `false`. `prior_knowledge` proposes
`dorothea`, `collectri`, and filesystem paths. File-valued options use regular
filesystem completion, while reset and trust options complete to known scBOLT
modules.

## Project context

Dynamic completion resolves project configuration in the normal order:

1. `--config=<file>` on the current command line;
2. the `.scbolt` project locator;
3. `scbolt.yml` in the launch directory;
4. the legacy `params.mk` fallback.

Without a resolvable project, generic command options remain available, but
condition-specific and module-specific suggestions may be incomplete.

## Maintenance

Do not duplicate module parameter lists in the completion script. New module
parameters belong in the Make help registry and are discovered dynamically.
Only finite value domains and command-specific completion behavior should be
maintained directly in `bin/completion.bash`.
