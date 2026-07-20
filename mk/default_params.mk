# Path resolution policy:
# - paths defined in params.mk are resolved relative to the directory
#   containing params.mk;
# - paths passed on the command line are resolved relative to the
#   directory from which make is launched;
# - RESOURCES_DIR defaults to resources relative to the active scBOLT project
#   file when available, otherwise relative to the active parameter file.
$(eval PARAMS ?= params.mk)  # user parameter file (resolved relative to scBOLT root)

# Configuration policy:
# - PARAMS can be overridden here to point to another parameter file
# - all other parameters must be defined in the file specified by PARAMS
# - target-specific parameters may stay undefined until their target is requested
# - Boolean parameters use true or false
# - min/max ranges use two values: <min> <max>; use inf/-inf for open bounds

## COMPUTING RESOURCES ##
# MEMORY accepts an integer in GB, or a value with unit KB, MB, GB, TB, KiB,
# MiB, GiB, or TiB. LOGGING=true persists command output in log files.
MEMORY ?= 50
JOBS ?= 16
SEED ?= 10
LOGGING ?= true

## RUNTIME ##
# BACKEND values: conda, mamba, micromamba, docker.
# Docker mode uses one scBOLT image containing all scbolt-* micromamba environments.
ifeq ($(origin BACKEND),undefined)
$(eval BACKEND := $(if $(strip $(SCBOLT_DEFAULT_BACKEND)),$(SCBOLT_DEFAULT_BACKEND),conda)) # backend used by Make rules
endif
$(eval SCBOLT_IMAGE ?= ghcr.io/bnediction/scbolt:latest) # Docker image for BACKEND=docker
$(eval SCBOLT_CONTAINER_ENGINE ?= docker)   # container engine used for Docker backend
$(eval SCBOLT_CONTAINER_ARGS ?= --user $(shell id -u):$(shell id -g)) # extra arguments passed to docker run
$(eval SCBOLT_CONTAINER_MOUNTS ?=)          # extra host paths mounted at the same path

## INFORMATION ##
# ORGANISM values: mouse, human, escherichia-coli.
# Empty CONDITIONS is treated as one unnamed mono-condition project.
$(eval ORGANISM ?=)                         # organism used for gene resources
$(eval CONDITIONS ?=)                       # experimental conditions
$(eval PROJECT_DIR ?= project)              # project directory
# Resource directory. In params.mk, relative paths are resolved relative to
# params.mk; on the command line, they are resolved relative to launch_dir.
# When omitted, RESOURCES_DIR defaults to resources relative to the active
# scBOLT project file when available, otherwise relative to the active
# parameter file.
$(eval RESOURCES_DIR ?= resources)          # reference/resource directory

## URLS ##
genome_url ?=
repeat_msk_url ?=
go_organism_url ?= https://current.geneontology.org/ontology/subsets/goslim_$(ORGANISM).obo

## ALIGNMENT/COUNTING ##
# ALIGNMENT_TOOL values: cellranger, star.
# STAR uses STAR 2.7.1a to reuse Cell Ranger reference indices.
# It assumes 10x-style reads: R1 stores cell barcode/UMI, R2 stores cDNA.
# STAR_BARCODE_FILTER values: auto, threshold, top.
# auto estimates a knee point; threshold requires STAR_MIN_UMI; top requires
# STAR_TOP_BARCODES.
$(eval ALIGNMENT_TOOL ?= star)            # alignment/counting backend
$(eval STAR_CB_LEN ?= 16)                  # cell-barcode length
$(eval STAR_UMI_LEN ?= 10)                 # UMI length
$(eval STAR_WHITELIST ?=)                  # barcode whitelist file
$(eval STAR_BARCODE_FILTER ?= auto)        # barcode filtering method
$(eval STAR_MIN_UMI ?=)                    # optional minimum UMI count
$(eval STAR_TOP_BARCODES ?=)               # optional number of top barcodes

## EXTRA PARAMETERS ##
# Useful when starting from user-provided or precomputed upstream analyses.
# Input routes are mutually exclusive. Define only one of SRA/GSM for an
# unnamed mono-condition project, SRA_<CONDITION>/GSM_<CONDITION> for named
# conditions, COUNT_FILES, MACROSTATE_FILES, or BINARIZATION_FILE.
# COUNT_FILES skips alignment/counting and restarts from one count AnnData file
# per condition, ordered like CONDITIONS. Files must contain layer 'counts';
# adata.X is not used as a fallback expression matrix.
# BINARIZATION_FILE overrides the binarization target when set.
# MACROSTATE_FILES skips macrostate inference and restarts from either one
# multi-condition AnnData file or one AnnData file per condition, ordered like
# CONDITIONS. Files must contain layer 'log-norm', obs 'macrostate', and obsm
# REPRESENTATION. adata.X is not used as a fallback expression matrix. A single
# multi-condition file must also contain obs 'condition'.
# If BIN_HVG_METHOD=loess is used downstream, macrostate files must also
# contain layer 'counts'.
# REPRESENTATION must name an embedding in adata.obsm, usually created by clustering.
# LABEL_COL is created by annotation, copied per condition, and used by
# downstream macrostate methods.
$(eval COUNT_FILES ?=)                     # precomputed count AnnData files
$(eval BINARIZATION_FILE ?=)                # precomputed macrostate binarization
$(eval MACROSTATE_FILES ?=)                 # precomputed macrostate AnnData files
$(eval REPRESENTATION ?= X_umap)            # embedding key in adata.obsm
$(eval LABEL_COL ?= label)                  # annotated cell-type column in adata.obs
$(eval OLD_FILES ?=)                        # trusted existing scBOLT DAG files

## FILTERING ##
# Dropout and MT thresholds are fractions in [0,1].
# *_EXPRESSION, *_COUNTS, and *_READS are non-negative min/max ranges.
# MAD_DEVIATION defines lower and upper factors for discarding cells whose
# log-total reads deviate from the median by more than the MAD-scaled threshold.
$(eval GENE_DROPOUT ?= 0.999)               # maximum gene dropout fraction
$(eval GENE_EXPRESSION ?= 0 inf)            # min/max cells expressing a gene
$(eval GENE_COUNTS ?= 0 inf)                # min/max total gene counts
$(eval CELL_DROPOUT ?= 1)                   # maximum cell dropout fraction
$(eval CELL_EXPRESSION ?= 0 inf)            # min/max expressed genes per cell
$(eval CELL_READS ?= 0 inf)                 # min/max total cell reads
$(eval MAD_DEVIATION ?= 2 2)                # lower/upper MAD factors around median log-total reads
$(eval CONSISTENT_MAD ?= true)              # use Gaussian-consistent MAD scaling
$(eval MT ?= 0.05)                          # maximum mitochondrial count fraction

## NORMALIZATION ##
# CC_CORRECTION=true is supported only for ORGANISM=mouse.
$(eval CC_CORRECTION ?= true)               # regress out cell-cycle effects

## CLUSTERING ##
# If ANALYSIS_HVG_TOP is empty, the number of HVGs is estimated automatically.
$(eval ANALYSIS_HVG_METHOD ?= loess)        # HVG method for analysis modules
$(eval ANALYSIS_HVG_TOP ?=)                 # top HVGs for analysis modules
$(eval ANALYSIS_HVG_SPAN ?= 0.3)            # cell fraction used by loess
$(eval ANALYSIS_HVG_BINS ?= 20)             # mean-expression bins for HVG selection
# INTEGRATION values: bbknn, scanorama, ingest.
$(eval INTEGRATION ?= bbknn)                # integration method
$(eval DIM_PCA ?= 50)                       # number of PCA components
$(eval DIM_EMBEDDING ?= 2)                  # number of embedding dimensions
$(eval CENTERED_PCA ?= true)                # center variables before PCA
$(eval NEIGHBORS ?= 20)                     # number of nearest neighbors
$(eval METRIC ?= euclidean)                 # neighbor/t-SNE distance metric
$(eval RESOLUTION ?= 0.4)                   # Leiden clustering resolution
$(eval MIN_DIST ?= 0.1)                     # UMAP minimum distance
$(eval SPREAD ?= 1)                         # UMAP spread
# Number of optimization iterations used by the embedding layout.
$(eval EMBEDDING_N_ITER ?= 500)
$(eval PCA_ONLY_HVG ?= true)                # use only HVGs for PCA projection

## DEA ##
# DEA_METHOD values: wilcoxon, welch, welch_overestimate.
# LOGFC is non-negative.
# CORRECTION values: benjamini-hochberg, bonferroni.
# ALPHA is an adjusted p-value threshold in [0,1].
$(eval DEA_METHOD ?= wilcoxon)             # statistical test for marker DEA
$(eval LOGFC ?= 0.25)                       # minimum absolute log2 fold-change
$(eval CORRECTION ?= bonferroni)            # p-value correction method
$(eval ALPHA ?= 0.05)                       # adjusted p-value threshold

## ANNOTATION ##
# LABEL must be defined before annotation; values map clusters 0..n to biological labels.

## VELOCITY ##
# SMM_MODE values: deterministic, stochastic, dynamical.
$(eval DIM_MOMENT ?= 15)                    # PCA components used to estimate moments
$(eval VELOCITY_ONLY_HVG ?= true)           # use only HVGs for RNA velocity
$(eval SMM_MODE ?= dynamical)               # scVelo mode

## POTENCY ##
# CytoTRACE supports ORGANISM=mouse or ORGANISM=human.
$(eval BATCH_SIZE ?= 20000)                 # cells processed per batch
$(eval SMOOTH_BATCH_SIZE ?= 1000)           # cells subsampled for diffusion smoothing

## MACROSTATES ##
# MACROSTATE_METHOD values: knnsc, stream, cotan, cellrank.
# For stream, macrostates smaller than MACROSTATE_SIZE are extended to
# neighboring elastic principal graph nodes.
$(eval MACROSTATE_SIZE ?= 100)              # target macrostate size
$(eval MACROSTATE_METHOD ?= cellrank)       # macrostate method

## COTAN ##
# COTAN_METHOD values: classic, soft-merging, strong-merging.
$(eval COTAN_METHOD ?= strong-merging)      # COTAN method
$(eval COTAN_ONLY_HVG ?= false)             # use only HVGs for COTAN macrostates
$(eval MAX_ITER ?= 25)                      # maximum COTAN merging iterations

## CELLRANK ##
# CELLRANK_METHOD values: stability, top_n, eigengap, eigengap_coarse.
$(eval CELLRANK_METHOD ?= stability)        # terminal-state method
$(eval STATES ?= 10)                        # number of CellRank macrostates
$(eval INITIAL_STATES ?= 5)                 # number of initial macrostates
$(eval TERMINAL_STATES ?= 5)                # terminal macrostates for top_n
$(eval CELLRANK_STABILITY ?= 0.96)          # minimum stability for terminal states
$(eval CELLRANK_ALPHA ?= 1.0)               # eigengap weighting parameter

## STREAM ##
# CLUSTERING_METHOD values: kmeans, ap, sc.
# EXTEND_MODE values: QuantDists, QuantCentroid, WeigthedCentroid.
# EXTEND_PARAMETER is a fraction in [0,1].
# COLLAPSE_PARAMETER must be a float when PRUNE_EPG=true.
$(eval CLUSTERING_METHOD ?= kmeans)         # EPG seed clustering
$(eval CLUSTER_NUMBER ?= 6)                 # EPG seed cluster number
$(eval ALPHA_EPG ?= 0.03)                   # branch penalty
$(eval MU_EPG ?= 0.05)                      # harmonic embedding penalty
$(eval LAMBDA_EPG ?= 0.05)                  # edge-length penalty
$(eval EXTEND_EPG ?= true)                  # extend EPG leaf nodes
$(eval EXTEND_MODE ?= QuantDists)           # extension mode
$(eval EXTEND_PARAMETER ?= 0.8)             # extension parameter
$(eval PRUNE_EPG ?= false)                  # prune trivial branches
$(eval COLLAPSE_PARAMETER ?= false)         # pruning collapse parameter

## KNNSC ##
# KNNSC_EMBEDDING must name an embedding in adata.obsm.
# Each named condition needs KNNSC_CENTRALITY_<CONDITION>,
# KNNSC_PERIPHERY_<CONDITION>, or both. Unnamed mono-condition projects use
# KNNSC_CENTRALITY and KNNSC_PERIPHERY.
# CENTRALITY minimizes distances to the cluster's own barycenter.
# PERIPHERY maximizes distances to other clusters' barycenters.
$(eval KNNSC_EMBEDDING ?= X_umap)           # embedding key used for distances
$(eval KNNSC_DIMENSION ?=)                  # embedding dimensions used for distances
$(eval KNNSC_NEIGHBORS ?= 20)               # KNN graph neighbor number
$(eval KNNSC_MIN_CLUSTER_SIZE ?= 20)        # minimum label size for KNNSC candidates

## BINARIZATION ##
# If BIN_HVG_TOP is empty, the number of HVGs is estimated automatically.
# BIN_HVG_* controls the shared HVG selection used by binarization methods.
# BIN_METHOD values: scboolseq, dea, consensus.
# BINARIZATION_FILE overrides BIN_METHOD when set.
# Consensus keeps compatible scBoolSeq/DEA states and leaves conflicts undefined.
$(eval BIN_HVG_METHOD ?= binning)           # HVG method for binarization
$(eval BIN_HVG_TOP ?=)                      # top HVGs for binarization
$(eval BIN_HVG_SPAN ?= 0.3)                 # cell fraction used by loess
$(eval BIN_HVG_BINS ?= 20)                  # mean-expression bins for HVG selection
$(eval BIN_METHOD ?= consensus)             # binarization method

## BIN-CELLS ##
# HVG methods: loess, binning.
# scBoolSeq native thread defaults split JOBS between OpenBLAS and OpenMP.
$(eval BIN_SCBOOLSEQ_ONLY_HVG ?= true)      # use only HVGs for scBoolSeq binarization
$(eval SCBOOLSEQ_OPENBLAS_THREADS ?= auto)  # OpenBLAS threads used by scBoolSeq
$(eval SCBOOLSEQ_OMP_THREADS ?= auto)       # OpenMP threads used by scBoolSeq
$(eval UNIMODAL_QUANTILE ?= 0.10)           # quantile threshold for unimodal genes
$(eval ZEROES_ARE_ZEROES ?= true)           # set zero-inflated zeroes to 0

## BIN-SCBOOLSEQ ##
# NANS_THRESHOLD is in [0,1]. Other vote thresholds are in [0.5,1].
# NANS_THRESHOLD is not applied to zero-inflated genes.
$(eval NANS_THRESHOLD ?= 0.3)               # maximum NaN fraction per macrostate
$(eval BIMODAL_THRESHOLD ?= 0.7)            # minimum vote fraction for bimodal genes
$(eval ZEROINF_THRESHOLD ?= 0.7)            # minimum vote fraction for zero-inflated genes
$(eval UNIMODAL_THRESHOLD ?= 0.7)           # minimum vote fraction for unimodal genes

## BIN-DEA ##
# BIN_LOGFC is non-negative.
# BIN_CORRECTION values: benjamini-hochberg, bonferroni.
# BIN_ALPHA is an adjusted p-value threshold in [0,1].
$(eval BIN_DEA_ONLY_HVG ?= true)            # use only HVGs for DEA binarization
$(eval BIN_LOGFC ?= 0.5)                    # minimum absolute log2 fold-change for binarization
$(eval BIN_CORRECTION ?= benjamini-hochberg)# p-value correction method
$(eval BIN_ALPHA ?= 0.05)                   # adjusted p-value threshold

## SPEC ##
# SPEC_FILE stores manual BoNesis constraints; spec checks their syntax.
$(eval SPEC_FILE ?= spec.yml)               # BoNesis model specification file

## INFERENCE ##
# PRIOR_KNOWLEDGE values: collectri, dorothea, or an existing file path.
# GENEINFO_VERSION values: bundled, latest, or file path.
# OMNIPATH_VERSION values: latest, YYYY-MM-DD, or YYYYMMDD.
# HCOP_VERSION values: bundled, latest, or file path.
# DOROTHEA_API values: modern, legacy. Used only when PRIOR_KNOWLEDGE=dorothea.
# DOROTHEA_COMPATIBILITY values: true, false. Used only when PRIOR_KNOWLEDGE=dorothea.
# DOROTHEA_LEVELS values: A, B, C, D.
# Clingo filter configs: auto, frumpy, jumpy, tweety, handy, crafty, trendy, many, or file path.
# Clingo filter opt modes: opt, optN, ignore.
# Clingo opt strategies: bb[,<method>] or usc[,<method>].
# Diagnostic opt modes: opt gives fast anytime solutions; optN targets
# certified optima; ignore disables optimization objectives.
# CANONICAL_FILTER controls filter-nodes/filter-consts.
# CANONICAL_INFER controls min/submin/diverse.
# TIMEOUT_* values bound the total solver runtime; empty means no timeout.
# PATIENCE_CLAUSE_CONTINUATION_* values bound time without an objective
# improvement at intermediate clause bounds.
# PATIENCE_DOMAIN_CONTINUATION_* values bound portfolio stagnation per wave.
$(eval MAX_CLAUSE ?= 8)                     # maximum literals per propositional formula
$(eval PRIOR_KNOWLEDGE ?= collectri)        # prior GRN domain
$(eval GENEINFO_VERSION ?= bundled)         # NCBI gene_info source
$(eval OMNIPATH_VERSION ?= latest)          # OmniPath resource version
$(eval HCOP_VERSION ?= bundled)             # HCOP orthology version
$(eval DOROTHEA_API ?= modern)              # DoRothEA API source
$(eval DOROTHEA_COMPATIBILITY ?= true)      # reproduce decoupler DoRothEA deduplication
$(eval DOROTHEA_LEVELS ?= A B C)            # DoRothEA confidence levels
$(eval CANONICAL_FILTER ?= false)           # canonical functions during filtering
$(eval CANONICAL_INFER ?= true)             # canonical functions during BN inference

clause_continuation_clingo_default_strategy := bb,lin
clingo_opt_strategy_seed_default := bb,inc
clause_continuation_clingo_mode = $(if $(filter true,$($(1))),opt,$(2))
clause_continuation_clingo_strategy = $(if $(filter true,$($(1))),$(clause_continuation_clingo_default_strategy),$(2))

## MAX-NODES-SOFT ##
$(eval CLAUSE_CONTINUATION_SOFT ?= false)   # progressively increase clause bounds
$(eval DOMAIN_CONTINUATION_SOFT ?= false)   # search and expand candidate subdomains
$(eval PATIENCE_CLAUSE_CONTINUATION_SOFT ?= 30m)
$(eval PATIENCE_DOMAIN_CONTINUATION_SOFT ?= 5m)
$(eval CLINGO_CONFIG_SOFT ?=)               # Clingo default configuration
CLINGO_OPT_MODE_SOFT ?= $(call clause_continuation_clingo_mode,CLAUSE_CONTINUATION_SOFT,optN)
CLINGO_OPT_STRATEGY_SOFT ?= $(call clause_continuation_clingo_strategy,CLAUSE_CONTINUATION_SOFT,usc)
$(eval JOBS_CLINGO_SOFT ?= 1)               # jobs for complete-domain solving
$(eval TIMEOUT_SOFT ?=)                     # timeout

## MAX-CONSTS-SOFT ##
$(eval MIN_SELF_LOOP_CONSTS ?= true)        # minimize one-node feedbacks
$(eval CLINGO_CONFIG_CONSTS ?=)             # Clingo default configuration
$(eval CLINGO_OPT_MODE_CONSTS ?= optN)      # Clingo optimization mode
$(eval CLINGO_OPT_STRATEGY_CONSTS ?= usc)   # Clingo optimization strategy
$(eval JOBS_CLINGO_CONSTS ?= 1)             # solver jobs
$(eval TIMEOUT_CONSTS ?= 24h)               # timeout

## MAX-NODES-RELAXED ##
$(eval CLAUSE_CONTINUATION_RELAXED ?= true) # progressively increase clause bounds
$(eval DOMAIN_CONTINUATION_RELAXED ?= false) # search and expand candidate subdomains
$(eval PATIENCE_CLAUSE_CONTINUATION_RELAXED ?= 30m)
$(eval PATIENCE_DOMAIN_CONTINUATION_RELAXED ?= 5m)
$(eval CLINGO_CONFIG_RELAXED ?=)            # Clingo default configuration
CLINGO_OPT_MODE_RELAXED ?= $(call clause_continuation_clingo_mode,CLAUSE_CONTINUATION_RELAXED,optN)
CLINGO_OPT_STRATEGY_RELAXED ?= $(call clause_continuation_clingo_strategy,CLAUSE_CONTINUATION_RELAXED,usc)
$(eval JOBS_CLINGO_RELAXED ?= 1)            # jobs for complete-domain solving
$(eval TIMEOUT_RELAXED ?= 48h)              # timeout

## MAX-NODES-SEED ##
# TIMEOUT_SEED is required when max-nodes-seed is reached.
$(eval CLAUSE_CONTINUATION_SEED ?= true)    # progressively increase clause bounds
$(eval DOMAIN_CONTINUATION_SEED ?= true)    # search and expand candidate subdomains
$(eval PATIENCE_CLAUSE_CONTINUATION_SEED ?= 30m)
$(eval PATIENCE_DOMAIN_CONTINUATION_SEED ?= 5m)
$(eval CLINGO_CONFIG_SEED ?=)               # Clingo default configuration
CLINGO_OPT_MODE_SEED ?= $(call clause_continuation_clingo_mode,CLAUSE_CONTINUATION_SEED,opt)
CLINGO_OPT_STRATEGY_SEED ?= $(call clause_continuation_clingo_strategy,CLAUSE_CONTINUATION_SEED,$(clingo_opt_strategy_seed_default))
$(eval JOBS_CLINGO_SEED ?= 1)               # jobs for complete-domain solving
$(eval TIMEOUT_SEED ?= 24h)                 # timeout

## MAX-NODES-LOCK ##
$(eval CLAUSE_CONTINUATION_LOCK ?= true)    # progressively increase clause bounds
$(eval PATIENCE_CLAUSE_CONTINUATION_LOCK ?= 30m)
$(eval CLINGO_CONFIG_LOCK ?=)               # Clingo default configuration
CLINGO_OPT_MODE_LOCK ?= $(call clause_continuation_clingo_mode,CLAUSE_CONTINUATION_LOCK,opt)
CLINGO_OPT_STRATEGY_LOCK ?= $(call clause_continuation_clingo_strategy,CLAUSE_CONTINUATION_LOCK,usc)
$(eval JOBS_CLINGO_LOCK ?= 1)               # solver jobs
$(eval TIMEOUT_LOCK ?= 72h)                 # timeout

## OUTPUTS ##
# CONFIG_FORMATS values: csv, cfg, json.
# GRAPH_FORMATS values: dot, neato, circo, fdp, sfdp.
$(eval CONFIG_FORMATS = csv)                # configuration output formats
$(eval GRAPH_FORMATS = dot)                 # Graphviz layouts to export

## BONESIS-MIN ##
$(eval MIN_SELF_LOOP_INFER ?= true)         # minimize one-node feedbacks at inference stage
$(eval CLINGO_OPT_MODE_MIN ?= optN)         # Clingo optimization mode

## BONESIS-DIVERSE / BONESIS-SUBMIN ##
$(eval INFER_LIMIT ?=)                      # diverse/subset-minimal solution limit
# If empty, enumerate all available solutions for the selected inference target.
