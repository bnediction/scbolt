# Output State Taxonomy

scBOLT tracks generated outputs with a configuration-aware state model. A file
is not considered valid only because it exists on disk: when available, its
metadata sidecar is also compared with the current effective configuration.

This taxonomy is used by:

- `scbolt progress`;
- `scbolt check`;
- `scbolt clean --stale`;
- stale and untracked-output warnings printed before running a module.

## Core States

### `DONE`

The module belongs to the current workflow, its expected outputs exist, and its
stored configuration hash matches the current configuration.

`DONE` means the output is up to date from scBOLT's point of view.

### `STALE`

The module belongs to the current workflow and its expected outputs exist, but
the stored configuration does not match the current configuration.

Typical causes are:

- a sensitive method parameter changed;
- the metadata sidecar exists but its hash differs;
- the module output exists, but at least one upstream dependency is stale;
- the module output exists, but at least one upstream dependency is missing and
  should be rebuilt.

`STALE` is a scBOLT configuration-validity state, not a native Make state.
Make may still see the file as present and avoid rebuilding it automatically.

### `UNTRACKED`

The module belongs to the current workflow and its expected outputs exist, but
their scBOLT metadata sidecar is missing or unreadable.

`UNTRACKED` does not mean that the output is invalid. It means scBOLT cannot
verify which configuration produced it.

Typical causes are:

- the output was produced before metadata sidecars were introduced;
- the output was copied from another project without its sidecar;
- the sidecar was deleted or corrupted.

Modules depending on an untracked upstream output are also considered
untracked for progress and warnings:

```text
WARNING missing module metadata: normalization
WARNING untracked module output: clustering (depends on untracked normalization)
```

### `PENDING`

The module belongs to the current workflow, but at least one expected output is
missing.

`PENDING` means the module still has to be built for the current workflow.

## Outside-Workflow States

These states are shown by `scbolt progress --all`.

### `EXTRA COMPLETED`

The module does not belong to the current workflow, but its outputs exist and
are not stale relative to their own current module configuration.

This can happen when a user previously ran an alternative branch, for example
`stream`, while the current workflow uses `knnbs`.

### `EXTRA STALE`

The module does not belong to the current workflow, but its outputs exist and
are stale relative to their own current module configuration.

### `EXTRA UNTRACKED`

The module does not belong to the current workflow, but its outputs exist
without readable scBOLT metadata sidecars.

### `SKIPPED`

The module does not belong to the current workflow and has no output.

Examples include:

- macrostate methods not selected by `MACROSTATE_METHOD`;
- upstream modules bypassed by entry-point parameters such as
  `MACROSTATE_FILE` or `BINARIZATION_FILE`.

## Progress Counter

The main progress counter only considers the current workflow:

```text
completed modules = (DONE + UNTRACKED) / (DONE + STALE + UNTRACKED + PENDING)
```

Outside-workflow states are excluded from the denominator.

`UNTRACKED` counts as completed because the expected output exists. It remains
listed separately from `DONE` because scBOLT cannot verify its provenance or
configuration metadata.

This keeps progress focused on the workflow the user is actually asking scBOLT
to build.

## Runtime Behavior

Stale and untracked outputs are warnings by default.

Before executing a module, scBOLT scans the selected workflow and prints all
stale and untracked warnings upfront. It does not delete these outputs and does
not force Make to rebuild them automatically.

To explicitly remove stale outputs:

```bash
scbolt clean --stale
```

After removal, stale modules become `PENDING`.

`scbolt clean --stale` does not remove `UNTRACKED` outputs. Untracked outputs
may be valid historical or externally restored files, so they require an
explicit module clean, `scbolt clean --all`, or manual user action.
