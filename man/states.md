# Output State Taxonomy

scBOLT tracks generated outputs with a configuration-aware state model. A file
is not considered current only because it exists on disk: its recorded
configuration and provenance are also considered when available.

This taxonomy is used by:

- `scbolt progress`;
- `scbolt check`;
- `scbolt clean --stale`;
- stale and untracked-output warnings printed before running a module.

## Core States

| State | Meaning |
| --- | --- |
| `DONE` | Expected outputs and metadata match the current workflow. |
| `STALE` | Outputs exist, but their configuration or an upstream dependency has changed. |
| `UNTRACKED` | Outputs exist, but provenance metadata is missing or unreadable. |
| `PENDING` | At least one expected output is missing. |

Modules downstream of an untracked output are also `UNTRACKED`. This state
does not imply that an output is invalid, only that scBOLT cannot verify it.

## Outside-Workflow States

These states appear with `scbolt progress --all`:

| State | Meaning |
| --- | --- |
| `EXTRA COMPLETED` | Outputs from a module outside the current workflow are current. |
| `EXTRA STALE` | Outputs from a module outside the current workflow are stale. |
| `EXTRA UNTRACKED` | Outputs from a module outside the current workflow lack readable metadata. |
| `SKIPPED` | A module outside the current workflow has no output. |

## Progress Counter

The main progress counter only considers the current workflow:

```text
completed modules = (DONE + UNTRACKED) / (DONE + STALE + UNTRACKED + PENDING)
```

Outside-workflow states are excluded. `UNTRACKED` counts as completed because
its expected output exists.

## Runtime Behavior

Stale and untracked outputs produce warnings but are neither removed nor
rebuilt automatically.

To explicitly remove stale outputs:

```bash
scbolt clean --stale
```

After removal, stale modules become `PENDING`. Untracked outputs require an
explicit module clean, `scbolt clean --all`, or manual removal.
