# Output State Taxonomy

scBOLT tracks generated outputs with a configuration-aware state model. A file
is not considered valid only because it exists on disk: when available, its
metadata sidecar is also compared with the current effective configuration.

This taxonomy is used by:

- `scbolt progress`;
- `scbolt check`;
- `scbolt clean --stale`;
- stale-output warnings printed before running a module.

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
- the metadata sidecar is missing;
- the module depends on an upstream module that is stale or pending.

`STALE` is a scBOLT configuration-validity state, not a native Make state.
Make may still see the file as present and avoid rebuilding it automatically.

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

### `SKIPPED`

The module does not belong to the current workflow and has no output.

Examples include:

- macrostate methods not selected by `MACROSTATE_METHOD`;
- upstream modules bypassed by entry-point parameters such as
  `MACROSTATE_FILE` or `BINARIZATION_FILE`.

## Progress Counter

The main progress counter only considers the current workflow:

```text
up-to-date modules = DONE / (DONE + STALE + PENDING)
```

Outside-workflow states are excluded from the denominator.

This keeps progress focused on the workflow the user is actually asking scBOLT
to build.

## Runtime Behavior

Stale outputs are warnings by default.

Before executing a module, scBOLT scans the selected workflow and prints all
stale warnings upfront. It does not delete stale outputs and does not force
Make to rebuild them automatically.

To explicitly remove stale outputs:

```bash
scbolt clean --stale
```

After removal, stale modules become `PENDING`.
