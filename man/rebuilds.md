# Rebuild Controls

scBOLT exposes four controls for reusing or rebuilding existing outputs.

## `--reset-target`

`--reset-target` forces the workflow to rebuild from one or more modules.

```bash
scbolt bn-submin --reset-target=clustering
```

The selected module and its downstream modules are rebuilt.

Multiple modules can be provided by quoting a space-separated list, or by
repeating the option:

```bash
scbolt bn-submin --reset-target="clustering annotation"
scbolt bn-submin --reset-target=clustering --reset-target=annotation
```

## `--trust-target`

`--trust-target` trusts all outputs produced by one or more modules.

```bash
scbolt bn-submin --trust-target=clustering
```

Every output registered for the selected module is trusted. Multiple modules
use the same repeated or space-separated forms as `--reset-target`.

## `--trust-existing`

`--trust-existing` trusts every known scBOLT output that is already present
when the command starts.

```bash
scbolt bn-submin --trust-existing
```

Missing outputs are built normally.

Trust affects rebuild decisions, but metadata drift is still reported so that
changes in parameters, dependencies, or runtime environments remain visible.

`--reset-target` overrides all trust controls for the selected module and its
downstream modules.

## `old-files` and `--old-file`

`old-files` trusts individual files belonging to the scBOLT workflow.

```bash
scbolt bn-submin \
  --old-file=apl/omics/annot/integrated/annot.h5ad \
  --old-file=apl/bin/consensus/knnsc/mstates_bin.csv
```

Permanent project-level declarations can be added to `scbolt.yml`:

```yaml
old-files:
  - apl/omics/annot/integrated/annot.h5ad
  - apl/bin/consensus/knnsc/mstates_bin.csv
```

YAML and command-line paths follow the rules in
[configuration.md](configuration.md).

`old-files` is more granular than `--trust-target`: it trusts only the listed
files, not every output produced by the corresponding module.

## Comparison

| Control | Level | Effect |
| ------- | ----- | ------ |
| `--reset-target` | module | Rebuild from selected modules. |
| `--trust-target` | module | Trust all outputs from selected modules. |
| `--trust-existing` | project | Trust known outputs that already exist. |
| `old-files` / `--old-file` | file | Trust selected files only. |

## Validation

Active `old-files` entries are valid only when their files exist. Unknown
scBOLT targets produce a warning rather than an error.

Old files are not exempt from downstream content validation. For example, if an
old AnnData file is consumed by a downstream module, `scbolt check` still
validates the required AnnData metadata.
