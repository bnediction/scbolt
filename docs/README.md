# Developer Documentation

This directory documents scBOLT's implementation and contributor workflows.
User-facing guides remain in [`man/`](../man/README.md).

## Development Installation

Install an editable development launcher from the repository root:

```sh
./install --dev
```

This links `~/.local/bin/scbolt` and Bash completion to the working tree. The
pipeline therefore uses the current `Makefile`, Python modules, scripts, and
environment definitions immediately.

The local `scbolt-install` helper used during development is equivalent to
running `./install --dev` from the repository root. Re-run it after moving the
checkout or changing installer and completion behavior.

Use the installed command for routine development tests:

```sh
scbolt version
scbolt diagnostics
```

The regular installer intentionally has different semantics:

```sh
./install
```

It copies an autonomous runtime into `~/.local/lib/scbolt`. This is the mode
distributed to users and should continue to work after the source checkout is
removed.

## Documentation Layout

- [`architecture.md`](architecture.md) describes the launcher, configuration,
  Make orchestration, runtime backends, and installation layout.
- [`testing.md`](testing.md) describes the test categories and CI guarantees.
- [`man/`](../man/README.md) contains commands and scientific workflow guides
  intended for scBOLT users.

## Development Checks

Run the focused test associated with a change first, followed by the CLI and
compatibility suites when launcher or configuration behavior changes:

```sh
python3 tests/unit/test_project_config.py
bash tests/smoke/test_scbolt_cli.sh
bash tests/compatibility/test_install_backend_config.sh
git diff --check
```
