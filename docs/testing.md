# Testing

Tests are grouped by the guarantee they protect:

| Directory | Scope |
| --- | --- |
| `tests/unit/` | Isolated Python, shell, configuration, solver, and formatting behavior |
| `tests/smoke/` | Public command-line entry points and launcher behavior |
| `tests/regression/` | Previously observed failures and output contracts |
| `tests/compatibility/` | Runtime backends, installation, and external execution contexts |

Smoke tests remain fast and avoid complete biological workflows. Regression
tests reproduce a specific failure before protecting its correction.

Compatibility tests may create runtime environments, but avoid complete
workflows. CI caches each environment by its YAML file so only changed
environments are rebuilt.

## Continuous Integration

Unit, smoke, and regression tests run on every push and pull request.
Compatibility tests run when their required backend is available.
