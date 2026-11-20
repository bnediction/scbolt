# Command Reference

## Reading scBOLT Commands

A pipeline command names the result to build:

```bash
scbolt <module>
```

scBOLT resolves the active configuration, constructs the required dependency
graph, and executes missing upstream modules before the requested module. Users
therefore do not need to run every command in sequence.

| Command form | Question answered |
| --- | --- |
| `scbolt help` | Which commands and modules exist? |
| `scbolt <module> help` | What does this module consume, produce, and configure? |
| `scbolt config <module>` | Which effective settings will this module use? |
| `scbolt check <module>` | Is the required input, runtime, and configuration valid? |
| `scbolt dry-run <module>` | Which module commands would be executed? |
| `scbolt <module>` | Build the module and its missing dependencies. |
| `scbolt progress <module>` | Which required modules are done, stale, untracked, or pending? |

For example, a normal first execution can remain short:

```bash
scbolt check bn-submin
scbolt dry-run bn-submin
scbolt bn-submin
```

Run individual upstream modules when their intermediate outputs need inspection
or a biological decision is required.

## Workflow at a Glance

| Stage | Main command | Alternative or supporting commands | User role |
| --- | --- | --- | --- |
| Data acquisition | Selected from the configured input route | `load-fastq`, `load-matrix` | Select accessions or local files. |
| Alignment and counting | `alignment` | `star`, `cellranger`, `qc`, `velocyto` | Select an alignment method when starting from FASTQ. |
| Preprocessing | `normalization` | `filtering` | Inspect quality control and tune dataset-specific thresholds when required. |
| Population identification | `clustering` | `dea`, `scoring`, `goea`, `annotation` | Interpret clusters and assign biological labels. |
| Dynamics | As required by the selected macrostate strategy | `velocity`, `potency` | Inspect whether inferred temporal information is biologically plausible. |
| Macrostate characterization | `macrostates` | `cotan`, `cellrank`, `stream`, `knnsc` | Select populations that represent the states to model. |
| State abstraction | `binarization` | `bin-cells`, `bin-macrostates`, `bin-dea`, `bin-consensus` | Inspect partial Boolean profiles and choose an appropriate strategy. |
| Model specification | `spec` | none | Define dynamical constraints and node contracts in `spec.yml`. |
| Gene selection | Triggered by final inference | `max-nodes-soft`, `max-consts`, `max-nodes-relaxed`, `max-nodes-seed`, `max-nodes-lock` | Set resource budgets and inspect retained domains or partial results. |
| BN inference | `bn-min`, `bn-submin`, or `bn-diverse` | none | Select the intended solution-space exploration. |

The macrostate and binarization stages require particular care. Their defaults
provide a runnable path, not a claim that one method is optimal for every
dataset.

## Input Routes

Input routes are mutually exclusive. A downstream target automatically starts
from the earliest configured route.

| Input available to the user | Parameter | Modules bypassed | First generated analysis |
| --- | --- | --- | --- |
| SRA/INSDC runs | `sra` | None | FASTQ retrieval, then alignment and counting |
| GEO Sample count matrices | `gsm` | FASTQ retrieval and alignment | Standardized count AnnData files |
| Local count AnnData files | `count-file` | Download, alignment, and counting | Filtering |
| Local macrostate AnnData files | `macrostate-file` | Upstream omics analysis and macrostate construction | Binarization |
| Local partial-binarization CSV | `binarization-file` | Omics analysis and binarization | Boolean specification |

A multi-condition route uses a mapping:

```yaml
conditions: [control, perturbation]

count-file:
  control: data/control.h5ad
  perturbation: data/perturbation.h5ad
```

Equivalent suffixed parameters such as `count-file-control` and
`count-file-perturbation` are accepted. See
[configuration.md](configuration.md) for validation, condition ordering, and
relative-path rules.

### Starting from Counts

Count files enter the ordinary preprocessing path:

```yaml
count-file:
  control: data/control-counts.h5ad
  perturbation: data/perturbation-counts.h5ad
```

Each accepted file contains `counts` in `layers`; `adata.X` is not used as a
fallback expression matrix.

```bash
scbolt check clustering
scbolt clustering
```

A later target, such as `bn-submin`, also starts from these files and builds
all configured downstream stages.

### Starting from Macrostates

A shared macrostate file or one file per condition can be configured:

```yaml
macrostate-file: data/macrostates.h5ad
```

The accepted AnnData object provides:

- `log-norm` in `layers`;
- `macrostate` in `obs`;
- `condition` in `obs` when one file represents several conditions;
- the configured `representation` in `obsm`;
- `counts` in `layers` when downstream HVG selection uses
  `bin-hvg-method: loess`.

Expression is read from these named layers; `adata.X` is not used as a
fallback. Validate the complete contract with:

```bash
scbolt check binarization
```

### Starting from a Binarization

```yaml
binarization-file: data/mstates-bin.csv
```

The file is a comma-separated table with macrostates as rows, genes as
columns, and the first column containing row identifiers. State entries are
`0`, `1`, or missing for an undefined value.

```bash
scbolt check spec
scbolt spec
```

This route is useful when state abstraction was performed externally but model
specification and inference remain managed by scBOLT.

## Selector Commands

Three commands select a method from configuration:

| Selector | Parameter | Methods |
| --- | --- | --- |
| `alignment` | `alignment-tool` | `star`, `cellranger` |
| `macrostates` | `macrostate-method` | `knnsc`, `cellrank`, `cotan`, `stream` |
| `binarization` | `binarization-method` | `scboolseq`, `dea`, `consensus` |

Use selector commands in ordinary workflows. Run a method command
directly to inspect or compare that branch without changing the conceptual
role of the selector.

## Utility Commands

| Command | Description |
| --- | --- |
| `init` | Create, update, show, or remove project configuration files. |
| `help` | Display global or command-specific help. |
| `version` | Display the installed release and source revision. |
| `config` | Display effective global or module-specific configuration. |
| `check` | Validate the selected target path, runtime, files, and metadata. |
| `dry-run` | Preview commands without executing them. |
| `progress` | Report configuration-aware workflow state. |
| `clean` | Remove cache, logs, stale outputs, or selected module outputs. |
| `install` | Install a runtime backend. |

See [utilities.md](utilities.md) for complete command behavior.

## Download Commands

| Command | Purpose | Normally triggered by |
| --- | --- | --- |
| `load-genome` | Download the reference genome required by raw-read workflows. | `star`, `cellranger`, or `velocyto` |
| `load-fastq` | Download reads declared through `sra`. | `alignment` |
| `load-matrix` | Download and standardize matrices declared through `gsm`. | `filtering` |
| `load-signatures` | Retrieve phenotype-related gene signatures. | `scoring` |
| `load-cc` | Retrieve cell-cycle markers. | Preprocessing that computes or corrects cell-cycle effects |
| `load-go` | Retrieve Gene Ontology resources. | `goea` |

Resource modules are scheduled only when the selected path uses them.

## Alignment and Counting

| Command | Purpose | Main result |
| --- | --- | --- |
| `alignment` | Run the method selected by `alignment-tool`. | Count matrices and alignment products |
| `star` | Align reads and count molecules with STARsolo. | STAR count and alignment products |
| `cellranger` | Align and count with Cell Ranger. | Cell Ranger count and alignment products |
| `qc` | Apply barcode and alignment quality-control rules. | Quality-controlled count inputs |
| `velocyto` | Quantify spliced and unspliced transcripts. | Layers used by RNA-velocity analysis |

These commands are relevant only to raw-read workflows. Local counts and GEO
matrices bypass them.

## Preprocessing

| Command | Purpose | Main result |
| --- | --- | --- |
| `filtering` | Compute quality metrics and filter low-quality cells and genes. | Filtered AnnData files for each condition |
| `normalization` | Normalize counts and optionally correct cell-cycle-associated variation. | Normalized expression layers |

Filtering thresholds are dataset-dependent. Inspect generated quality-control
plots before treating default values as final analytical choices.

## Clustering, Integration, and Annotation

| Command | Purpose | Role |
| --- | --- | --- |
| `clustering` | Integrate configured conditions, compute reduced representations, construct neighbours, and identify clusters. | Main automated population-identification stage |
| `dea` | Identify cluster-associated upregulated genes. | Annotation support |
| `scoring` | Test cluster marker overlap with phenotype-related signatures. | Annotation support |
| `goea` | Test Gene Ontology enrichment among cluster markers. | Annotation support |
| `annotation` | Assign configured biological labels to clusters. | User-guided transition from clusters to named populations |

The decision-support commands do not replace biological interpretation.
`annotation` consumes the labels selected by the user through `labels`.

## Trajectory Commands

| Command | Purpose | Main inputs |
| --- | --- | --- |
| `velocity` | Estimate condition-specific RNA velocity. | Spliced and unspliced counts from `velocyto` |
| `potency` | Estimate condition-specific differentiation potential. | Raw expression values and annotated populations |

Trajectory outputs can guide macrostate selection and the relationships later
encoded in `spec.yml`. Inspect them before translating their interpretation
into dynamical constraints.

## Macrostate Commands

`macrostates` runs the method selected by `macrostate-method`.

| Command | Information used | Practical role |
| --- | --- | --- |
| `knnsc` | Local neighbourhood topology in a configured embedding | Refine annotated clusters into central or peripheral condition-specific populations. |
| `cellrank` | Velocity, potency, and transcriptional similarity kernels | Identify populations through transition structure when those signals are informative. |
| `cotan` | Co-expression structure inferred from zero-count patterns | Characterize populations in sparse count data. |
| `stream` | An elastic principal graph in a reduced embedding | Characterize populations along clear branching structures. |
| `macrostates` | The selected method above | Produce the canonical macrostate input for binarization. |

Method-specific requirements and effective values are available through, for
example:

```bash
scbolt knnsc help
scbolt config knnsc
scbolt check knnsc
```

## Binarization Commands

Binarization creates partial Boolean profiles. A value of `0` or `1`
describes low or high transcript abundance relative to the selected abstraction
procedure; it is not a direct measurement of protein activity. Undefined
values remain unconstrained during model inference.

| Command | Strategy | Main result |
| --- | --- | --- |
| `bin-cells` | Apply scBoolSeq at single-cell resolution. | Partial cell-level Boolean assignments |
| `bin-macrostates` | Aggregate scBoolSeq assignments by voting within each macrostate. | scBoolSeq macrostate profiles |
| `bin-dea` | Contrast each macrostate against the remaining cells. | DEA-based macrostate profiles |
| `bin-consensus` | Combine non-contradictory scBoolSeq and DEA assignments. | Conservative consensus profiles |
| `binarization` | Select `scboolseq`, `dea`, or `consensus`. | Canonical input for `spec` |

The two component methods capture different information and can react
differently to sparse expression. Inspect the generated assignments before
writing dynamical constraints.

## Boolean Specification

The `spec` command combines the selected binarization, regulatory prior, and
public `spec.yml` into inference-ready BoNesis inputs.

| `spec.yml` key | Purpose |
| --- | --- |
| `constraints` | Declare observations, configurations, attractor properties, and trajectory constraints. |
| `important-nodes` | Give selected nodes the first priority in the gene-selection objective. |
| `mandatory-nodes` | Require nodes in every retained domain. |
| `forbidden-nodes` | Exclude nodes before gene selection. |

```yaml
constraints:
  - control_initial = ~obs('control_initial')
  - control_terminal = fixed(~obs('control_terminal'))
  - control_initial >= control_terminal

important-nodes: [Rara, Cebpa, Spi1]
mandatory-nodes: []
forbidden-nodes: []
```

Run syntax and input checks before a long solve:

```bash
scbolt check spec
scbolt spec
```

Constraint formulation remains a biological modelling decision. scBOLT
validates and executes the specification but does not infer the intended
relationships automatically.

## Gene-Selection Commands

Final inference normally triggers gene selection automatically. Direct commands
are useful for inspecting retained domains, testing resource settings, or
resuming an expensive selection stage.

| Command | Active constraint level | Role |
| --- | --- | --- |
| `max-nodes-soft` | Soft | Maximize jointly satisfiable components under the least expensive constraints. |
| `max-consts` | Configured by `strong-constants-scope` | Remove one optimized set of jointly strong constants at the selected scope. |
| `max-nodes-relaxed` | Soft and intermediate | Introduce non-reachability-related constraints. |
| `max-nodes-seed` | Complete specification | Obtain or improve a bounded-time complete-constraint solution. |
| `max-nodes-lock` | Complete specification | Resume from the seed domain while protecting its retained nodes. |

The order of the single `max-consts` pass depends on
`strong-constants-scope`:

| Scope | Position |
| --- | --- |
| `soft` | After `max-nodes-soft` |
| `relaxed` | After `max-nodes-relaxed` |
| `full` | After `max-nodes-lock` |
| `none` | Disabled |

Gene selection maximizes retained important nodes first, then total retained
nodes. A certified optimum applies to the exact domain, constraints, clause
bound, and objective vector solved by that module. Interrupted stages retain
an explicitly uncertified incumbent when one exists.

See [solver.md](solver.md) before modifying continuation policies, solver
strategies, patience, or timeouts.

## Boolean Network Inference

| Command | Solution-space criterion | Use it to |
| --- | --- | --- |
| `bn-min` | Minimum possible number of signed regulatory interactions | Enumerate edge-minimum compatible BNs. |
| `bn-submin` | No proper subset of a network's signed interactions remains compatible | Enumerate irreducible influence structures. |
| `bn-diverse` | Diversity-oriented heuristics over clauses and constant assignments | Sample distinct compatible BNs without claiming edge-minimum or subset-minimum status. |

For `bn-diverse`, diversity refers to the explored logical structures. It does
not establish a minimum number of interactions or subset minimality.

Each inferred network is exported in `.bnet` format together with compatible
macrostate completions and configured graph representations. The number of
requested solutions is controlled by `inference-limit`.

During large `bn-submin` enumerations, scBOLT monitors the configured `memory`
budget, limits concurrent workers to `jobs`, and checkpoints completed
solutions so an interrupted enumeration can be resumed.

```bash
scbolt bn-submin --inference-limit=1000
```

The option above is a temporary override. Put `inference-limit: 1000` in
`scbolt.yml` to make it part of the recorded project configuration.

## Conditions and References

`conditions` defines the biological experiments represented by the project.
`--references` restricts reference-level work for one invocation:

```bash
scbolt filtering --references=control
scbolt filtering --references="control perturbation"
```

This option does not redefine the project's conditions. Downstream integrated
modules may still require all configured inputs.

## Temporary Overrides

Every configuration parameter can be overridden for one command:

```bash
scbolt clustering --neighbors=30
scbolt bn-submin --max-clauses=6 --timeout-seed=3h
```

Overrides are recorded with the resulting run but do not edit `scbolt.yml`.
Persistent analytical choices belong in the YAML file so that a plain
`scbolt <module>` reproduces them.

## Reusing and Rebuilding Outputs

| Need | Command |
| --- | --- |
| Recompute a module and everything downstream | `scbolt <target> --reset-target=<module>` |
| Accept all outputs of one module | `scbolt <target> --trust-target=<module>` |
| Accept every known output currently present | `scbolt <target> --trust-existing` |
| Accept one specific workflow file | `scbolt <target> --old-file=<file>` |
| Remove stale tracked outputs | `scbolt clean --stale` |

`--reset-target` takes priority over trust controls. See
[rebuilds.md](rebuilds.md) for exact propagation and validation rules.

## Main Output Locations

Paths are relative to `project-dir`.

| Output family | Default directory |
| --- | --- |
| Reference-level and integrated omics objects | `omics/` |
| Cell and macrostate binarizations | `bin/` |
| Compiled Boolean specification | `infer/spec/` |
| Gene-selection domains and witnesses | `infer/genes/` |
| Inferred Boolean networks and ensemble summaries | `infer/bn/` |
| Persisted command logs | `logs/` |

The `infer/` prefix is controlled by `inference-dir` and may therefore be
renamed in the project configuration.

Exact paths are printed by `scbolt <module> help`.
