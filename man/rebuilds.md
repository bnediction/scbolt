# Rebuild Controls

scBOLT exposes four controls for changing how existing outputs are treated by
the build engine.

They are intentionally separate from biological entry-point configuration such
as `count_files`, `macrostate_files`, or `binarization_file`.

## `--reset-target`

`--reset-target` forces the workflow to rebuild from one or more modules.

```bash
scbolt bn-submin --reset-target=clustering
```

This is useful when a module should be recomputed even if its outputs already
exist. Successful recipes replace the corresponding outputs.

Multiple modules can be provided by quoting a space-separated list, or by
repeating the option:

```bash
scbolt bn-submin --reset-target="clustering annotation"
scbolt bn-submin --reset-target=clustering --reset-target=annotation
```

Repeated `--reset-target=<module>` options are combined by the launcher.

## `--trust-target`

`--trust-target` trusts all outputs produced by one or more modules.

```bash
scbolt bn-submin --trust-target=clustering
```

This is the module-level equivalent of `old_files`: every output registered for
the selected module is treated as an existing trusted file.

Multiple modules can be provided by quoting a space-separated list, or by
repeating the option:

```bash
scbolt bn-submin --trust-target="clustering annotation"
scbolt bn-submin --trust-target=clustering --trust-target=annotation
```

Repeated `--trust-target=<module>` options are combined by the launcher.

## `--trust-existing`

`--trust-existing` trusts every known scBOLT DAG output that is already present
when the command starts.

```bash
scbolt bn-submin --trust-existing
```

Missing outputs are not fabricated or trusted: the workflow builds them normally.
This makes `--trust-existing` useful when resuming a project whose existing
outputs should be accepted without listing each module or file individually.

Trust only affects timestamp-based rebuild decisions. Metadata drift
is still reported so that changes in parameters, dependencies, or runtime
environments remain visible.

`--reset-target` has absolute priority. Outputs from the reset module and every
downstream module scheduled for reconstruction are excluded from trust,
including trust requested through `--trust-target`, `--trust-existing`, or
`old_files`. Existing outputs on unrelated DAG branches remain trusted.

## `old_files` and `--old-file`

`old_files` trusts individual files already belonging to the scBOLT DAG.
Reference-level single-cell files live under `project_dir/omics/`; Boolean
abstractions and inference outputs stay under `project_dir/bin/` and the
configured `project_dir/inference_dir/`.

```bash
scbolt bn-submin \
  --old-file=apl/omics/annot/integrated/annot.h5ad \
  --old-file=apl/bin/consensus/knnsc/mstates_bin.csv
```

Several files can also be provided as a quoted space-separated list:

```bash
scbolt bn-submin \
  --old-file="apl/omics/annot/integrated/annot.h5ad apl/bin/consensus/knnsc/mstates_bin.csv"
```

Permanent project-level declarations can be added to `scbolt.yml`:

```yaml
old_files:
  - apl/omics/annot/integrated/annot.h5ad
  - apl/bin/consensus/knnsc/mstates_bin.csv
```

Relative paths in `scbolt.yml` are resolved relative to the configuration-file
directory. Relative `--old-file=<file>` paths are resolved relative to the
launch directory.

`old_files` is more granular than `--trust-target`: it trusts only the listed
files, not every output produced by the corresponding module.

## Comparison

| Control | Level | Effect |
| ------- | ----- | ------ |
| `--reset-target` | module | Rebuild from selected modules. |
| `--trust-target` | module | Trust all outputs from selected modules. |
| `--trust-existing` | project | Trust known outputs that already exist. |
| `old_files` / `--old-file` | file | Trust selected files only. |

## Validation

Active trusted old files must exist. An `old_files` entry excluded by
`--reset-target` is not validated as trusted because that output will be rebuilt.

`scbolt check <module>` reports:

```text
SUCCESS old file found: apl/omics/annot/integrated/annot.h5ad
FAIL old file not found: apl/bin/consensus/knnsc/mstates_bin.csv
```

If an old file is not a known scBOLT target, scBOLT warns but does not fail.
This keeps the mechanism usable for advanced workflows while making the
boundary explicit.

Old files are not exempt from downstream content validation. For example, if an
old AnnData file is consumed by a downstream module, `scbolt check` still
validates the required AnnData metadata.
