<img align="right" src="man/fig/logo-scbolt.svg" alt="scBOLT logo" height="145">

[![tests](https://github.com/bnediction/scbolt/actions/workflows/tests.yml/badge.svg)](https://github.com/bnediction/scbolt/actions/workflows/tests.yml)
[![Make >= 4.3](https://img.shields.io/badge/Make-%3E%3D4.3-red?style=flat)](https://www.gnu.org/software/make)

<br>

# scBOLT

scBOLT is a software framework for inferring Boolean networks from multi-condition single-cell transcriptomic data.

Its main goal is to transform complex transcriptomic observations into biologically meaningful Boolean abstractions and dynamical constraints suitable for exact logical model inference. This remains a major challenge in data-driven logical modeling, particularly for poorly characterized biological systems and non-canonical cellular processes.

scBOLT combines transcriptome-derived state abstractions, user-defined dynamical constraints, and prior regulatory knowledge to generate inference-ready logical models through a reproducible and modular workflow.

### Key features

* multi-condition logical modeling
* transcriptome-driven constraint engineering
* scalable exact Boolean network inference
* multiple macrostate characterisation and binarization strategies
* reusable intermediate entry points
* reproducible execution and dependency management

<p align="center">
  <img src="man/fig/scbolt-overview.png" alt="scbolt-overview" width="700"/>
</p>

### Under the hood

scBOLT relies on the BoNesis framework for exact Boolean network synthesis.

# Installation

## Required dependencies

scBOLT requires:
1. GNU Make (>= 4.3)
2. One Conda-compatible environment backend:
   * [Anaconda](https://www.anaconda.com/download/)
   * [Mamba](https://mamba.readthedocs.io/en/latest/installation/mamba-installation.html)
   * [Micromamba](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html)

Alternatively, scBOLT can run through Docker. In that mode, the local `scbolt`
command keeps the same interface and delegates execution to the scBOLT Docker
image.

Install the required system dependencies:
```sh
apt-get install build-essential
```

---

## Setup

Clone and configure the project:

```sh
git clone https://github.com/bnediction/scbolt.git scbolt
cd scbolt
./install
```

To use Docker as the default runtime backend:

```sh
./install --backend=docker
```

This writes `~/.config/scbolt/config.mk`, pulls the configured scBOLT image if
needed, and keeps normal commands such as `scbolt bn-submin` unchanged.

Initialize a project in any working directory:

```sh
mkdir my_project
cd my_project
scbolt init params.mk
```

Verify the installation:

```sh
make check
```

---

## Optional

LaTeX is optional. When available, scBOLT uses it for figure text rendering.
Otherwise, figures are generated with Matplotlib's native text renderer and
plain axis labels such as `UMAP1` and `PC1`.

```sh
apt-get install texlive dvipng texlive-latex-extra texlive-fonts-recommended cm-super texlive-extra-utils
```

The following resources are only required when starting from raw sequencing data:
* [Cell Ranger](https://www.10xgenomics.com/support/software/cell-ranger/downloads) (optional alternative to STAR for alignment and counting)
* Reference genomes and RepeatMasker annotations are downloaded automatically
  for supported organisms when needed.

For long-term reproducibility in raw FASTQ mode, back up `RESOURCES_DIR`
together with the project. scBOLT does not redistribute large third-party
reference archives.

# Quickstart

A minimal runnable example is available in `quickstart/`. It uses the built-in
Nestorowa hematopoiesis dataset from BoNesisTools and runs scBOLT without any
manual data download.

See `quickstart/README.md` for the commands.

---

# Output Layout

Generated files are written under `PROJECT_DIR` with separate namespaces:

* `omics/`: reference-level single-cell objects, plots, trajectories, and macrostates;
* `bin/`: Boolean abstractions of cells and macrostates;
* `infer/`: BoNesis specifications, selected genes, and inferred Boolean networks;
* `logs/`: command logs.

This avoids collisions with condition names such as `bin`, `infer`, or `logs`.

---

# Usage

Display available modules:

```bash
scbolt help
```

Display command-specific help:

```bash
scbolt init --help
scbolt config help
scbolt check --help
scbolt progress --help
scbolt clean help
```

Create, update, or remove the project configuration:

```bash
scbolt init <params.mk>
scbolt init --show
scbolt init --remove
```

If `<params.mk>` does not exist, `scbolt init` creates a minimal parameter file.

Run a module:

```bash
scbolt <module...>
```

Display effective configuration:

```bash
scbolt config
```

Preview execution without running:

```bash
scbolt dry-run <module>
```

Validate dependencies and configuration:

```bash
scbolt check <module>
```

Display workflow progress:

```bash
scbolt progress
scbolt progress --all
scbolt progress bn-submin
```

Clean cache and logs, optionally with selected module outputs:

```bash
scbolt clean
scbolt clean --all
scbolt clean macrostates bn-submin
```

Without modules, `scbolt clean` asks before removing cache and logs.
With `--all`, it asks before removing cache, logs, and all generated module outputs.

## Common options

| Option                         | Description                                           |
| ------------------------------ | ----------------------------------------------------- |
| `--params=<file>`              | Select the parameter file.                            |
| `--references=<condition...>`  | Restrict execution to selected references.            |
| `--reset-target=<module...>`   | Rebuild from these modules.                           |
| `--trust-target=<module...>`   | Trust all outputs from selected modules.              |
| `--trust-existing`             | Trust every existing scBOLT DAG output.               |
| `--old-file=<file>`            | Trust one existing scBOLT DAG file.                   |
| `--logging=false`              | Disable persistent logging.                           |
| `--help`                       | Display command-specific help when supported.         |
| `--raw`                        | Display raw `config` listing.                         |
| `--<parameter>=<value>`        | Override any Make parameter using dash-separated option names. |
| `--prior-knowledge=<resource>` | Use `collectri`, `dorothea`, or a custom regulatory network. |

`--trust-existing` only trusts known DAG outputs present when the command
starts; missing outputs are built normally. `--reset-target` always takes
priority and excludes the requested rebuild path from trust.

Make-style assignments such as `PRIOR_KNOWLEDGE=dorothea` remain supported.

Advanced documentation is available in: `man/`, including rebuild controls in
`man/rebuilds.md`.

Examples:

```bash
scbolt bn-submin
scbolt bn-submin --references=ctrl
scbolt check velocity
scbolt bn-submin --logging=false
scbolt bn-submin --max-clause=12
```

Internally, scBOLT uses GNU Make as its workflow engine. Advanced users can
still call `make` directly when needed.

### Starting from custom macrostates

```bash
scbolt bn-submin --macrostate-files=my_macrostates.h5ad
```

Required AnnData fields:

```text
layers:
  log-norm

obs:
  macrostate
  condition (for multi-condition projects)

obsm:
  X_umap, X_tsne, or X_se (matching REPRESENTATION)
```

scBOLT reads expression from the named layers and does not use `adata.X` as a
fallback for this entry point.

### Starting from precomputed binarizations

```bash
scbolt bn-submin --binarization-file=my_binarization.csv
```

This allows scBOLT to integrate with existing single-cell analysis workflows and external trajectory inference methods.

---

# Bug reports

Please report any bugs or ask questions [here](https://github.com/bnediction/scbolt/issues) or contact contributors directly.

---

# License

No license currently.

The project is currently intended for internal research use.

---

# Contributors

* Théo Roncalli
* Loïc Paulevé
* Élisabeth Remy
