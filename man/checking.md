# Checking with `scbolt check`

`scbolt check <module>` validates the parameters, files, AnnData metadata,
conda environments, and external commands needed to build a selected scBOLT
module.

The check is intentionally target-aware: it should validate what the selected
target will actually use, not every parameter in the project.

## Usage

```bash
scbolt check <module>
```

Examples:

```bash
scbolt check velocity
scbolt check bin-dea --reset-target=bin-dea
scbolt check bin-cells --macrostate-files=case/macrostate.h5ad
scbolt check max-nodes-seed
```

The module argument selects what to inspect. `--reset-target`,
`--trust-target`, `--trust-existing`, and `--old-file` are applied before
checking because they affect the rebuilt pipeline segment.

## Execution Model

`scbolt check` works in two phases.

First, it asks the internal workflow engine what would run. This dry-run defines
what will be checked. If it is empty, the target is already up to date and
`scbolt check` prints:

```text
Files and metadata
  ✓ target '<module>' already up to date

Status
  Check passed for target '<module>'.
```

Otherwise, `scbolt check` inspects the dry-run output and validates only the
parameters, resources, and tools that appear in the rebuilt segment.

Second, it prints grouped diagnostics. The output order is:

1. project parameters
2. core parameters
3. method parameters
4. external resource parameters
5. files and AnnData metadata
6. runtime environments and commands
7. other checks
8. final status

Diagnostic statuses are:

```text
✓ successful check
⚠ non-blocking warning
✗ blocking error
```

A single blocking error makes `scbolt check` exit with a non-zero status. The
final `Status` section reports the numbers of blocking errors and warnings.

## Parameter Taxonomy

scBOLT configuration values are organized into four conceptual categories.
This taxonomy is used by `scbolt check`, `scbolt config`, and target-specific
validation.

When validating a target, only parameter categories required by the selected
target should be checked. The pipeline should avoid failing early for unrelated
missing parameters.

Core parameters are intentionally strict: outside diagnostic commands such as
`scbolt check` and `scbolt config`, invalid core parameters fail during global
pipeline initialization.

### Project Parameters

Project parameters describe the biological project, datasets, and user-defined
interpretations. They generally depend on the studied biological dataset or
case study and are expected to be customized by users.

Examples:

- `organism`
- `conditions`
- `sra`
- `labels`
- `constraints`

These parameters should only be validated by targets requiring user-defined
biological information.

Example output:

```text
Project parameters
  ✓ labels=Prom1 Prom2 Rep (needed by target 'annotation')
  ✗ required project parameter not defined: labels (needed by target 'annotation')
```

### Core Parameters

Core parameters control global pipeline execution, reproducibility, resources,
runtime behavior, output organization, and shared cross-module conventions.

Examples:

- project configuration
- `references`
- `project_dir`
- `resources_dir`
- `memory`
- `jobs`
- `seed`
- `logging`
- `representation`
- `label_column`
- `old_files`

Core parameters usually have defaults and are not tied to a specific analytical
method. They are validated during pipeline initialization, except in diagnostic
modes where missing target-specific values should not prevent inspection of
unrelated targets.

Example output:

```text
Core parameters
  ✓ jobs=16
  ✓ representation=X_umap
```

### Method Parameters

Method parameters control preprocessing, clustering, trajectory inference,
binarization, Boolean inference, exports, and solver behavior. They define the
analytical behavior of the pipeline.

Examples:

- `alignment_tool`
- `star_barcode_filter`
- `consistent_mad`
- `cell_cycle_correction`
- `pca_dimensions`
- `centered_pca`
- `velocity_only_hvg`
- `macrostate_method`
- `knnsc_embedding`
- `knnsc_min_cluster_size`
- `binarization_method`
- `binarization_hvg_method`
- `max_clauses`
- `clause_continuation_<stage>`
- `clingo_<setting>_<stage>`
- `timeout_<stage>`

Method parameters should only be validated by targets using the associated
method or module.

Example output:

```text
Method parameters
  ✓ knnsc_embedding=X_umap (needed by target 'knnsc')
  ✗ unsupported value for method parameter binarization_method (supported values: scboolseq, dea, consensus)
```

### External Resource Parameters

External resource parameters reference files, custom resources, or precomputed
artifacts used by the pipeline.

Examples:

- `star_whitelist`
- `count_files`
- `binarization_file`
- `macrostate_files`
- `prior_knowledge`
- `geneinfo_version`
- `omnipath_version`
- `hcop_version`
- `clingo_config_<stage>`

`prior_knowledge` may refer to symbolic built-in resources (`collectri`,
`dorothea`) or to a user-provided file. `geneinfo_version` and
`omnipath_version` select the database versions used for gene identifiers and
OmniPath-derived priors. `hcop_version` selects the orthology resource used for
non-human CollecTRI/DoRothEA priors. `clingo_config_<stage>` may refer to named Clingo
configurations (`auto`, `frumpy`, `jumpy`, `tweety`, `handy`, `crafty`,
`trendy`, `many`) or to custom configuration files.

External resource parameters should only be validated when the corresponding
resource or file is effectively required by the selected target.

Example output:

```text
External resources
  ✓ macrostate_files=case/macrostate.h5ad (needed by target 'bin-dea')
  ✗ required file not found: case/macrostate.h5ad
```

## File, Command, and Environment Checks

`scbolt check` validates external resources used by the rebuilt segment.

File checks include resources such as:

- the active project configuration;
- reference genome archive sources;
- RepeatMasker annotation source for Velocyto;
- user-provided `count_files` or `macrostate_files`;
- custom prior networks;
- custom Clingo configuration files.

Command checks currently include tools that are actually visible in the dry-run,
for example:

- `conda`
- `cellranger`
- `dot`

Conda environment checks verify that referenced `scbolt-*` environments exist.
They also compare installed packages with the corresponding `envs/conda/*.yml` file.
Mismatches are warnings, not failures, because users may intentionally keep a
newer or patched environment.

Example:

```text
Runtime
  ✓ conda environment found: scbolt-core
  ⚠ conda environment mismatch: scbolt-core (bonesistools: 1.1.6->1.2.3; mpbn: 4.4->4.2)
```

For git-installed packages, the checker can validate the installed commit when
the package exposes PEP 610 metadata. This is used for packages such as
`bonesis` and `scvelo`.

## AnnData Dependency Validation

`scbolt check <target>` validates AnnData metadata dependencies before
executing a target.

The validation inspects the first existing AnnData boundary files that would be
consumed by the selected target, per relevant reference, and verifies that all
required fields are present.

The check is lightweight:

- it does not load the full AnnData object;
- it inspects only HDF5 metadata (`obs`, `var`, `obsm`, `obsp`, `layers`);
- it fails early with a clear error message when a required field is missing.

`provides` lists only fields that are needed by downstream modules. It is not
intended to be an exhaustive inventory of all fields created by each script.

Most AnnData-to-AnnData targets preserve input metadata. Their effective output
metadata is therefore:

```text
input metadata + provides
```

unless a target explicitly rewrites or drops fields.

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

### Validation Strategy

The AnnData checker reasons over the rebuilt pipeline segment:

1. Run the target dry-run with `--reset-target`, `--trust-target`,
   `--trust-existing`, and `--old-file` options applied.
2. Extract the ordered list of AnnData-producing and AnnData-consuming commands
   that will actually run.
3. Parse each known script command into an operation:
   - input H5AD files;
   - output H5AD files;
   - required metadata fields;
   - provided metadata fields;
   - whether downstream metadata is preserved from the input.
4. Walk operations backward from downstream to upstream and propagate unresolved
   metadata requirements to the boundary files that already exist.
5. Validate only those unresolved requirements against existing H5AD files.

Example: if `scbolt check potency --reset-target=normalization` rebuilds
normalization, clustering, annotation, and potency, then `potency` may require
`counts` as a layer. This should not necessarily be checked only one step before
`potency`; the checker should know that `counts` is required at the rebuilt
segment boundary and then preserved through the rebuilt AnnData steps.

Non-AnnData artifacts stay outside this H5AD metadata table and are checked
by existing file or target dependency checks. For example, CellRank uses
`potency.csv` and requires its `score` column; the workflow extracts this
column and inserts it into a temporary H5AD as `cytotrace_score` before running
the CellRank script.

### `count_files`

`count_files` is a count-level AnnData entry point. It must contain one H5AD
file per condition, ordered like `conditions`. When defined, filtering consumes
these files directly instead of depending on Velocyto or public GEO matrix
loading. Gene-name standardization is applied by `filter.py`, so count files,
GEO matrices, and Velocyto outputs share the same downstream contract.
Each file must contain `counts` in `layers`; `adata.X` is not used as a
fallback expression matrix.

Input routes are mutually exclusive:

```text
sra | gsm | count_files | macrostate_files | binarization_file
```

Only one input-route family should be defined at a time.

### `macrostate_files`

`macrostate_files` is a special external AnnData boundary for users restarting
the pipeline at binarization. It accepts either one multi-condition AnnData file
or one AnnData file per condition, ordered like `conditions`. When defined,
`bin-cells`, `bin-macrostates`, and `bin-dea` depend on a prepared temporary
copy of these files instead of depending on internally generated macrostate
H5AD/CSV pairs.

The user-provided file must contain:

- `log-norm` in `layers`;
- `macrostate` in `obs`;
- `condition` in `obs`, required when a single file is used for a
  multi-condition project;
- the configured `representation` in `obsm`.

Expression is always read from these named layers. `adata.X` is not used as a
fallback expression matrix.

If downstream HVG selection uses `binarization_hvg_method: loess`, the file must also
contain:

- `counts` in `layers`.

For multi-condition projects, the preparation step prefixes `macrostate` values
with condition values so that downstream binarization sees globally unique
macrostate labels. This matches the behavior of internally generated macrostate
CSVs.

## AnnData Target Dependency Specification

The following table documents fields that are required or provided for
downstream use. It is intentionally not a complete inventory of every field
produced by each script.

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

- the configured `label_column` in `obs`

### Per-Condition Annotation

Requires:

- `condition` in `obs` from the integrated AnnData when using multiple
  conditions;
- `cluster` in `obs` when using a single condition;
- the configured `representation` in `obsm`.

Provides:

- the configured `label_column` in `obs`

### Velocity

Requires:

- `counts` in `layers`
- `spliced` in `layers`
- `unspliced` in `layers`
- `X_pca` in `obsm`
- `X_umap` in `obsm`
- the configured `label_column` in `obs`
- `connectivities` in `obsp`
- `highly_variable` in `var`, only when `velocity_only_hvg: true`

Provides:

- `Ms` in `layers`
- `Mu` in `layers`
- `variance_velocity` in `layers`
- `velocity` in `layers`

### Potency

Requires:

- `counts` in `layers`
- the configured `label_column` in `obs`
- the configured `representation` in `obsm`

Provides:

- no downstream AnnData metadata

The pipeline consumes `potency.csv` downstream. The optional potency H5AD
contains `cytotrace_*` fields, but it is not the CellRank input used by the
workflow. The downstream CellRank recipe requires the `score` column from
`potency.csv`.

### COTAN

Requires:

- `counts` in `layers`
- `highly_variable` in `var`, only when `cotan_only_hvg: true`
- the configured `representation` in `obsm`

Provides:

- `macrostate` in `obs`

### CellRank

Requires:

- `Ms` in `layers`
- `velocity` in `layers`
- `connectivities` in `obsp`
- the configured `label_column` in `obs`
- `X_umap` in `obsm`

Provides:

- `macrostate` in `obs`

`cytotrace_score` is added to a temporary CellRank input H5AD from `potency.csv`
inside the CellRank recipe. It is not expected to exist in the pre-existing
velocity H5AD.

### STREAM

Requires:

- the configured `representation` in `obsm`
- the configured `label_column` in `obs`

Provides:

- `macrostate` in `obs`

### KNNSC

Requires:

- the configured `knnsc_embedding` in `obsm`
- the configured `representation` in `obsm`
- the configured `label_column` in `obs`

Provides:

- `macrostate` in `obs`

### Bin-Cells

Requires:

- `log-norm` in `layers`
- the configured `representation` in `obsm`
- `macrostate` in `obs`, only when starting from `macrostate_files` and needed
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

The most useful way to read `scbolt check` output is from top to bottom.

Parameter failures usually mean the selected module cannot even be configured.
File and H5AD failures mean the module could start, but one of its inputs is
missing or does not contain the expected metadata. Conda and command failures
mean the local installation is incomplete or different from the repository
environment files.

Warnings are non-blocking. They point to local differences that may be
intentional, for example a patched conda environment or a package installed
from a local checkout.

For example:

```text
Method parameters
  ✓ binarization_method=consensus (needed by target 'binarization')

Files and metadata
  ✓ h5ad metadata: layer 'log-norm' found (reference: input)
  ✗ h5ad metadata: obs 'macrostate' missing (/path/to/macrostate.h5ad, reference: input)

Runtime
  ⚠ conda environment mismatch: scbolt-core (bonesistools: 1.1.6->1.2.3)
```

In this example, the target is configured correctly, but the provided AnnData
file cannot be used for binarization because it lacks `obs["macrostate"]`.

## Limitations

`scbolt check` is a preflight check. It does not execute analytical recipes and
cannot prove that a target will complete successfully.

In particular, it does not validate:

- numerical shape compatibility beyond visible H5AD groups and keys;
- semantic consistency of AnnData metadata values such as `cluster`,
  `macrostate`, or `condition`;
- biological validity of annotations or macrostates;
- exact package solver reproducibility;
- runtime memory requirements;
- solver convergence.

It is designed to catch configuration mistakes, missing files, missing metadata,
missing environments, and obvious target-specific incompatibilities before a
long pipeline step starts.
