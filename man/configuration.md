# Project configuration

scBOLT projects use two public YAML files. `scbolt.yml` stores the scientific
configuration and input routes, while `spec.yml` stores Boolean constraints
and node contracts. GNU Make remains the internal workflow engine, but neither
its syntax nor its variable names are required for normal use.

The `.scbolt` file remains the project locator. A new project contains:

```text
CONFIG=scbolt.yml
```

Run `scbolt init` to create both YAML files and the locator, or select another
project configuration for one command with `--config=<file>`.

## Resolution and defaults

Configuration values use this precedence, from highest to lowest:

1. command-line overrides;
2. the project `scbolt.yml`;
3. the global launcher configuration;
4. scBOLT defaults.

An absent YAML key therefore keeps the scBOLT default. An explicit `null`
represents an empty optional value, for example automatic HVG estimation:

```yaml
bin-hvg-top: null
```

Relative paths in `scbolt.yml` are resolved relative to the directory that
contains the YAML file. Relative command-line paths are resolved from the
launch directory.

The schema has no `version` key. Unknown keys, duplicate keys, incorrect YAML
types, and invalid condition names are rejected with their source line and
column. Booleans must be native YAML booleans (`true` or `false`), not quoted
strings.

Public keys use `kebab-case`, exactly like command-line options. Equivalent
`snake_case` spellings are intentionally rejected as unknown keys.

## Shape

The configuration is intentionally flat. Keys describe scientific decisions,
not internal pipeline modules:

```yaml
project-dir: project_gsm
inference-dir: infer
organism: mouse

gsm:
  ctrl: GSM5492245
  treated: GSM5492246

pca-dimensions: 15
neighbors: 14
resolution: 0.4
umap-min-dist: 0.5
umap-spread: 2.0

macrostate-method: knnsc
macrostate-size: 100

knnsc-centrality:
  ctrl: [Prom1, Prom2]
  treated: [Prom1, Prom2]

knnsc-periphery:
  ctrl: [Rep, Neu, Alt]
  treated: [Rep, Neu]

omics-hvg-method: loess
omics-hvg-top: 2000
bin-hvg-method: binning
bin-hvg-top: null
zeroes-are-zeroes: false

max-clauses: 4
inference-limit: 10000
spec-file: spec.yml
```

Do not introduce artificial sections such as `clustering: {neighbors: 14}`.

## Conditions

Condition-dependent values accept either mappings or flat keys suffixed by the
condition name. Condition names are arbitrary; `ctrl` and `treated` are not
hard-coded:

```yaml
conditions: [control, perturbation]

sra:
  control: [SRR_control_1, SRR_control_2]
  perturbation: [SRR_perturbation_1, SRR_perturbation_2]
```

The following compact form is equivalent:

```yaml
sra-control: [SRR_control_1, SRR_control_2]
sra-perturbation: [SRR_perturbation_1, SRR_perturbation_2]

knnsc-centrality-control: [Prom1, Prom2]
knnsc-centrality-perturbation: [Prom1]
```

When `conditions` is omitted, scBOLT derives its order from the first
appearance of mapped or suffixed condition keys. When it is present, every
condition must occur in that list. Use scalar `gsm` or `sra` values only for an
unnamed single-condition project.

The same generic condition rule applies to `gsm`, `sra`, `count-file`,
`macrostate-file`, `knnsc-centrality`, and `knnsc-periphery`. A single shared
`macrostate-file` is also accepted. The two condition-specific forms may be
mixed, but definitions of the same condition must agree; conflicting values
are rejected.

Command-line overrides use the equivalent dash-separated suffix, for example
`--knnsc-centrality-ctrl="Prom1 Prom2"`.

## Lists and mappings

Compact and vertical YAML lists are equivalent:

```yaml
bin-include-nodes: [Rara, Cebpa, Spi1]
```

```yaml
bin-include-nodes:
  - Rara
  - Cebpa
  - Spi1
```

This applies to every list-valued key in either YAML file, including values
nested under a condition mapping.

## Inference specification

The file selected by `spec-file`, normally `spec.yml`, contains four inference
contracts:

| Key | Meaning |
| --- | --- |
| `constraints` | BoNesis observations and dynamical constraints. |
| `important-nodes` | Nodes prioritized by gene selection. |
| `mandatory-nodes` | Nodes that every selected domain must retain. |
| `forbidden-nodes` | Nodes removed before gene selection. |

```yaml
constraints:
  - ctrl_prom1 = ~obs('ctrl_Prom1')
  - ctrl_rep = fixed(~obs('ctrl_Rep'))
  - ctrl_prom1 >= ctrl_rep

important-nodes: [Rara, Cebpa, Spi1]
mandatory-nodes: []
forbidden-nodes: []
```

Inference outputs are written below `project-dir/inference-dir`. To evaluate
another hypothesis without overwriting an existing inference, select another
configuration file and specification:

```yaml
inference-dir: infer-alternative
spec-file: spec-alternative.yml
```

The corresponding `spec-alternative.yml` contains the alternative contracts.
For example, run `scbolt bn-submin --config=scbolt-alternative.yml`. The
selected specification is a direct workflow dependency, so modifying it
rebuilds the `spec` module.

`inference-dir` must be a relative subdirectory of `project-dir`; absolute
paths and parent traversal with `..` are rejected.

## HVG settings

Omics analysis and binarization expose independent HVG settings. This keeps a
change in one workflow from silently changing the other:

```yaml
omics-hvg-method: loess
omics-hvg-top: 2000
bin-hvg-method: binning
bin-hvg-top: null
```

## Public key reference

The tables below inventory the public YAML keys. The legacy column is provided
only to migrate existing `params.mk` projects; these internal names are not
needed in new projects.

### Project and runtime

| YAML key | Legacy name | Default / use |
| --- | --- | --- |
| `backend` | `BACKEND` | `conda`; local or Docker execution backend. |
| `container-image` | `SCBOLT_IMAGE` | Published image matching the installed scBOLT version. |
| `container-engine` | `SCBOLT_CONTAINER_ENGINE` | `docker`. |
| `container-args` | `SCBOLT_CONTAINER_ARGS` | Extra container arguments. |
| `container-mounts` | `SCBOLT_CONTAINER_MOUNTS` | Extra mount paths. |
| `project-dir` | `PROJECT_DIR` | `project`; generated outputs. |
| `inference-dir` | `INFERENCE_DIR` | `infer`; inference outputs within the project directory. |
| `resources-dir` | `RESOURCES_DIR` | `resources`; shared resources. |
| `memory` | `MEMORY` | `50` GB; workflow memory budget. |
| `jobs` | `JOBS` | `16`; workflow parallelism. |
| `seed` | `SEED` | `10`; shared random seed. |
| `logging` | `LOGGING` | `true`; persistent logs. |
| `openblas-core-type` | `OPENBLAS_CORETYPE` | `HASWELL` on compatible x86-64 processors; numerical kernel profile. |
| `organism` | `ORGANISM` | Required by organism-aware modules. |
| `conditions` | `CONDITIONS` | Derived from mappings when omitted. |
| `references` | `REFERENCES` | Optional subset of conditions used as references. |
| `gsm[-<condition>]` | `GSM[_<CONDITION>]` | GEO matrix accession route; mapping and suffixed forms are accepted. |
| `sra[-<condition>]` | `SRA[_<CONDITION>]` | SRA run accession route; mapping and suffixed forms are accepted. |
| `count-file[-<condition>]` | `COUNT_FILES` | One precomputed count AnnData file per condition. |
| `macrostate-file[-<condition>]` | `MACROSTATE_FILES` | One shared or condition-specific macrostate AnnData file. |
| `binarization-file` | `BINARIZATION_FILE` | Precomputed binarization route. |
| `representation` | `REPRESENTATION` | `X_umap`; shared embedding key. |
| `label-column` | `LABEL_COL` | `label`; cell annotation column. |
| `labels` | `LABEL` | Cluster labels used by annotation. |
| `spec-file` | `SPEC_FILE` | `spec.yml`; Boolean inference specification. |
| `old-files` | `OLD_FILES` | Existing DAG files to trust. |

### External data and alignment

| YAML key | Legacy name | Default / use |
| --- | --- | --- |
| `genome-url` | `genome_url` | Organism-specific reference archive. |
| `repeat-masker-url` | `repeat_msk_url` | Organism-specific RepeatMasker table. |
| `gene-ontology-url` | `go_organism_url` | Current organism GO slim URL. |
| `alignment-tool` | `ALIGNMENT_TOOL` | `star`. |
| `star-barcode-length` | `STAR_CB_LEN` | `16`. |
| `star-umi-length` | `STAR_UMI_LEN` | `10`. |
| `star-whitelist` | `STAR_WHITELIST` | Optional barcode whitelist path. |
| `star-barcode-filter` | `STAR_BARCODE_FILTER` | `auto`. |
| `star-min-umi` | `STAR_MIN_UMI` | Optional threshold. |
| `star-top-barcodes` | `STAR_TOP_BARCODES` | Optional top-barcode count. |

### Preprocessing and clustering

| YAML key | Legacy name | Default / use |
| --- | --- | --- |
| `gene-dropout` | `GENE_DROPOUT` | `0.999`. |
| `gene-expression` | `GENE_EXPRESSION` | `[0, inf]`. |
| `gene-counts` | `GENE_COUNTS` | `[0, inf]`. |
| `cell-dropout` | `CELL_DROPOUT` | `1`. |
| `cell-expression` | `CELL_EXPRESSION` | `[0, inf]`. |
| `cell-reads` | `CELL_READS` | `[0, inf]`. |
| `mad-deviation` | `MAD_DEVIATION` | `[2, 2]`. |
| `consistent-mad` | `CONSISTENT_MAD` | `true`. |
| `mitochondrial-fraction` | `MT` | `0.05`. |
| `cell-cycle-correction` | `CC_CORRECTION` | `true`. |
| `omics-hvg-method` | `OMICS_HVG_METHOD` | `loess`. |
| `omics-hvg-top` | `OMICS_HVG_TOP` | `null`. |
| `omics-hvg-span` | `OMICS_HVG_SPAN` | `0.3`. |
| `omics-hvg-bins` | `OMICS_HVG_BINS` | `20`. |
| `bin-hvg-method` | `BIN_HVG_METHOD` | `binning`. |
| `bin-hvg-top` | `BIN_HVG_TOP` | `null`. |
| `bin-hvg-span` | `BIN_HVG_SPAN` | `0.3`. |
| `bin-hvg-bins` | `BIN_HVG_BINS` | `20`. |
| `integration` | `INTEGRATION` | `bbknn`. |
| `pca-dimensions` | `DIM_PCA` | `50`. |
| `embedding-dimensions` | `DIM_EMBEDDING` | `2`. |
| `centered-pca` | `CENTERED_PCA` | `true`. |
| `pca-only-hvg` | `PCA_ONLY_HVG` | `true`. |
| `neighbors` | `NEIGHBORS` | `20`. |
| `metric` | `METRIC` | `euclidean`. |
| `resolution` | `RESOLUTION` | `0.4`. |
| `umap-min-dist` | `MIN_DIST` | `0.1`. |
| `umap-spread` | `SPREAD` | `1`. |
| `embedding-iterations` | `EMBEDDING_N_ITER` | `500`. |

### Differential analysis, velocity, and potency

| YAML key | Legacy name | Default / use |
| --- | --- | --- |
| `dea-method` | `DEA_METHOD` | `wilcoxon`. |
| `logfc` | `LOGFC` | `0.25`. |
| `correction` | `CORRECTION` | `bonferroni`. |
| `alpha` | `ALPHA` | `0.05`. |
| `moment-dimensions` | `DIM_MOMENT` | `15`. |
| `velocity-only-hvg` | `VELOCITY_ONLY_HVG` | `true`. |
| `velocity-mode` | `SMM_MODE` | `dynamical`. |
| `potency-batch-size` | `BATCH_SIZE` | `20000`. |
| `potency-smoothing-batch-size` | `SMOOTH_BATCH_SIZE` | `1000`. |

### Macrostates

| YAML key | Legacy name | Default / use |
| --- | --- | --- |
| `macrostate-size` | `MACROSTATE_SIZE` | `100`. |
| `macrostate-method` | `MACROSTATE_METHOD` | `cellrank`. |
| `cotan-method` | `COTAN_METHOD` | `strong-merging`. |
| `cotan-only-hvg` | `COTAN_ONLY_HVG` | `false`. |
| `cotan-max-iterations` | `MAX_ITER` | `25`. |
| `cellrank-method` | `CELLRANK_METHOD` | `stability`. |
| `cellrank-states` | `STATES` | `10`. |
| `cellrank-initial-states` | `INITIAL_STATES` | `5`. |
| `cellrank-terminal-states` | `TERMINAL_STATES` | `5`. |
| `cellrank-stability` | `CELLRANK_STABILITY` | `0.96`. |
| `cellrank-alpha` | `CELLRANK_ALPHA` | `1.0`. |
| `stream-clustering-method` | `CLUSTERING_METHOD` | `kmeans`. |
| `stream-cluster-number` | `CLUSTER_NUMBER` | `6`. |
| `stream-alpha` | `ALPHA_EPG` | `0.03`. |
| `stream-mu` | `MU_EPG` | `0.05`. |
| `stream-lambda` | `LAMBDA_EPG` | `0.05`. |
| `stream-extend` | `EXTEND_EPG` | `true`. |
| `stream-extend-mode` | `EXTEND_MODE` | `QuantDists`. |
| `stream-extend-parameter` | `EXTEND_PARAMETER` | `0.8`. |
| `stream-prune` | `PRUNE_EPG` | `false`. |
| `stream-collapse-parameter` | `COLLAPSE_PARAMETER` | `false`. |
| `knnsc-embedding` | `KNNSC_EMBEDDING` | `X_umap`. |
| `knnsc-dimensions` | `KNNSC_DIMENSION` | All available dimensions. |
| `knnsc-neighbors` | `KNNSC_NEIGHBORS` | `20`. |
| `knnsc-min-cluster-size` | `KNNSC_MIN_CLUSTER_SIZE` | `20`. |
| `knnsc-centrality[-<condition>]` | `KNNSC_CENTRALITY_<CONDITION>` | Condition mapping or suffixed key. |
| `knnsc-periphery[-<condition>]` | `KNNSC_PERIPHERY_<CONDITION>` | Condition mapping or suffixed key. |

### Binarization

| YAML key | Legacy name | Default / use |
| --- | --- | --- |
| `binarization-method` | `BIN_METHOD` | `consensus`. |
| `bin-include-nodes` | `BIN_INCLUDE_NODES` | Additional nodes retained when HVG filtering is enabled; empty by default. |
| `scboolseq-only-hvg` | `BIN_SCBOOLSEQ_ONLY_HVG` | `true`. |
| `scboolseq-openblas-threads` | `SCBOOLSEQ_OPENBLAS_THREADS` | `auto`. |
| `scboolseq-omp-threads` | `SCBOOLSEQ_OMP_THREADS` | `auto`. |
| `unimodal-quantile` | `UNIMODAL_QUANTILE` | `0.10`. |
| `zeroes-are-zeroes` | `ZEROES_ARE_ZEROES` | `true`. |
| `undefined-threshold` | `NANS_THRESHOLD` | `0.3`. |
| `bimodal-threshold` | `BIMODAL_THRESHOLD` | `0.7`. |
| `zero-inflated-threshold` | `ZEROINF_THRESHOLD` | `0.7`. |
| `unimodal-threshold` | `UNIMODAL_THRESHOLD` | `0.7`. |
| `binarization-dea-only-hvg` | `BIN_DEA_ONLY_HVG` | `true`. |
| `binarization-logfc` | `BIN_LOGFC` | `0.5`. |
| `binarization-correction` | `BIN_CORRECTION` | `benjamini-hochberg`. |
| `binarization-alpha` | `BIN_ALPHA` | `0.05`. |

### Boolean inference

| YAML key | Legacy name | Default / use |
| --- | --- | --- |
| `prior-knowledge` | `PRIOR_KNOWLEDGE` | `collectri`. |
| `geneinfo-version` | `GENEINFO_VERSION` | `bundled`. |
| `omnipath-version` | `OMNIPATH_VERSION` | `latest`. |
| `hcop-version` | `HCOP_VERSION` | `bundled`. |
| `dorothea-api` | `DOROTHEA_API` | `modern`. |
| `dorothea-compatibility` | `DOROTHEA_COMPATIBILITY` | `true`. |
| `dorothea-levels` | `DOROTHEA_LEVELS` | `[A, B, C]`. |
| `max-clauses` | `MAX_CLAUSES` | `8`. |
| `clause-continuation-soft` | `CLAUSE_CONTINUATION_SOFT` | `false`. |
| `clause-continuation-relaxed` | `CLAUSE_CONTINUATION_RELAXED` | `true`. |
| `clause-continuation-seed` | `CLAUSE_CONTINUATION_SEED` | `true`. |
| `clause-continuation-lock` | `CLAUSE_CONTINUATION_LOCK` | `true`. |
| `clause-bound-patience` | `PATIENCE_CLAUSE_BOUND` | `30m`. |
| `domain-continuation-soft` | `DOMAIN_CONTINUATION_SOFT` | `false`. |
| `domain-continuation-relaxed` | `DOMAIN_CONTINUATION_RELAXED` | `true`. |
| `domain-continuation-seed` | `DOMAIN_CONTINUATION_SEED` | `true`. |
| `domain-continuation-lock` | `DOMAIN_CONTINUATION_LOCK` | `true`. |
| `domain-wave-patience` | `PATIENCE_DOMAIN_WAVE` | `5m` for `SOFT`, `RELAXED`, and `SEED`. |
| `domain-wave-patience-lock` | `PATIENCE_DOMAIN_WAVE_LOCK` | `10m` for `LOCK`. |
| `minimum-domain-yield` | `MIN_DOMAIN_YIELD` | `0.10`. |
| `maximum-domain-refreshes` | `MAX_DOMAIN_REFRESHES` | `1`. |
| `clingo-threads` | `CLINGO_THREADS` | `1`. |
| `clingo-config-<stage>` | `CLINGO_CONFIG_<STAGE>` | Named configuration or file. |
| `clingo-mode-<stage>` | `CLINGO_MODE_<STAGE>` | Stage-dependent. |
| `clingo-strategy-<stage>` | `CLINGO_STRATEGY_<STAGE>` | Stage-dependent. |
| `timeout-<stage>` | `TIMEOUT_<STAGE>` | Stage-dependent duration. |
| `clingo-mode-min` | `CLINGO_MODE_MIN` | `optN`. |
| `minimize-self-loops-constants` | `MIN_SELF_LOOP_CONSTS` | `true`. |
| `minimize-self-loops-inference` | `MIN_SELF_LOOP_INFER` | `true`. |
| `configuration-formats` | `CONFIG_FORMATS` | `[csv]`. |
| `graph-formats` | `GRAPH_FORMATS` | `[dot]`. |
| `inference-limit` | `INFER_LIMIT` | `null`; enumerate all. |

The stage placeholder is one of `soft`, `consts`, `relaxed`, `seed`, or
`lock`. Clause and domain continuation switches do not apply to `consts`.

## Legacy projects

Projects containing `.scbolt` with `PARAMS=params.mk`, or projects selected
with `--params=<file>`, remain readable and are not rewritten. A legacy project
can be migrated by translating its Make parameters to `scbolt.yml`, retaining
`spec.yml` through the `spec-file` key, and changing the locator:

```text
CONFIG=scbolt.yml
```

Keeping `params.mk` beside `scbolt.yml` during validation is safe and makes
rollback straightforward.
