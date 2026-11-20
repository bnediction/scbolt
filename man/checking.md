# Checking with `scbolt check`

`scbolt check <module>` validates the parameters, files, AnnData metadata,
runtime environments, and external commands needed to build a selected scBOLT
module. It also reports the numerical reproducibility profile of the selected
runtime.

The check is target-aware: it validates what the selected target uses, not
every parameter in the project.

## Usage

```bash
scbolt check <module>
```

Examples:

```bash
scbolt check velocity
scbolt check bin-cells --macrostate-file=case/macrostate.h5ad
```

Validation honors rebuild and trust options.

## Diagnostic Output

Diagnostics are grouped by parameters, files and metadata, runtime, numerical
reproducibility, and final status.

| Symbol | Meaning |
| --- | --- |
| `✓` | Successful check |
| `⚠` | Non-blocking warning |
| `✗` | Blocking error |

A single blocking error makes `scbolt check` exit with a non-zero status. The
final `Status` section reports the numbers of blocking errors and warnings.

## Parameter Taxonomy

| Category | Covers | Examples |
| --- | --- | --- |
| Project | Biological datasets and interpretations | `organism`, `conditions`, `sra`, `labels` |
| Core | Shared execution and output settings | `project-dir`, `memory`, `jobs`, `seed` |
| Method | Analytical and solver choices | `alignment-tool`, `macrostate-method`, `max-clauses` |
| External resources | Files and versioned resources | `count-file`, `prior-knowledge`, `hcop-version` |

Project, method, and resource parameters are checked only when the selected
target uses them. Core parameters are validated for every pipeline run.

## File, Command, and Environment Checks

`scbolt check` validates files, commands, and `scbolt-*` environments required
by the selected target. Environment drift is reported as a warning so locally
patched runtimes remain usable.

## AnnData Dependency Validation

Existing AnnData inputs are checked for required `obs`, `var`, `obsm`, `obsp`,
and `layers` fields without loading the full expression matrix.

### Validation Output

Successful validation example:

```text
Files and metadata
  ✓ h5ad metadata: obsm 'X_umap' found (reference: ctrl)
```

Failure example:

```text
Files and metadata
  ✗ h5ad metadata: obsm 'X_umap' missing (/path/to/file.h5ad, reference: ctrl)
```

### External Entry Points

| Entry point | Required AnnData metadata |
| --- | --- |
| `count-file` | `counts` in `layers` |
| `macrostate-file` | `log-norm` in `layers`, `macrostate` in `obs`, and the configured `representation` in `obsm` |

A shared multi-condition `macrostate-file` also requires `condition` in `obs`.
The `loess` binarization HVG method additionally requires `counts` in `layers`.
Named layers are used instead of `adata.X`.

## AnnData Input Contracts

The following sections document fields required from inputs and fields made
available to downstream modules. They are not exhaustive inventories of every
field present in each output.

### Velocyto

Provides:

- `ambiguous` in `layers`
- `spliced` in `layers`
- `unspliced` in `layers`
- `counts` in `layers`

### Filtering

Requires:

- `counts` in `layers`

Provides:

- `G1_score` in `obs`, only when `organism: mouse`
- `S_score` in `obs`, only when `organism: mouse`
- `G2M_score` in `obs`, only when `organism: mouse`
- `n_features` in `obs`
- `total` in `obs`

### Normalization

Requires:

- `counts` in `layers`

Provides:

- `norm` in `layers`
- `log-norm` in `layers`
- `scale` in `layers`
- `correct` in `layers`

### Integrated Clustering

Requires each condition input to contain:

- `counts` in `layers`
- `log-norm` in `layers`
- `correct` in `layers`

Provides:

- `condition` in `obs`
- `highly_variable` in `var`
- `highly_variable_rank` in `var`
- `X_pca` in `obsm`
- `connectivities` in `obsp`
- `cluster` in `obs`
- the configured `representation` in `obsm`

### Per-Condition Clustering

Requires:

- `counts` in `layers`
- `log-norm` in `layers`
- `correct` in `layers`

Provides:

- `highly_variable` in `var`
- `highly_variable_rank` in `var`
- `X_pca` in `obsm`
- `connectivities` in `obsp`
- `cluster` in `obs`
- the configured `representation` in `obsm`

### Differential Expression Analysis

Requires:

- `cluster` in `obs`
- `log-norm` in `layers`

### Integrated Annotation

Requires:

- `cluster` in `obs`
- the configured `representation` in `obsm`

Provides:

- the configured `label-column` in `obs`

### Per-Condition Annotation

Requires:

- `condition` in `obs` from the integrated AnnData when using multiple
  conditions;
- `cluster` in `obs` when using a single condition;
- the configured `representation` in `obsm`.

Provides:

- the configured `label-column` in `obs`

### Velocity

Requires:

- `counts` in `layers`
- `spliced` in `layers`
- `unspliced` in `layers`
- `X_pca` in `obsm`
- `X_umap` in `obsm`
- the configured `label-column` in `obs`
- `connectivities` in `obsp`
- `highly_variable` in `var`, only when `velocity-only-hvg: true`

Provides:

- `Ms` in `layers`
- `Mu` in `layers`
- `variance_velocity` in `layers`
- `velocity` in `layers`

### Potency

Requires:

- `counts` in `layers`
- the configured `label-column` in `obs`
- the configured `representation` in `obsm`

Provides:

- no downstream AnnData metadata

When CellRank uses potency results, `potency.csv` provides a `score` column.
The optional potency H5AD is not used for this handoff.

### COTAN

Requires:

- `counts` in `layers`
- `highly_variable` in `var`, only when `cotan-only-hvg: true`
- the configured `representation` in `obsm`

Provides:

- `macrostate` in `obs`

### CellRank

Requires:

- `Ms` in `layers`
- `velocity` in `layers`
- `connectivities` in `obsp`
- the configured `label-column` in `obs`
- `X_umap` in `obsm`

Provides:

- `macrostate` in `obs`

`cytotrace_score` is derived from `potency.csv` and is absent from the velocity
H5AD input contract for CellRank.

### STREAM

Requires:

- the configured `representation` in `obsm`
- the configured `label-column` in `obs`

Provides:

- `macrostate` in `obs`

### KNNSC

Requires:

- the configured `knnsc-embedding` in `obsm`
- the configured `representation` in `obsm`
- the configured `label-column` in `obs`

Provides:

- `macrostate` in `obs`

### Bin-Cells

Requires:

- `log-norm` in `layers`
- the configured `representation` in `obsm`
- `macrostate` in `obs`, only when starting from `macrostate-file` and needed
  downstream

Provides:

- `bin` in `layers`
- `distribution` in `var`

### Bin-Macrostates

Requires:

- `macrostate` in `obs`
- `bin` in `layers`
- the configured `representation` in `obsm`
- `distribution` in `var`

### Bin-DEA

Requires:

- `macrostate` in `obs`
- `log-norm` in `layers`
- the configured `representation` in `obsm`

## Reading the Output

Parameter errors identify invalid settings; file and metadata errors identify
missing or incompatible inputs; runtime errors identify unavailable tools or
environments. Warnings remain non-blocking.

## Limitations

`scbolt check` does not execute analyses or validate:

- numerical shape compatibility beyond visible H5AD groups and keys;
- semantic consistency of AnnData metadata values such as `cluster`,
  `macrostate`, or `condition`;
- biological validity of annotations or macrostates;
- exact package solver reproducibility;
- runtime memory requirements;
- solver convergence.
