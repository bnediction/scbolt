# Architecture

scBOLT presents one command-line interface while keeping workflow orchestration
and runtime environments behind it.

## Runtime Layers

1. `bin/scbolt` parses commands, resolves project configuration, dispatches
   utility commands, and starts the selected workflow target.
2. `scripts/utils/project_config.py` validates public `scbolt.yml` files and
   translates their kebab-case keys into typed internal parameters.
3. `Makefile` and `make/` define the dependency graph, parameter validation,
   rebuild decisions, logging, and metadata sidecars.
4. `scripts/` and `lib/scbolt/` implement the scientific and runtime tasks.
5. `envs/` defines the isolated environments used by local backends; the Docker
   backend executes the same public command inside the selected image.

Make variable names are an internal contract shared by recipes, parameter
validation, and JSON metadata. Public YAML and CLI names are mapped centrally
by `scripts/utils/project_config.py`.

## Installation Layout

The regular installer creates an autonomous runtime:

```text
~/.local/bin/scbolt
  -> ~/.local/lib/scbolt/bin/scbolt

~/.local/lib/scbolt/
  Makefile
  VERSION
  REVISION
  install
  bin/
  envs/
  lib/
  make/
  scripts/
```

`REVISION` preserves the source commit when the installed copy has no Git
metadata. The launcher, run logs, and metadata sidecars use it as a fallback.

`./install --dev` instead links the command and completion directly to the
working tree. It is explicit because deleting or moving that checkout invalidates
the development installation.

Runtime backend configuration remains under
`${XDG_CONFIG_HOME:-~/.config}/scbolt`, while project data and resources remain
outside the installed application tree.

## Configuration Flow

The effective configuration follows this precedence:

```text
CLI overrides
> project configuration
> global configuration
> defaults
```

The YAML loader rejects unknown keys and emits Make assignments plus public-name
metadata. Make consumes those assignments without exposing its file format as
the normal user interface.

Condition-indexed mappings such as `sra`, `count-file`, and
`knnsc-centrality` expand generically to condition-suffixed internal variables.

## Rebuild Metadata

Each tracked module records its sensitive parameters, runtime environments,
source revision, and solution state in a JSON sidecar. Before running a target,
scBOLT compares the stored values with the current effective configuration and
reports stale outputs. The parameter names written to JSON come directly from
the same Make parameter lists used by the recipes.

## Backend Dispatch

Local Conda, Mamba, and Micromamba backends execute Make on Linux and select an
environment per workflow task. The launcher injects the installed `lib/` into
those task environments.

The Docker backend mounts the project and resource directories and runs the
pipeline implementation from the container image. Host Bash and GNU Make are
not pipeline requirements for that backend once container dispatch begins.
