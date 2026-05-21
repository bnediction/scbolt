$(eval PARAMS ?= user/apl/params.mk)  # user parameter file

# Configuration policy:
# - PARAMS can be overridden here to point to another parameter file
# - all other parameters must be defined in the file specified by PARAMS
# - target-specific parameters may stay undefined until their target is requested
# - Boolean parameters use true or false
# - min/max ranges use two values: <min> <max>; use inf/-inf for open bounds

## COMPUTING RESOURCES ##
# MEMORY is in GB. LOGGING=true persists command output in log files.
MEMORY ?= 50
JOBS ?= 16
SEED ?= 10
LOGGING ?= true

## INFORMATION ##
# ORGANISM values: mouse, human, escherichia-coli.
$(eval ORGANISM ?= mouse)                   # organism used for gene resources
$(eval CONDITIONS ?= ctrl treated)          # experimental conditions
$(eval RESULTS ?= project/)                 # output directory

## URLS ##
genome_url ?= https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-GRCm39-2024-A.tar.gz
go_organism_url ?= https://current.geneontology.org/ontology/subsets/goslim_$(ORGANISM).obo

## EXTRA PARAMETERS ##
# Useful when starting from user-provided or precomputed upstream analyses.
# BINARIZATION_FILE overrides the binarization target when set.
# USE_REP must name an embedding in adata.obsm, usually created by clustering.
# LABEL_COL is created by annotation, copied per condition, and used by downstream macrostate methods.
$(eval BINARIZATION_FILE ?=)                # precomputed macrostate binarization
$(eval USE_REP ?= X_umap)                   # embedding key in adata.obsm
$(eval LABEL_COL ?= label)                  # annotated cell-type column in adata.obs

## FILTERING ##
# Dropout and MT thresholds are fractions in [0,1].
# *_EXPRESSION, *_COUNTS, and *_READS are non-negative min/max ranges.
# MAD_DEVIATION defines lower and upper factors for discarding cells 
# whose log-total reads deviate from the median by more than the corresponding MAD-scaled threshold.
$(eval GENE_DROPOUT ?= 0.999)               # maximum gene dropout fraction required for a gene to pass filtering
$(eval GENE_EXPRESSION ?= 0 inf)            # minimum and maximum number of cells expressing a gene required for it to pass filtering
$(eval GENE_COUNTS ?= 0 inf)                # minimum and maximum total counts required for a gene to pass filtering
$(eval CELL_DROPOUT ?= 1)                   # maximum gene dropout fraction required for a cell to pass filtering
$(eval CELL_EXPRESSION ?= 0 inf)            # minimum and maximum number of expressed genes required for a cell to pass filtering
$(eval CELL_READS ?= 0 inf)                 # minimum and maximum total reads required for a cell to pass filtering
$(eval MAD_DEVIATION ?= 2 2)                # lower/upper MAD factors around median log-total reads
$(eval NORM_MAD ?= true)                    # use Gaussian-consistent MAD scaling
$(eval MT ?= 0.05)                          # maximum mitochondrial count fraction required for a cell to pass filtering
$(eval HVG ?= 2000)                         # number of highly variable genes
$(eval FILTER_NON_HVG ?= false)             # keep only highly variable genes

## NORMALIZATION ##
# CC_CORRECTION=true is supported only for ORGANISM=mouse.
$(eval CC_CORRECTION ?= true)               # regress out cell-cycle effects

## CLUSTERING ##
# INTEGRATION values: bbknn, scanorama, ingest.
$(eval INTEGRATION ?= bbknn)                # integration method
$(eval DIM_PCA ?= 50)                       # number of PCA components
$(eval DIM_CLUSTERING ?= 20)                # PCA components used for clustering
$(eval DIM_EMBEDDING ?= 2)                  # number of embedding dimensions
$(eval PCA_ONLY_HVG ?= true)                # use only HVGs for PCA projection
$(eval NEIGHBORS ?= 20)                     # number of nearest neighbors
$(eval METRIC ?= euclidean)                 # distance metric for neighbors and optionally t-SNE projection
$(eval RESOLUTION ?= 0.4)                   # Leiden clustering resolution
$(eval MIN_DIST ?= 0.1)                     # UMAP minimum distance
$(eval SPREAD ?= 1)                         # UMAP spread

## DEA ##
# LOGFC is non-negative.
# CORRECTION values: benjamini-hochberg, bonferroni.
# ALPHA is an adjusted p-value threshold in [0,1].
$(eval LOGFC ?= 0.25)                       # minimum absolute log2 fold-change for differential expression
$(eval CORRECTION ?= bonferroni)            # p-value correction method
$(eval ALPHA ?= 0.05)                       # adjusted p-value threshold

## ANNOTATION ##
# LABEL must be defined before annotation; values map clusters 0..n to biological labels.

## VELOCITY ##
# SMM_MODE values: deterministic, stochastic, dynamical.
$(eval DIM_MOMENT ?= 15)                    # PCA components used to estimate moments
$(eval VELOCITY_ONLY_HVG ?= true)           # use only HVGs for RNA velocity
$(eval SMM_MODE ?= dynamical)               # scVelo mode

## CYTOTRACE ##
# CytoTRACE supports ORGANISM=mouse or ORGANISM=human.
$(eval BATCH_SIZE ?= 20000)                 # cells processed per batch
$(eval SMOOTH_BATCH_SIZE ?= 1000)           # cells subsampled for diffusion smoothing

## MACROSTATES ##
# MACROSTATE_METHOD values: knnbs, stream, cotan, cellrank.
# For stream, if the number of cells assigned to a macrostate is lower than MACROSTATE_SIZE, the macrostate is extended to neighbouring nodes in the elastic principal graph.
$(eval MACROSTATE_SIZE ?= 100)              # target macrostate size
$(eval MACROSTATE_METHOD ?= cotan)          # macrostate method

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

## KNNBS ##
# KNNBS_EMBEDDING values supported by the Makefile: pca, umap.
# Each condition needs KNNBS_CENTRALITY_<CONDITION>, KNNBS_PERIPHERY_<CONDITION>, or both.
# CENTRALITY minimizes distances to the cluster's own barycenter.
# PERIPHERY maximizes distances to other clusters' barycenters.
$(eval KNNBS_EMBEDDING ?= umap)             # embedding used for distances
$(eval KNNBS_DIMENSION ?=)                  # embedding dimensions used for distances
$(eval KNNBS_NEIGHBORS ?= 20)               # KNN graph neighbor number

## BIN-CELLS ##
# HVG methods: seurat, cell_ranger, seurat_v3.
# If SCBOOLSEQ_TOP_HVG is not specified, the number of HVGs is estimated automatically, except when SCBOOLSEQ_HVG_METHOD=seurat_v3 where it is required.
$(eval SCBOOLSEQ_HVG_METHOD ?= cell_ranger) # HVG method for cell binarization
$(eval SCBOOLSEQ_TOP_HVG ?=)                # top HVGs for cell binarization
$(eval UNIMODAL_QUANTILE ?= 0.10)           # quantile threshold for unimodal genes
$(eval ZEROES_ARE_ZEROES ?= true)           # set zero-inflated zeroes to 0

## BIN-SCBOOLSEQ ##
# NANS_THRESHOLD is in [0,1]. Other vote thresholds are in [0.5,1].
$(eval NANS_THRESHOLD ?= 0.3)               # maximum NaN fraction per macrostate, not applied to zero-inflated genes
$(eval BIMODAL_THRESHOLD ?= 0.7)            # minimum vote fraction for bimodal genes
$(eval ZEROINF_THRESHOLD ?= 0.7)            # minimum vote fraction for zero-inflated genes
$(eval UNIMODAL_THRESHOLD ?= 0.7)           # minimum vote fraction for unimodal genes

## BIN-DEA ##
# HVG methods: seurat, cell_ranger, seurat_v3.
# If DEA_TOP_HVG is not specified, the number of HVGs is estimated automatically, except when DEA_HVG_METHOD=seurat_v3 where it is required.
# BIN_LOGFC is non-negative.
# BIN_CORRECTION values: benjamini-hochberg, bonferroni.
# BIN_ALPHA is an adjusted p-value threshold in [0,1].
$(eval DEA_HVG_METHOD ?= cell_ranger)       # HVG method for DEA binarization
$(eval DEA_TOP_HVG ?=)                      # top HVGs for DEA binarization
$(eval BIN_LOGFC ?= 0.5)                    # minimum absolute log2 fold-change for binarization
$(eval BIN_CORRECTION ?= benjamini-hochberg)# p-value correction method
$(eval BIN_ALPHA ?= 0.05)                   # adjusted p-value threshold

## BINARIZATION ##
# BIN_METHOD values: scboolseq, dea, consensus.
# BINARIZATION_FILE overrides BIN_METHOD when set.
# Consensus keeps compatible scBoolSeq/DEA states and leaves conflicts undefined.
$(eval BIN_METHOD ?= consensus)             # binarization method

## SPEC ##
# HVG methods: empty, seurat, cell_ranger, seurat_v3.
# MODEL_TOP_HVG is required when MODEL_HVG_METHOD=seurat_v3.
# YAML_MODEL stores manual BoNesis constraints; spec checks their syntax.
$(eval YAML_MODEL ?= spec.yml)              # BoNesis model specification file
$(eval MODEL_HVG_METHOD ?=)                 # HVG method for model genes
$(eval MODEL_TOP_HVG ?=)                    # top HVGs for model genes

## INFERENCE ##
# PRIOR_KNOWLEDGE values: collectri, dorothea, or an existing file path.
# DOROTHEA_API values: current, legacy. Used only when PRIOR_KNOWLEDGE=dorothea.
# current loads DoRothEA in scbolt-bonesis; legacy first exports a CSV file.
# Clingo opt modes: opt, optN, ignore, enum,<n>.
# Clingo opt strategies: bb[,<method>] or usc[,<method>].
# TIMEOUT_* values are passed to GNU timeout; empty means no timeout.
$(eval MAX_CLAUSE ?= 8)                     # maximum literals per propositional formula
$(eval PRIOR_KNOWLEDGE ?= collectri)        # prior GRN domain
$(eval DOROTHEA_API ?= current)             # DoRothEA API source

## MAX-NODES-SOFT ##
$(eval CLINGO_OPT_MODE_SOFT ?= optN)        # Clingo optimization mode
$(eval CLINGO_OPT_STRATEGY_SOFT ?= usc)     # Clingo optimization strategy
$(eval JOBS_SOFT ?= 1)                      # solver jobs
$(eval TIMEOUT_SOFT ?=)                     # timeout

## MAX-CONSTS-SOFT ##
$(eval MIN_SELF_LOOP_CONSTS ?= true)        # minimize one-node feedbacks
$(eval CLINGO_OPT_MODE_CONSTS ?= optN)      # Clingo optimization mode
$(eval CLINGO_OPT_STRATEGY_CONSTS ?= usc)   # Clingo optimization strategy
$(eval JOBS_CONSTS ?= 1)                    # solver jobs
$(eval TIMEOUT_CONSTS ?= 24h)               # timeout

## MAX-NODES-RELAXED ##
$(eval CLINGO_OPT_MODE_RELAXED ?= optN)     # Clingo optimization mode
$(eval CLINGO_OPT_STRATEGY_RELAXED ?= usc)  # Clingo optimization strategy
$(eval JOBS_RELAXED ?= 1)                   # solver jobs
$(eval TIMEOUT_RELAXED ?= 48h)              # timeout

## MAX-NODES-SEED ##
# TIMEOUT_SEED is required when max-nodes-seed is reached.
$(eval CLINGO_OPT_MODE_SEED ?= opt)         # Clingo optimization mode
$(eval CLINGO_OPT_STRATEGY_SEED ?= usc)     # Clingo optimization strategy
$(eval JOBS_SEED ?= 1)                      # solver jobs
$(eval TIMEOUT_SEED ?= 24h)                 # timeout

## MAX-NODES-LOCK ##
$(eval CLINGO_OPT_MODE_LOCK ?= opt)         # Clingo optimization mode
$(eval CLINGO_OPT_STRATEGY_LOCK ?= usc)     # Clingo optimization strategy
$(eval JOBS_LOCK ?= 1)                      # solver jobs
$(eval TIMEOUT_LOCK ?= 72h)                 # timeout

## OUTPUTS ##
# CONFIG_FORMATS values: csv, cfg, json.
# GRAPH_FORMATS values: dot, neato, circo, fdp, sfdp.
$(eval CONFIG_FORMATS = csv cfg)            # configuration output formats
$(eval GRAPH_FORMATS = dot neato circo fdp sfdp) # Graphviz layouts to export

## BONESIS-MIN ##
$(eval MIN_SELF_LOOP_INFER ?= true)         # minimize one-node feedbacks at inference stage
$(eval CLINGO_OPT_MODE_MIN ?= optN)         # Clingo optimization mode

## BONESIS-DIVERSE / BONESIS-SUBMIN ##
$(eval INFER_LIMIT ?=)                      # number of diverse sparsest or subset-minimal BN solutions; if empty, enumerate all available solutions according to the selected inference target
