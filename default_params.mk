$(eval PARAMS ?= user/apl/params.mk)  # path to user-defined parameter file

# Configuration policy:
# - PARAMS can be overridden here to point to another parameter file
# - all other parameters must be defined in the file specified by PARAMS

## COMPUTING RESOURCES ##
MEMORY ?= 50
JOBS ?= 16
SEED ?= 10
LOGGING ?= true

## INFORMATION ##
$(eval ORGANISM ?= mouse)                   # organism on which data are made up
$(eval CONDITIONS ?= ctrl treated)          # experimental conditions
$(eval RESULTS ?= project/)                 # directory storing outputs

## URL ##
genome_url ?= https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-GRCm39-2024-A.tar.gz
go_organism_url ?= https://current.geneontology.org/ontology/subsets/goslim_$(ORGANISM).obo

## EXTRA PARAMETERS ##
# Parameters useful when user want to run the pipeline by starting at a specific step, with pre-computed dependencies.

$(eval USE_REP ?= X_umap)                   # Key in adata.obsm used as embedding space
$(eval LABEL_COL ?= label)                  # Column name in adata.obs used as labels.

## FILTERING ##
$(eval GENE_DROPOUT ?= 0.999)               # maximum percentage of cell dropout required for a gene to pass filtering
$(eval GENE_EXPRESSION ?= 0 inf)            # minimum and maximum number of cells in which they are expressed required for a gene to pass filtering
$(eval GENE_COUNTS ?= 0 inf)                # minimum and maximum number of counts required for a gene to pass filtering
$(eval CELL_DROPOUT ?= 1)                   # maximum percentage of gene dropout required for a cell to pass filtering
$(eval CELL_EXPRESSION ?= 0 inf)            # minimum and maximum number of expressed genes required for a cell to pass filtering
$(eval CELL_READS ?= 0 inf)                 # minimum and maximum number of reads required for a cell to pass filtering
$(eval MAD_DEVIATION ?= 2 2)                # factor droping cells for which their total reads are smaller or higher than this factor*mean-absolute-deviation with respect to the median
$(eval NORM_MAD ?= true)                    # if true, use normalized mean absolute deviation
$(eval MT ?= 0.05)                          # maximum proportion of expressed genes encoding mitochondrion proteins required for a cell to pass filtering
$(eval HVG ?= 2000)                         # top highly variables genes
$(eval FILTER_NON_HVG ?= false)             # filter non-highly variable genes

## NORMALIZATION ##
$(eval CC_CORRECTION ?= true)               # regress-out cell-cycle effects

## CLUSTERING ##
$(eval INTEGRATION ?= bbknn)                # integration method used (bbknn, scanorama or ingest)
$(eval DIM_PCA ?= 50)                       # number of computed principal components
$(eval DIM_CLUSTERING ?= 20)                # number of principal components taken into account for clustering cells
$(eval DIM_EMBEDDING ?= 2)                  # number of embedding dimensions
$(eval PCA_ONLY_HVG ?= true)                # use only highly variable genes for PCA projection
$(eval NEIGHBORS ?= 20)                     # number of closest neighbors
$(eval METRIC ?= euclidean)                 # metric used for computing closest neighbors and optionally t-sne projection
$(eval RESOLUTION ?= 0.4)                   # coarseness of the clustering
$(eval MIN_DIST ?= 0.1)                     # effective minimum distance between embedded points in umap
$(eval SPREAD ?= 1)                         # effective scale of embedded points in umap

## DEA ##
$(eval LOGFC ?= 0.25)                       # minimum log2 fold-change for a gene to be considered as differentially expressed
$(eval ALPHA ?= 0.05)                       # significance level of rejecting null hypothesis that gene is not differentially expressed
$(eval CORRECTION ?= bonferroni)            # method used for correcting the significance level (benjamini-hochberg or bonferroni)

## ANNOTATION ##
# User have to specify LABEL.

## SCVELO ##
$(eval DIM_MOMENT ?= 15)                    # number of principal components taken into account for estimating moments
$(eval VELOCITY_ONLY_HVG ?= true)           # use only highly variable genes for estimating rna velocities
$(eval SMM_MODE ?= dynamical)               # mode used for estimating the steady-state model (deterministic, stochastic or dynamical)								

## CYTOTRACE ##
$(eval BATCH_SIZE ?= 20000)                 # number of cells to process at once for the pipeline steps (recommended: 20000)
$(eval SMOOTH_BATCH_SIZE ?= 1000)           # number of cells to subsample for the smoothing by diffusion step (recommended: 1000)

## MACROSTATES ##
$(eval MACROSTATE_SIZE ?= 100)              # macrostate size (for cellrank, knnbs or stream)
# For stream: if the number of cells in a macrostate is lower than the threshold, extend macrostate to neighborhood nodes in elastic principal graph
$(eval MACROSTATE_METHOD ?= cotan)         # macrostate method used (knnbs, stream, cotan or cellrank)

## COTAN ##
$(eval COTAN_METHOD ?= strong-merging)      # method for computing cotan clusters (classic, soft-merging or strong-merging)
$(eval COTAN_ONLY_HVG ?= false)             # use only highly variable genes for estimating cotan macrostates
$(eval MAX_ITER ?= 25)                      # maximum iteration number for merging clustering: soft-merging and strong-merging merge uniform clusters

## CELLRANK ##
$(eval CELLRANK_METHOD ?= stability)        # method used to select terminal states (stability, top_n, eigengap or eigengap_coarse)
$(eval STATES ?= 10)                        # number of cellrank macrostates
$(eval INITIAL_STATES ?= 5)                 # number of initial macrostates
$(eval TERMINAL_STATES ?= 5)                # number of terminal macrostates (used only if CELLRANK_METHOD = top_n)
$(eval CELLRANK_STABILITY ?= 0.96)          # minimum stability for a state to be selected as a final macrostate
$(eval CELLRANK_ALPHA ?= 1.0)               # weight given to the deviation of an eigenvalue from one (used only if CELLRANK_METHOD = eigengap or eigengap_coarse)

## STREAM ##
$(eval CLUSTERING_METHOD ?= kmeans)         # clustering method used for seeding the initial elastic principal graph (kmeans, ap, sc)
$(eval CLUSTER_NUMBER ?= 6)                 # number of clusters for elastic principal graph
$(eval ALPHA_EPG ?= 0.03)                   # alpha parameter used for computing elastic energy (penalized spurious branching events)
$(eval MU_EPG ?= 0.05)                      # mu parameter used for computing elastic energy (penalized the deviation from harmonic embedding)
$(eval LAMBDA_EPG ?= 0.05)                  # lambda parameter used for computing elastic energy (penalized the total length of edges)
$(eval EXTEND_EPG ?= true)                  # extend leaves of elastic principal graph by attaching new nodes
$(eval EXTEND_MODE ?= QuantDists)           # mode used for extending the leaves (used only if EXTEND_EPG = true, value: QuantDists, QuantCentroid, WeigthedCentroid)
$(eval EXTEND_PARAMETER ?= 0.8)             # stream parameter used for extending the leaves (used only if EXTEND_EPG = true)
$(eval PRUNE_EPG ?= false)                  # prune elastic principal graph by filtering out trivial branches
$(eval COLLAPSE_PARAMETER ?= false)         # stream parameter used for pruning the graph (used only if PRUNE_EPG = true)

## KNNBS ##
$(eval KNNBS_EMBEDDING ?= umap)             # embedding space used when calculating pairwise distances (pca or umap)
$(eval KNNBS_DIMENSION ?=)                  # number of embedding dimensions used when calculating pairwise distances
$(eval KNNBS_NEIGHBORS ?= 20)               # number of closest neighbors for k-nearest neighbors graph

## BIN-CELLS ##
$(eval SCBOOLSEQ_HVG_METHOD ?= cell_ranger) # method used for identifying highly variable genes (seurat, cell_ranger or seurat_v3, if not specified, consider all genes)
$(eval SCBOOLSEQ_TOP_HVG ?=)                # use only top SCBOOLSEQ_TOP_HVG highly variable genes for binarizing cells (if not specified, estimate automatically number of hvg)
$(eval UNIMODAL_QUANTILE ?= 0.10)           # quantile classifying cells into inactive/active when learnt distribution is unimodal
$(eval ZEROES_ARE_ZEROES ?= true)           # binarize zero-values to zero instead of nan when learnt distribution is zero-inflated
# $(eval ZEROINF_BINARIZER ?= quantile)       # method to binarize cells when classified as zero-inflated (value: quantile, zero_or_not)

## BIN-SCBOOLSEQ ##
$(eval NANS_THRESHOLD ?= 0.3)               # maximum proportion of nan-values in a cluster required for a gene to be binarized (not applied to zero-inflated genes)
$(eval BIMODAL_THRESHOLD ?= 0.7)            # minimum proportion of zero- or one-values w.r.t binarized values in a cluster required for a bimodal gene to be binarized
$(eval ZEROINF_THRESHOLD ?= 0.7)            # minimum proportion of zero- or one-values w.r.t binarized and nan values in a cluster required for a zero-inflated gene to be binarized
$(eval UNIMODAL_THRESHOLD ?= 0.7)           # minimum proportion of zero- or one-values w.r.t binarized values in a cluster required for a unimodal gene to be binarized

## BIN-DEA ##
$(eval DEA_HVG_METHOD ?= cell_ranger)       # method used for identifying highly variable genes (seurat, cell_ranger or seurat_v3, if not specified, consider all genes)
$(eval DEA_TOP_HVG ?=)                      # use only top DEA_TOP_HVG highly variable genes for binarizing cells (if not specified, estimate automatically number of hvg)
$(eval BIN_LOGFC ?= 0.5)                    # minimum log2 fold-change in absolute value for a gene to be binarized
$(eval BIN_ALPHA ?= 0.05)                   # maximum adjusted p-value for a gene to be binarized
$(eval BIN_CORRECTION ?= benjamini-hochberg)# method used for correcting the significance level (benjamini-hochberg or bonferroni)

## BINARIZATION ##
$(eval BINARIZATION_FILE ?=)                # optional pre-computed macrostate binarization file; used instead of BIN_METHOD target when defined
$(eval BIN_METHOD ?= consensus)             # binarization method used when BINARIZATION_FILE is not defined (scboolseq, dea or consensus)

## SPEC ##
$(eval YAML_MODEL ?= spec.yml)              # file storing model specifications for bonesis
$(eval MODEL_HVG_METHOD ?=)                 # method used for identifying highly variable genes (seurat, cell_ranger or seurat_v3, if not specified, consider all genes)
$(eval MODEL_TOP_HVG ?=)                    # use only top BONESIS_TOP_HVG highly variable genes for inferring Boolean Networks (if not specified, estimate automatically number of hvg)

## INFERENCE ##
$(eval MAX_CLAUSE ?= 8)                     # maximum number of literals/atoms in each propositional formula
$(eval PRIOR_KNOWLEDGE ?= collectri)        # prior knowledge defining the domain/search space (collectri, dorothea)

## MAX-NODES-SOFT
$(eval CLINGO_OPT_MODE_SOFT ?= optN)
$(eval CLINGO_OPT_STRATEGY_SOFT ?= usc)
$(eval JOBS_SOFT ?= 1)
$(eval TIMEOUT_SOFT ?= 24h)

## MAX-STRONG-CONSTS
$(eval MIN_SELF_LOOP_CONSTS ?= true)         # minimize the number of length-one feedbacks
$(eval CLINGO_OPT_MODE_CONSTS ?= optN)
$(eval CLINGO_OPT_STRATEGY_CONSTS ?= usc)
$(eval JOBS_CONSTS ?= 1)
$(eval TIMEOUT_CONSTS ?= 24h)

## MAX-NODES-RELAXED
$(eval CLINGO_OPT_MODE_RELAXED ?= optN)
$(eval CLINGO_OPT_STRATEGY_RELAXED ?= usc)
$(eval JOBS_RELAXED ?= 1)
$(eval TIMEOUT_RELAXED ?= 48h)

## MAX-NODES-SEED
$(eval CLINGO_OPT_MODE_SEED ?= opt)
$(eval CLINGO_OPT_STRATEGY_SEED ?= usc)
$(eval JOBS_SEED ?= 1)
$(eval TIMEOUT_SEED ?= 24h)
## Corriger le makefile
## Il faut que ce timeout soit tj défini.

## MAX-NODES-LOCK
$(eval CLINGO_OPT_MODE_LOCK ?= opt)
$(eval CLINGO_OPT_STRATEGY_LOCK ?= usc)
$(eval JOBS_LOCK ?= 1)
$(eval TIMEOUT_LOCK ?= 72h)

## INFERENCE ##
$(eval CONFIG_FORMATS = csv cfg)            # output formats used for exporting Boolean configurations (csv, cfg, json)

## BONESIS-MIN ##
$(eval MIN_SELF_LOOP_INFER ?= true)         # minimize the number of length-one feedbacks at inference stage
$(eval CLINGO_OPT_MODE_MIN ?= optN)

## BONESIS-SUB ##
$(eval GRAPH_FORMATS = dot neato circo fdp sfdp) # graphviz layout programs used for exporting Boolean network associated influence graphs
$(eval INFER_LIMIT ?=)          			     # number of diverse subset minimal solutions. If not specified, enumerate all subset minimal solutions without diversity

