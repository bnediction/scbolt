# Rebuild Controls

scBOLT exposes three controls for changing how existing outputs are treated by
the build engine.

They are intentionally separate from biological entry-point parameters such as
`MACROSTATE_FILE`, `BINARIZATION_FILE`, or `SPEC_FILE`.

## `RESET_TARGET`

`RESET_TARGET` forces Make to rebuild from one or more modules.

```bash
scbolt bn-submin --reset-target=clustering
```

This is useful when a module should be recomputed even if its outputs already
exist. Successful recipes replace the corresponding outputs.

## `TRUST_TARGET`

`TRUST_TARGET` trusts all outputs produced by one or more modules.

```bash
scbolt bn-submin --trust-target=clustering
```

This is the module-level equivalent of `OLD_FILES`: every output registered for
the selected module is passed to Make as an old file.

## `OLD_FILES`

`OLD_FILES` trusts individual files already belonging to the scBOLT DAG.

```bash
scbolt bn-submin \
  --old-file=apl/integrated/clust/annot.h5ad \
  --old-file=apl/bin/consensus/knnbs/mstates_bin.csv
```

Permanent project-level declarations can be added to `params.mk`:

```make
OLD_FILES += apl/integrated/clust/annot.h5ad
OLD_FILES += apl/bin/consensus/knnbs/mstates_bin.csv
```

Relative paths in `params.mk` are resolved relative to the parameter-file
directory. Relative `--old-file=<file>` paths are resolved relative to the
launch directory.

`OLD_FILES` is more granular than `TRUST_TARGET`: it trusts only the listed
files, not every output produced by the corresponding module.

## Comparison

| Control | Level | Effect |
| ------- | ----- | ------ |
| `RESET_TARGET` | module | Rebuild from selected modules. |
| `TRUST_TARGET` | module | Trust all outputs from selected modules. |
| `OLD_FILES` | file | Trust selected files only. |

## Validation

Trusted old files must exist.

`scbolt check <module>` reports:

```text
SUCCESS old file found: apl/integrated/clust/annot.h5ad
FAIL old file not found: apl/bin/consensus/knnbs/mstates_bin.csv
```

If an old file is not a known scBOLT target, scBOLT warns but does not fail.
This keeps the mechanism usable for advanced workflows while making the
boundary explicit.

Old files are not exempt from downstream content validation. For example, if an
old AnnData file is consumed by a downstream module, `scbolt check` still
validates the required AnnData metadata.
