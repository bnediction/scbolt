# Project configuration

scBOLT projects use one locator and two public YAML files:

- a project locator selecting the active project configuration
  (file: `.scbolt`);
- a project configuration file storing scientific configuration and input
  routes (default file: `scbolt.yml`);
- a Boolean specification file storing Boolean constraints and node contracts
  (default file: `spec.yml`).

## Project initialization

Run `scbolt init` from the project directory to create `.scbolt` and the
default YAML files when they are missing. Its general form is:

```sh
scbolt init [<file>] [--<parameter>=<value> ...]
```

The optional file becomes the active project configuration. Initial values
such as `--organism=mouse` populate a newly created configuration file; they
do not modify an existing file. Display the active configuration selected for
the current directory with:

```sh
scbolt init --show
```

Use `--config=<file>` to select another configuration for a single command.

For every other command, scBOLT searches for `.scbolt` in the current
directory and then each parent directory. A project can therefore be used from
its root or any descendant directory; the nearest locator is selected.

## Resolution and defaults

Configuration values use this precedence, from highest to lowest:

1. command-line overrides;
2. the active project configuration file;
3. built-in scBOLT defaults.

The execution backend has one extra fallback: when neither the command line
nor the project configuration selects it, scBOLT uses the backend chosen
during installation.

A `null` value leaves a parameter unset. Validation fails when the selected
target requires that parameter.

Relative YAML paths are resolved from the directory containing `.scbolt`, or
from the YAML file's directory when no locator is active. Relative command-line
paths are resolved from the launch directory.

Parameter names use `kebab-case`, like command-line options. Equivalent
`snake_case` spellings, unknown or duplicate parameters, and incorrect value
types are rejected.

## Shape

The configuration is flat:

```yaml
organism: mouse
conditions: [control, perturbation]
gsm:
  control: GSM000001
  perturbation: GSM000002
labels: [initial, terminal]

macrostate-method: knnsc
spec-file: spec.yml
```

Nested workflow sections such as `clustering: {neighbors: 14}` are not
accepted.

## Conditions

`gsm`, `sra`, `count-file`, `macrostate-file`, `knnsc-centrality`, and
`knnsc-periphery` accept either mappings or parameter names suffixed by the
condition name:

```yaml
conditions: [control, perturbation]

sra:
  control: [SRR_control_1, SRR_control_2]
  perturbation: [SRR_perturbation_1, SRR_perturbation_2]
```

The equivalent flat form is:

```yaml
conditions: [control, perturbation]

sra-control: [SRR_control_1, SRR_control_2]
sra-perturbation: [SRR_perturbation_1, SRR_perturbation_2]
```

`conditions` may be omitted when named conditions are present; scBOLT then
uses their order of first appearance. When declared, it fixes the order and
unlisted conditions are rejected. For an unnamed single-condition project, use
`gsm` or `sra` without condition mappings or suffixes.

A single `macrostate-file` can contain macrostates for all conditions.

Mappings and suffixed parameters can be combined, but duplicate definitions of
the same parameter and condition are accepted only when their values match.

Condition names start with a letter or number and may contain letters, numbers,
hyphens, and underscores. `integrated` and `unique` are reserved.

Command-line overrides use the equivalent dash-separated suffix, for example
`--sra-control="SRR_control_1 SRR_control_2"`.

## Inference specification

The file selected by `spec-file` (default: `spec.yml`) contains four inference
contracts:

| Key | Meaning |
| --- | --- |
| `constraints` | BoNesis observations and dynamical constraints. |
| `important-nodes` | Nodes prioritized by gene selection. |
| `mandatory-nodes` | Nodes retained by every selected domain. |
| `forbidden-nodes` | Nodes removed before gene selection. |

```yaml
constraints:
  - control_initial = ~obs('control_initial')
  - control_terminal = fixed(~obs('control_terminal'))
  - perturbation_initial = ~obs('perturbation_initial')
  - perturbation_terminal = fixed(~obs('perturbation_terminal'))
  - control_initial >= control_terminal
  - perturbation_initial >= perturbation_terminal
  - control_initial / perturbation_terminal
  - perturbation_initial / control_terminal

important-nodes: [GeneA, GeneB, GeneC]
mandatory-nodes: []
forbidden-nodes: []
```

To keep an alternative hypothesis separate, select another inference directory
and specification:

```yaml
inference-dir: infer-alternative
spec-file: spec-alternative.yml
```

Run it with `scbolt bn-submin --config=scbolt-alternative.yml`. Modifying the
selected specification rebuilds `spec`.

Only a relative subdirectory of `project-dir` is accepted for `inference-dir`;
absolute paths and parent traversal with `..` are rejected.

## Parameter reference

### Project and runtime

| Parameter | Use | Default |
| --- | --- | --- |
| `backend` | Execution backend (`conda`, `mamba`, `micromamba`, `docker`). | `conda` |
| `container-args` | Extra `docker run` arguments; defaults to the current host user. | Automatic |
| `container-mounts` | Extra host paths mounted at the same absolute path. | `[]` |
| `project-dir` | Generated-output directory. | `project` |
| `inference-dir` | Inference output subdirectory within the project directory. | `infer` |
| `resources-dir` | External-resource directory. | `resources` |
| `memory` | Memory budget; integers are interpreted as GB. | `50GB` |
| `jobs` | Maximum number of parallel workflow jobs. | `16` |
| `seed` | Shared random seed. | `10` |
| `openblas-core-type` | OpenBLAS profile; automatic by default if `HASWELL` is unsupported. | `HASWELL` |
| `organism` | Organism for gene resources (`mouse`, `human`, `escherichia-coli`). | `null` |
| `conditions` | Ordered conditions; inferred when omitted, or `[]` for an unnamed project. | Automatic |
| `references` | References to process, optionally including `integrated`. | All |
| `gsm[-<condition>]` | GEO sample containing the count matrix. | `null` |
| `sra[-<condition>]` | SRA run accessions to download. | `null` |
| `count-file[-<condition>]` | External AnnData file containing layer `counts`. | `null` |
| `macrostate-file[-<condition>]` | Shared or per-condition macrostate AnnData with named expression layers. | `null` |
| `binarization-file` | External binarization CSV file. | `null` |
| `representation` | Embedding key (`X_umap`, `X_tsne`, `X_se`). | `X_umap` |
| `label-column` | Cell annotation column. | `label` |
| `labels` | Biological labels assigned to clusters in cluster order. | `[]` |
| `spec-file` | Boolean inference specification file. | `spec.yml` |
| `old-files` | Existing workflow files to trust without rebuilding. | `[]` |

Runs are always recorded in the project log directory.

### External data and alignment

| Parameter | Use | Default |
| --- | --- | --- |
| `genome-url` | Genome reference archive URL. | By organism |
| `repeat-masker-url` | RepeatMasker annotation table URL. | By organism |
| `gene-ontology-url` | Current Gene Ontology slim URL for the organism. | By organism |
| `alignment-tool` | Alignment and counting backend (`cellranger`, `star`). | `star` |
| `star-barcode-length` | Cell-barcode length used by STAR. | `16` |
| `star-umi-length` | UMI length used by STAR. | `10` |
| `star-whitelist` | Barcode whitelist file used by STAR. | `null` |
| `star-barcode-filter` | Barcode selection method (`auto`, `threshold`, `top`). | `auto` |
| `star-min-umi` | Minimum UMI count for threshold mode. | `null` |
| `star-top-barcodes` | Number of top barcodes. | `null` |

### Preprocessing and clustering

| Parameter | Use | Default |
| --- | --- | --- |
| `gene-dropout` | Exclude genes undetected in more than this fraction of cells. | `0.999` |
| `gene-expression` | Keep genes expressed in a number of cells within this range. | `[0, inf]` |
| `gene-counts` | Keep genes whose total counts fall within this range. | `[0, inf]` |
| `cell-dropout` | Exclude cells with more than this fraction of undetected genes. | `1` |
| `cell-expression` | Keep cells whose number of detected genes falls within this range. | `[0, inf]` |
| `cell-reads` | Keep cells whose total reads fall within this range. | `[0, inf]` |
| `mad-deviation` | Exclude cells outside lower and upper MAD cutoffs around median log-reads. | `[2, 2]` |
| `consistent-mad` | Use Gaussian-consistent MAD scaling for cell filtering. | `true` |
| `mitochondrial-fraction` | Exclude cells at or above this mitochondrial count fraction. | `0.05` |
| `cell-cycle-correction` | Regress out cell-cycle scores (mouse). | `true` |
| `omics-hvg-method` | HVG method for omics analysis (`loess`, `binning`). | `loess` |
| `omics-hvg-top` | Number of top HVGs for omics analysis; `null` estimates it automatically. | `null` |
| `omics-hvg-span` | LOESS smoothing fraction. | `0.3` |
| `omics-hvg-bins` | Mean-expression bins for omics HVG selection. | `20` |
| `bin-hvg-method` | HVG method for binarization (`loess`, `binning`). | `binning` |
| `bin-hvg-top` | Number of top HVGs for binarization; `null` estimates it automatically. | `null` |
| `bin-hvg-span` | LOESS smoothing fraction. | `0.3` |
| `bin-hvg-bins` | Mean-expression bins for binarization HVG selection. | `20` |
| `integration` | Multi-condition integration method (`bbknn`, `scanorama`, `ingest`). | `bbknn` |
| `pca-dimensions` | Number of PCA components. | `50` |
| `embedding-dimensions` | Number of embedding dimensions. | `2` |
| `centered-pca` | Center variables before PCA. | `true` |
| `pca-only-hvg` | Restrict PCA projection to HVGs. | `true` |
| `neighbors` | Number of nearest neighbors. | `20` |
| `metric` | Distance metric for neighbors and t-SNE. | `euclidean` |
| `resolution` | Leiden clustering resolution. | `0.4` |
| `umap-min-dist` | UMAP minimum distance. | `0.1` |
| `umap-spread` | UMAP spread. | `1` |
| `embedding-iterations` | Embedding optimization iterations. | `500` |

### Differential analysis, velocity, and potency

| Parameter | Use | Default |
| --- | --- | --- |
| `dea-method` | Statistical test for marker differential expression. | `wilcoxon` |
| `logfc` | Minimum absolute log2 fold-change. | `0.25` |
| `correction` | P-value correction method (`benjamini-hochberg`, `bonferroni`). | `bonferroni` |
| `alpha` | Adjusted p-value threshold. | `0.05` |
| `moment-dimensions` | PCA components for velocity moments. | `15` |
| `velocity-only-hvg` | Restrict RNA velocity to HVGs. | `true` |
| `velocity-mode` | scVelo mode (`deterministic`, `stochastic`, `dynamical`). | `dynamical` |
| `potency-batch-size` | Cells processed per potency batch. | `20000` |
| `potency-smoothing-batch-size` | Cells sampled for smoothing. | `1000` |

### Macrostates

| Parameter | Use | Default |
| --- | --- | --- |
| `macrostate-size` | Target cells per macrostate. | `100` |
| `macrostate-method` | Macrostate estimation method (`knnsc`, `stream`, `cellrank`, `cotan`). | `cellrank` |
| `cotan-method` | COTAN method (`classic`, `soft-merging`, `strong-merging`). | `strong-merging` |
| `cotan-only-hvg` | Restrict COTAN to HVGs. | `false` |
| `cotan-max-iterations` | Maximum COTAN merging iterations. | `25` |
| `cellrank-method` | Terminal-state selection method. | `stability` |
| `cellrank-states` | Number of CellRank macrostates. | `10` |
| `cellrank-initial-states` | Number of initial macrostates. | `5` |
| `cellrank-terminal-states` | Number of terminal states for `top_n`. | `5` |
| `cellrank-stability` | Minimum terminal-state stability. | `0.96` |
| `cellrank-alpha` | Eigengap weighting parameter. | `1.0` |
| `stream-clustering-method` | STREAM seed clustering method (`kmeans`, `ap`, `sc`). | `kmeans` |
| `stream-cluster-number` | Number of STREAM seed clusters. | `6` |
| `stream-alpha` | STREAM branch penalty. | `0.03` |
| `stream-mu` | STREAM harmonic embedding penalty. | `0.05` |
| `stream-lambda` | STREAM edge-length penalty. | `0.05` |
| `stream-extend` | Extend STREAM leaf nodes. | `true` |
| `stream-extend-mode` | STREAM extension mode. | `QuantDists` |
| `stream-extend-parameter` | STREAM extension parameter. | `0.8` |
| `stream-prune` | Prune STREAM trivial branches. | `false` |
| `stream-collapse-parameter` | STREAM collapse parameter. | `false` |
| `knnsc-embedding` | Embedding key for KNNSC distances. | `X_umap` |
| `knnsc-dimensions` | Embedding dimensions for distances; `null` uses all dimensions. | `null` |
| `knnsc-neighbors` | Number of KNN graph neighbors. | `20` |
| `knnsc-min-cluster-size` | Minimum label size for KNNSC candidates. | `20` |
| `knnsc-centrality[-<condition>]` | Labels selected near their own barycenter. | `[]` |
| `knnsc-periphery[-<condition>]` | Labels selected far from other barycenters. | `[]` |

### Binarization

| Parameter | Use | Default |
| --- | --- | --- |
| `binarization-method` | Macrostate binarization method (`scboolseq`, `dea`, `consensus`). | `consensus` |
| `bin-include-nodes` | Additional nodes retained when binarization uses only HVGs. | `[]` |
| `scboolseq-only-hvg` | Restrict scBoolSeq to HVGs. | `true` |
| `scboolseq-openblas-threads` | OpenBLAS threads for scBoolSeq (`auto` or a positive integer). | `auto` |
| `scboolseq-omp-threads` | OpenMP threads for scBoolSeq (`auto` or a positive integer). | `auto` |
| `unimodal-quantile` | Quantile threshold for unimodal genes. | `0.10` |
| `zeroes-are-zeroes` | Set zero-inflated zeroes to 0. | `true` |
| `undefined-threshold` | Maximum undefined fraction. | `0.3` |
| `bimodal-threshold` | Vote threshold for bimodal genes. | `0.7` |
| `zero-inflated-threshold` | Zero-inflated vote threshold. | `0.7` |
| `unimodal-threshold` | Unimodal vote threshold. | `0.7` |
| `binarization-dea-only-hvg` | Restrict DEA binarization to HVGs. | `true` |
| `binarization-logfc` | Minimum absolute log2 fold-change. | `0.5` |
| `binarization-correction` | P-value correction method (`benjamini-hochberg`, `bonferroni`). | `benjamini-hochberg` |
| `binarization-alpha` | Adjusted p-value threshold. | `0.05` |

### Boolean inference

| Parameter | Use | Default |
| --- | --- | --- |
| `prior-knowledge` | Prior regulatory resource (`collectri`, `dorothea`, or a file). | `collectri` |
| `geneinfo-version` | NCBI gene_info source (`bundled`, `latest`, or a file). | `bundled` |
| `omnipath-version` | OmniPath resource version (`latest` or a date). | `latest` |
| `hcop-version` | HCOP orthology source (`bundled`, `latest`, or a file). | `bundled` |
| `dorothea-api` | DoRothEA API source (`modern`, `legacy`). | `modern` |
| `dorothea-compatibility` | Reproduce decoupler DoRothEA deduplication. | `true` |
| `dorothea-levels` | DoRothEA confidence levels (`A`, `B`, `C`, `D`, or a combination). | `[A, B, C]` |
| `max-clauses` | Maximum OR-joined conjunctive terms per Boolean update function. | `8` |
| `bounded-nonreach` | Non-reachability certificate iterations; `null` uses the complete bound. | `null` |
| `strong-constants-scope` | Strong-constant scope and placement (`soft`, `relaxed`, `full`, `none`). | `soft` |
| `clause-continuation-soft` | Progressively increase the soft clause bound up to `max-clauses`. | `false` |
| `clause-continuation-relaxed` | Progressively increase the relaxed clause bound up to `max-clauses`. | `true` |
| `clause-continuation-seed` | Progressively increase the seed clause bound up to `max-clauses`. | `true` |
| `clause-continuation-lock` | Progressively increase the lock clause bound up to `max-clauses`. | `true` |
| `clause-bound-patience` | Maximum time without objective improvement at intermediate clause bounds. | `30m` |
| `domain-continuation-soft` | Search soft subdomains and expand the best witness. | `false` |
| `domain-continuation-relaxed` | Search relaxed subdomains and expand the best witness. | `true` |
| `domain-continuation-seed` | Search complete-constraint subdomains and expand the best witness. | `true` |
| `domain-continuation-lock` | Expand the seed witness toward the complete seed input domain. | `true` |
| `domain-wave-patience` | Maximum stagnation time per wave for soft, relaxed, and seed selection. | `5m` |
| `domain-wave-patience-lock` | Maximum stagnation time per wave for lock selection. | `10m` |
| `minimum-domain-yield` | Minimum cumulative retained-node gain per node added during expansion. | `0.10` |
| `maximum-domain-refreshes` | Maximum constant-size refreshes per domain size. | `1` |
| `clingo-threads` | Stage-level solver threads; domain candidates always use one. | `1` |
| `clingo-config-<stage>` | Preset or file controlling how Clingo solves a problem. | `auto` |
| `clingo-mode-<stage>` | Clingo optimization mode (`opt`, `optN`, `ignore`). | By stage |
| `clingo-strategy-<stage>` | Clingo optimization algorithm (`bb,*`, `usc,*`). | By stage |
| `timeout-<stage>` | Total stage time limit; `null` disables it. | By stage |
| `minimize-self-loops-constants` | Minimize one-node feedbacks during strong-constant selection. | `true` |
| `minimize-self-loops-inference` | Minimize one-node feedbacks during BN inference. | `true` |
| `configuration-formats` | Configuration export formats (`csv`, `cfg`, `json`, or a combination). | `[csv]` |
| `graph-formats` | Graphviz layouts to export. | `[dot]` |
| `inference-limit` | Maximum number of inferred BNs; `null` or `0` enumerates all. | `null` |

The stage placeholder is one of `soft`, `consts`, `relaxed`, `seed`, or
`lock`. Clause and domain continuation switches do not apply to `consts`.
