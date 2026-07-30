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
binarization_hvg_top: null
```

Relative paths in `scbolt.yml` are resolved relative to the directory that
contains the YAML file. Relative command-line paths are resolved from the
launch directory.

The schema has no `version` key. Unknown keys, duplicate keys, incorrect YAML
types, and invalid condition names are rejected with their source line and
column. Booleans must be native YAML booleans (`true` or `false`), not quoted
strings.

## Shape

The configuration is intentionally flat. Keys describe scientific decisions,
not internal pipeline modules:

```yaml
project_dir: project_gsm
inference_dir: infer
organism: mouse

gsm:
  ctrl: GSM5492245
  treated: GSM5492246

pca_dimensions: 15
neighbors: 14
resolution: 0.4
umap_min_dist: 0.5
umap_spread: 2.0

macrostate_method: knnsc
macrostate_size: 100

knnsc_centrality:
  ctrl: [Prom1, Prom2]
  treated: [Prom1, Prom2]

knnsc_periphery:
  ctrl: [Rep, Neu, Alt]
  treated: [Rep, Neu]

hvg_method: binning
hvg_top: null
zeroes_are_zeroes: false

max_clauses: 4
inference_limit: 10000
spec_file: spec.yml
```

Do not introduce artificial sections such as `clustering: {neighbors: 14}`.

## Conditions

Condition-dependent values accept either mappings or flat keys suffixed by the
condition name. Condition names are arbitrary; `ctrl` and `treated` are not
hard-coded:

```yaml
conditions: [control, treatment_a, treatment_b]

gsm:
  control: GSM000001
  treatment_a: GSM000002
  treatment_b: GSM000003
```

The following compact form is equivalent:

```yaml
gsm_control: GSM000001
gsm_treatment_a: GSM000002
gsm_treatment_b: GSM000003

knnsc_centrality_control: [Prom1, Prom2]
knnsc_centrality_treatment_a: [Prom1, Prom2]
knnsc_centrality_treatment_b: [Prom1]
```

When `conditions` is omitted, scBOLT derives its order from the first
appearance of mapped or suffixed condition keys. When it is present, every
condition must occur in that list. Use scalar `gsm` or `sra` values only for an
unnamed single-condition project.

The same generic condition rule applies to `gsm`, `sra`, `knnsc_centrality`, and
`knnsc_periphery`. The two forms may be mixed, but definitions of the same
condition must agree; conflicting values are rejected.

Command-line overrides use the equivalent dash-separated suffix, for example
`--knnsc-centrality-ctrl="Prom1 Prom2"`.

## Lists and mappings

Compact and vertical YAML lists are equivalent:

```yaml
binarization_include_nodes: [Rara, Cebpa, Spi1]
```

```yaml
binarization_include_nodes:
  - Rara
  - Cebpa
  - Spi1
```

This applies to every list-valued key in either YAML file, including values
nested under a condition mapping.

## Inference specification

The file selected by `spec_file`, normally `spec.yml`, contains four inference
contracts:

| Key | Meaning |
| --- | --- |
| `constraints` | BoNesis observations and dynamical constraints. |
| `important_nodes` | Nodes prioritized by gene selection. |
| `mandatory_nodes` | Nodes that every selected domain must retain. |
| `forbidden_nodes` | Nodes removed before gene selection. |

```yaml
constraints:
  - ctrl_prom1 = ~obs('ctrl_Prom1')
  - ctrl_rep = fixed(~obs('ctrl_Rep'))
  - ctrl_prom1 >= ctrl_rep

important_nodes: [Rara, Cebpa, Spi1]
mandatory_nodes: []
forbidden_nodes: []
```

`dynamical_constraints` remains accepted as a deprecated alias for
`constraints` in legacy specification files.

Inference outputs are written below `project_dir/inference_dir`. To evaluate
another hypothesis without overwriting an existing inference, select another
configuration file and specification:

```yaml
inference_dir: infer-alternative
spec_file: spec-alternative.yml
```

The corresponding `spec-alternative.yml` contains the alternative contracts.
For example, run `scbolt bn-submin --config=scbolt-alternative.yml`. The
selected specification is a direct workflow dependency, so modifying it
rebuilds the `spec` module.

`inference_dir` must be a relative subdirectory of `project_dir`; absolute
paths and parent traversal with `..` are rejected.

## Shared HVG settings

The concise `hvg_method`, `hvg_top`, `hvg_span`, and `hvg_bins` keys set both
analysis and binarization HVG settings. A specific key takes priority for its
own workflow:

```yaml
hvg_method: binning
analysis_hvg_method: loess
```

This means analysis uses `loess`, while binarization keeps `binning`. The
specific forms are `analysis_hvg_*` and `binarization_hvg_*`.

## Public key reference

The tables below inventory the public YAML keys. The legacy column is provided
only to migrate existing `params.mk` projects; these internal names are not
needed in new projects.

### Project and runtime

| YAML key | Legacy name | Default / use |
| --- | --- | --- |
| `backend` | `BACKEND` | `conda`; local or Docker execution backend. |
| `container_image` | `SCBOLT_IMAGE` | Published scBOLT image. |
| `container_engine` | `SCBOLT_CONTAINER_ENGINE` | `docker`. |
| `container_args` | `SCBOLT_CONTAINER_ARGS` | Extra container arguments. |
| `container_mounts` | `SCBOLT_CONTAINER_MOUNTS` | Extra mount paths. |
| `project_dir` | `PROJECT_DIR` | `project`; generated outputs. |
| `inference_dir` | `INFERENCE_DIR` | `infer`; inference outputs within the project directory. |
| `resources_dir` | `RESOURCES_DIR` | `resources`; shared resources. |
| `memory` | `MEMORY` | `50` GB; workflow memory budget. |
| `jobs` | `JOBS` | `16`; workflow parallelism. |
| `seed` | `SEED` | `10`; shared random seed. |
| `logging` | `LOGGING` | `true`; persistent logs. |
| `openblas_core_type` | `OPENBLAS_CORETYPE` | `HASWELL` on compatible x86-64 processors; numerical kernel profile. |
| `organism` | `ORGANISM` | Required by organism-aware modules. |
| `conditions` | `CONDITIONS` | Derived from mappings when omitted. |
| `references` | `REFERENCES` | Optional subset of conditions used as references. |
| `gsm[_<condition>]` | `GSM[_<CONDITION>]` | GEO matrix accession route; mapping and suffixed forms are accepted. |
| `sra[_<condition>]` | `SRA[_<CONDITION>]` | SRA run accession route; mapping and suffixed forms are accepted. |
| `count_files` | `COUNT_FILES` | Precomputed count AnnData route. |
| `macrostate_files` | `MACROSTATE_FILES` | Precomputed macrostate AnnData route. |
| `binarization_file` | `BINARIZATION_FILE` | Precomputed binarization route. |
| `representation` | `REPRESENTATION` | `X_umap`; shared embedding key. |
| `label_column` | `LABEL_COL` | `label`; cell annotation column. |
| `labels` | `LABEL` | Cluster labels used by annotation. |
| `spec_file` | `SPEC_FILE` | `spec.yml`; Boolean inference specification. |
| `old_files` | `OLD_FILES` | Existing DAG files to trust. |

### External data and alignment

| YAML key | Legacy name | Default / use |
| --- | --- | --- |
| `genome_url` | `genome_url` | Organism-specific reference archive. |
| `repeat_masker_url` | `repeat_msk_url` | Organism-specific RepeatMasker table. |
| `gene_ontology_url` | `go_organism_url` | Current organism GO slim URL. |
| `alignment_tool` | `ALIGNMENT_TOOL` | `star`. |
| `star_barcode_length` | `STAR_CB_LEN` | `16`. |
| `star_umi_length` | `STAR_UMI_LEN` | `10`. |
| `star_whitelist` | `STAR_WHITELIST` | Optional barcode whitelist path. |
| `star_barcode_filter` | `STAR_BARCODE_FILTER` | `auto`. |
| `star_min_umi` | `STAR_MIN_UMI` | Optional threshold. |
| `star_top_barcodes` | `STAR_TOP_BARCODES` | Optional top-barcode count. |

### Preprocessing and clustering

| YAML key | Legacy name | Default / use |
| --- | --- | --- |
| `gene_dropout` | `GENE_DROPOUT` | `0.999`. |
| `gene_expression` | `GENE_EXPRESSION` | `[0, inf]`. |
| `gene_counts` | `GENE_COUNTS` | `[0, inf]`. |
| `cell_dropout` | `CELL_DROPOUT` | `1`. |
| `cell_expression` | `CELL_EXPRESSION` | `[0, inf]`. |
| `cell_reads` | `CELL_READS` | `[0, inf]`. |
| `mad_deviation` | `MAD_DEVIATION` | `[2, 2]`. |
| `consistent_mad` | `CONSISTENT_MAD` | `true`. |
| `mitochondrial_fraction` | `MT` | `0.05`. |
| `cell_cycle_correction` | `CC_CORRECTION` | `true`. |
| `hvg_method` | analysis and binarization HVG methods | Shared convenience key. |
| `hvg_top` | analysis and binarization HVG counts | `null` selects automatically. |
| `hvg_span` | analysis and binarization HVG spans | `0.3`. |
| `hvg_bins` | analysis and binarization HVG bins | `20`. |
| `analysis_hvg_method` | `ANALYSIS_HVG_METHOD` | `loess`. |
| `analysis_hvg_top` | `ANALYSIS_HVG_TOP` | `null`. |
| `analysis_hvg_span` | `ANALYSIS_HVG_SPAN` | `0.3`. |
| `analysis_hvg_bins` | `ANALYSIS_HVG_BINS` | `20`. |
| `binarization_hvg_method` | `BIN_HVG_METHOD` | `binning`. |
| `binarization_hvg_top` | `BIN_HVG_TOP` | `null`. |
| `binarization_hvg_span` | `BIN_HVG_SPAN` | `0.3`. |
| `binarization_hvg_bins` | `BIN_HVG_BINS` | `20`. |
| `integration` | `INTEGRATION` | `bbknn`. |
| `pca_dimensions` | `DIM_PCA` | `50`. |
| `embedding_dimensions` | `DIM_EMBEDDING` | `2`. |
| `centered_pca` | `CENTERED_PCA` | `true`. |
| `pca_only_hvg` | `PCA_ONLY_HVG` | `true`. |
| `neighbors` | `NEIGHBORS` | `20`. |
| `metric` | `METRIC` | `euclidean`. |
| `resolution` | `RESOLUTION` | `0.4`. |
| `umap_min_dist` | `MIN_DIST` | `0.1`. |
| `umap_spread` | `SPREAD` | `1`. |
| `embedding_iterations` | `EMBEDDING_N_ITER` | `500`. |

### Differential analysis, velocity, and potency

| YAML key | Legacy name | Default / use |
| --- | --- | --- |
| `dea_method` | `DEA_METHOD` | `wilcoxon`. |
| `logfc` | `LOGFC` | `0.25`. |
| `correction` | `CORRECTION` | `bonferroni`. |
| `alpha` | `ALPHA` | `0.05`. |
| `moment_dimensions` | `DIM_MOMENT` | `15`. |
| `velocity_only_hvg` | `VELOCITY_ONLY_HVG` | `true`. |
| `velocity_mode` | `SMM_MODE` | `dynamical`. |
| `potency_batch_size` | `BATCH_SIZE` | `20000`. |
| `potency_smoothing_batch_size` | `SMOOTH_BATCH_SIZE` | `1000`. |

### Macrostates

| YAML key | Legacy name | Default / use |
| --- | --- | --- |
| `macrostate_size` | `MACROSTATE_SIZE` | `100`. |
| `macrostate_method` | `MACROSTATE_METHOD` | `cellrank`. |
| `cotan_method` | `COTAN_METHOD` | `strong-merging`. |
| `cotan_only_hvg` | `COTAN_ONLY_HVG` | `false`. |
| `cotan_max_iterations` | `MAX_ITER` | `25`. |
| `cellrank_method` | `CELLRANK_METHOD` | `stability`. |
| `cellrank_states` | `STATES` | `10`. |
| `cellrank_initial_states` | `INITIAL_STATES` | `5`. |
| `cellrank_terminal_states` | `TERMINAL_STATES` | `5`. |
| `cellrank_stability` | `CELLRANK_STABILITY` | `0.96`. |
| `cellrank_alpha` | `CELLRANK_ALPHA` | `1.0`. |
| `stream_clustering_method` | `CLUSTERING_METHOD` | `kmeans`. |
| `stream_cluster_number` | `CLUSTER_NUMBER` | `6`. |
| `stream_alpha` | `ALPHA_EPG` | `0.03`. |
| `stream_mu` | `MU_EPG` | `0.05`. |
| `stream_lambda` | `LAMBDA_EPG` | `0.05`. |
| `stream_extend` | `EXTEND_EPG` | `true`. |
| `stream_extend_mode` | `EXTEND_MODE` | `QuantDists`. |
| `stream_extend_parameter` | `EXTEND_PARAMETER` | `0.8`. |
| `stream_prune` | `PRUNE_EPG` | `false`. |
| `stream_collapse_parameter` | `COLLAPSE_PARAMETER` | `false`. |
| `knnsc_embedding` | `KNNSC_EMBEDDING` | `X_umap`. |
| `knnsc_dimensions` | `KNNSC_DIMENSION` | All available dimensions. |
| `knnsc_neighbors` | `KNNSC_NEIGHBORS` | `20`. |
| `knnsc_min_cluster_size` | `KNNSC_MIN_CLUSTER_SIZE` | `20`. |
| `knnsc_centrality[_<condition>]` | `KNNSC_CENTRALITY_<CONDITION>` | Condition mapping or suffixed key. |
| `knnsc_periphery[_<condition>]` | `KNNSC_PERIPHERY_<CONDITION>` | Condition mapping or suffixed key. |

### Binarization

| YAML key | Legacy name | Default / use |
| --- | --- | --- |
| `binarization_method` | `BIN_METHOD` | `consensus`. |
| `binarization_include_nodes` | `BIN_INCLUDE_NODES` | Additional nodes retained when HVG filtering is enabled; empty by default. |
| `scboolseq_only_hvg` | `BIN_SCBOOLSEQ_ONLY_HVG` | `true`. |
| `scboolseq_openblas_threads` | `SCBOOLSEQ_OPENBLAS_THREADS` | `auto`. |
| `scboolseq_omp_threads` | `SCBOOLSEQ_OMP_THREADS` | `auto`. |
| `unimodal_quantile` | `UNIMODAL_QUANTILE` | `0.10`. |
| `zeroes_are_zeroes` | `ZEROES_ARE_ZEROES` | `true`. |
| `undefined_threshold` | `NANS_THRESHOLD` | `0.3`. |
| `bimodal_threshold` | `BIMODAL_THRESHOLD` | `0.7`. |
| `zero_inflated_threshold` | `ZEROINF_THRESHOLD` | `0.7`. |
| `unimodal_threshold` | `UNIMODAL_THRESHOLD` | `0.7`. |
| `binarization_dea_only_hvg` | `BIN_DEA_ONLY_HVG` | `true`. |
| `binarization_logfc` | `BIN_LOGFC` | `0.5`. |
| `binarization_correction` | `BIN_CORRECTION` | `benjamini-hochberg`. |
| `binarization_alpha` | `BIN_ALPHA` | `0.05`. |

### Boolean inference

| YAML key | Legacy name | Default / use |
| --- | --- | --- |
| `prior_knowledge` | `PRIOR_KNOWLEDGE` | `collectri`. |
| `geneinfo_version` | `GENEINFO_VERSION` | `bundled`. |
| `omnipath_version` | `OMNIPATH_VERSION` | `latest`. |
| `hcop_version` | `HCOP_VERSION` | `bundled`. |
| `dorothea_api` | `DOROTHEA_API` | `modern`. |
| `dorothea_compatibility` | `DOROTHEA_COMPATIBILITY` | `true`. |
| `dorothea_levels` | `DOROTHEA_LEVELS` | `[A, B, C]`. |
| `max_clauses` | `MAX_CLAUSES` | `8`. |
| `clause_continuation_soft` | `CLAUSE_CONTINUATION_SOFT` | `false`. |
| `clause_continuation_relaxed` | `CLAUSE_CONTINUATION_RELAXED` | `true`. |
| `clause_continuation_seed` | `CLAUSE_CONTINUATION_SEED` | `true`. |
| `clause_continuation_lock` | `CLAUSE_CONTINUATION_LOCK` | `true`. |
| `clause_bound_patience` | `PATIENCE_CLAUSE_BOUND` | `30m`. |
| `domain_continuation_soft` | `DOMAIN_CONTINUATION_SOFT` | `false`. |
| `domain_continuation_relaxed` | `DOMAIN_CONTINUATION_RELAXED` | `true`. |
| `domain_continuation_seed` | `DOMAIN_CONTINUATION_SEED` | `true`. |
| `domain_continuation_lock` | `DOMAIN_CONTINUATION_LOCK` | `true`. |
| `domain_wave_patience` | `PATIENCE_DOMAIN_WAVE` | `5m`. |
| `minimum_domain_yield` | `MIN_DOMAIN_YIELD` | `0.10`. |
| `maximum_domain_refreshes` | `MAX_DOMAIN_REFRESHES` | `2`. |
| `clingo_threads` | `CLINGO_THREADS` | `1`. |
| `clingo_config_<stage>` | `CLINGO_CONFIG_<STAGE>` | Named configuration or file. |
| `clingo_mode_<stage>` | `CLINGO_MODE_<STAGE>` | Stage-dependent. |
| `clingo_strategy_<stage>` | `CLINGO_STRATEGY_<STAGE>` | Stage-dependent. |
| `timeout_<stage>` | `TIMEOUT_<STAGE>` | Stage-dependent duration. |
| `clingo_mode_min` | `CLINGO_MODE_MIN` | `optN`. |
| `minimize_self_loops_constants` | `MIN_SELF_LOOP_CONSTS` | `true`. |
| `minimize_self_loops_inference` | `MIN_SELF_LOOP_INFER` | `true`. |
| `configuration_formats` | `CONFIG_FORMATS` | `[csv]`. |
| `graph_formats` | `GRAPH_FORMATS` | `[dot]`. |
| `inference_limit` | `INFER_LIMIT` | `null`; enumerate all. |

The stage placeholder is one of `soft`, `consts`, `relaxed`, `seed`, or
`lock`. Clause and domain continuation switches do not apply to `consts`.

## Legacy projects

Projects containing `.scbolt` with `PARAMS=params.mk`, or projects selected
with `--params=<file>`, remain readable and are not rewritten. A legacy project
can be migrated by translating its Make parameters to `scbolt.yml`, retaining
`spec.yml` through the `spec_file` key, and changing the locator:

```text
CONFIG=scbolt.yml
```

The deprecated `dynamical_constraints` key in an existing `spec.yml` remains
accepted; new specifications use `constraints`. Keeping `params.mk` beside
`scbolt.yml` during validation is safe and makes rollback straightforward.
