# scBOLT launcher

The Go launcher selects the runtime backend before resolving a local scBOLT
checkout. A Docker installation therefore needs only the launcher executable,
the user configuration, and the versioned container image.

## Build

```sh
make -C launcher all
```

Development artifacts are written under `build/launcher/`. Tracked release
artifacts are regenerated under `dist/` with:

```sh
make -C launcher release
```

Both targets build Linux amd64, Windows amd64, and macOS amd64/arm64
executables. Release builds embed the scBOLT version, source revision, and
matching default GHCR image.

## Install the launcher

Run the downloaded launcher once to install it for the current user:

```sh
./scbolt-linux-amd64
```

This copies the executable to `~/.local/bin/scbolt` and installs the
shell-completion adapters. On a first installation, it then proposes Conda,
Mamba, Micromamba, and Docker. Selecting Docker records the backend and image
in the user configuration and pulls the image when it is missing. The checkout
used for a Docker installation is not needed afterwards: the image contains
the scBOLT source, Make workflow, system tools, and Conda environments.

On Windows, run the equivalent executable from PowerShell:

```powershell
.\scbolt-windows-amd64.exe
```

Once the launcher is installed, backend management is independent:

```sh
scbolt install conda
scbolt install mamba
scbolt install micromamba
scbolt install docker
```

Running `scbolt install` without a backend displays the same interactive
selection. Backend installation never replaces the launcher or completion
files.

The local Conda, Mamba, and Micromamba backends use the same launcher binary.
They require a local scBOLT checkout and a matching `scbolt-system`
environment. The launcher resolves GNU Make and Bash from that environment,
then invokes the scBOLT Makefile directly; it does not pass through the Bash
CLI wrapper. The scripts under `bin/` remain available for development.

The native installer creates or replaces the managed environments by invoking
Conda, Mamba, or Micromamba directly. It records the local checkout, installs
the launcher and completion adapters, and never invokes the repository
`./install` script. Bash is therefore needed only inside `scbolt-system`, not on
the host during installation or execution.

For a source build, use Go directly:

```sh
go build -o build/launcher/scbolt-native ./launcher/scbolt
./build/launcher/scbolt-native
```

Users of a prebuilt release launcher do not need Go. The legacy `./install`
script remains available for development workflows.

## Completion

The completion manifest is generated from the effective scBOLT command and
module help, then embedded in the launcher:

```sh
make -C launcher manifest
make -C launcher manifest-check
```

At runtime no checkout, Make process, Python process, or container is needed:

```sh
scbolt completion bash
scbolt completion zsh
scbolt completion fish
scbolt completion powershell
```

The generated shell adapters call the internal `scbolt __complete` protocol.
Project-dependent values are read locally from `.scbolt` and the selected
parameter file.

## Development

Tests use build artifacts and temporary user directories. The installed
`~/.local/bin/scbolt` command is never modified:

```sh
make -C launcher test
```
