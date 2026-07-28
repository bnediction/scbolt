# scBOLT launcher

The Go launcher selects the runtime backend before resolving a local scBOLT
checkout. A Docker installation therefore needs only the launcher executable,
the user configuration, and the versioned container image.

## Build

```sh
make -C launcher all
```

Artifacts are written under `build/launcher/` for Linux amd64, Windows amd64,
and macOS amd64/arm64. Release builds embed the scBOLT version, source revision,
and matching default GHCR image.

## Install the Docker backend

Run the downloaded launcher once to install it for the current user:

```sh
./scbolt-linux-amd64 install --backend=docker
```

This copies the executable to `~/.local/bin/scbolt`, records the Docker backend
and image in the user configuration, installs shell-completion adapters, and
pulls the image when it is missing. The checkout used for this installation is
not needed afterwards: the image contains the scBOLT source, Make workflow,
system tools, and Conda environments.

On Windows, run the equivalent executable from PowerShell:

```powershell
.\scbolt-windows-amd64.exe install --backend=docker
```

The local Conda, Mamba, and Micromamba backends use the same launcher binary.
They require a local scBOLT checkout and a matching `scbolt-system`
environment. The launcher resolves GNU Make and Bash from that environment,
then invokes the scBOLT Makefile directly; it does not pass through the Bash
CLI wrapper. The scripts under `bin/` remain available for development.

When installing from a checkout, `./install --cli` builds the native launcher.
Go is needed only for that source build. Users of a prebuilt release launcher
do not need Go.

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
