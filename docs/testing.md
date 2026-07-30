# Testing

scBOLT tests are organized by the type of guarantee they provide. The goal is
not only to check that commands run, but also to make explicit what kind of
behavior each test protects.

## Test Categories

### Unit Tests

Unit tests validate small, isolated pieces of behavior such as parameter
conversion, shell helpers, or formatting logic.

Current location:

```text
tests/unit/
```

Typical guarantees:

- memory values are converted consistently across tools;
- parameter formatting remains stable;
- small helper functions keep their expected behavior.

### Smoke Tests

Smoke tests verify that the main command-line entry points start correctly.
They should be fast and should avoid running expensive biological workflows.

Current location:

```text
tests/smoke/
```

Typical guarantees:

- `scbolt` starts;
- core CLI commands are reachable;
- basic wrapper behavior does not regress.

### Regression Tests

Regression tests protect fixes for previously observed bugs. They are tied to
specific behaviors that should not break again.

Current location:

```text
tests/regression/
```

Typical guarantees:

- matrix input routes remain valid;
- unnamed mono-condition projects keep the expected output layout;
- annotation composition summaries use the correct normalization;
- command outputs remain compatible with documented behavior.

### Compatibility Tests

Compatibility tests validate supported runtime backends and external execution
contexts.

Current location:

```text
tests/compatibility/
```

Typical guarantees:

- Conda, mamba, micromamba, and Docker backends can be installed or built;
- backend-specific environments are created correctly;
- backends select the expected execution path;
- backend metadata is reported consistently;
- backend-specific wrappers do not change the user-facing `scbolt` interface.

Compatibility tests may create runtime environments, but they should avoid
running complete biological workflows. In CI, environment caches should be keyed
by the corresponding YAML file, for example:

```text
envs/conda/system.yml -> cache scbolt-system
envs/conda/core.yml   -> cache scbolt-core
```

When an environment YAML file is unchanged, CI can restore the corresponding
environment instead of recreating it. When the YAML file changes, only that
environment should be rebuilt.

### Reproducibility Tests

Reproducibility tests will validate stronger numerical and runtime guarantees.
These tests can be more expensive and may be better suited to manual or
scheduled CI jobs.

Planned guarantees:

- selected workflows produce stable checksums under a fixed runtime;
- backends produce equivalent outputs on controlled inputs;
- sidecar metadata detects runtime drift;
- Docker and local backends can be compared on controlled examples;
- numerical outputs remain within explicit tolerances when exact bitwise
  equality is not realistic.

## Continuous Integration

Fast tests should run on every push and pull request:

```text
unit
smoke
regression
```

Backend compatibility tests can run as a matrix when the required runtime is
available:

```text
compatibility
```

Heavy reproducibility tests should be introduced progressively after a stable
quickstart or controlled input dataset exists. They can then be run on demand or
on a schedule:

```text
reproducibility
```
