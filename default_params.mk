## BEGIN COMPUTING RESOURCES ##

MEMORY = 50
JOBS = 16

## END COMPUTING RESOURCES ##

## BEGIN INFORMATION ##

ORGANISM := mouse
CONDITIONS := ctrl treated
SEED := 10

## END INFORMATION ##

## BEGIN FILTERING ##

$(eval GENE_DROPOUT := 0.999)				# maximum percentage of cell dropout required for a gene to pass filtering
$(eval GENE_EXPRESSION := 0 inf)			# minimum and maximum number of expressed cells required for a gene to pass filtering
$(eval GENE_COUNTS := 0 inf)				# minimum and maximum number of counts required for a gene to pass filtering
$(eval CELL_DROPOUT := 1)					# maximum percentage of gene dropout required for a cell to pass filtering
$(eval CELL_EXPRESSION := 0 inf)			# minimum and maximum number of expressed genes required for a cell to pass filtering
$(eval CELL_READS := 0 inf)					# minimum and maximum number of reads required for a cell to pass filtering
$(eval MAD_DEVIATION := 2 2)				# factor droping cells for which their total reads are smaller or higher than this factor*mean-absolute-deviation with respect to the median
$(eval NORM_MAD := true)					# if true, use normalized mean absolute deviation
$(eval MT := 0.05)							# maximum proportion of expressed genes encoding mithocondrion proteins required for a cell to pass filtering
$(eval HVG := 2000)							# top highly variables genes
$(eval FILTER_NON_HVG := false)				# filter non-highly variable genes

## END FILTERING ##

## BEGIN NORMALIZATION ##

$(eval CC_CORRECTION := true)				# regress-out cell cycle effects

## END NORMALIZATION ##

## BEGIN CLUSTERING ##

$(eval INTEGRATION := bbknn)				# integration method used (bbknn, scanorama or ingest)
$(eval DIM_PCA := 15)						# number of computed principal components
$(eval DIM_CLUSTERING := 15)				# number of principal components taken into account for clustering cells
$(eval DIM_EMBEDDING := 2)					# number of embedding dimensions
$(eval PCA_ONLY_HVG := true)				# use only highly variable genes for PCA projection
$(eval NEIGHBORS := 20)						# number of closest neighbors
$(eval METRIC := euclidean)					# metric used for computing closest neighbors and optionally t-sne projection
$(eval RESOLUTION := 0.4)					# coarseness of the clustering
$(eval MIN_DIST := 0.5)						# effective minimum distance between embedded points in umap
$(eval SPREAD := 1)							# effective scale of embedded points in umap

## END CLUSTERING ##

## BEGIN DEA ##

$(eval LOGFC := 0.25)						# minimum log2 fold-change for a gene to be considered as differentially expressed
$(eval ALPHA := 0.05)						# significance level of rejecting null hypothesis that gene is not differentially expressed
$(eval CORRECTION := bonferroni)			# method used for correcting the significance level (benjamini-hochberg ou bonferroni)

## END DEA ##

## BEGIN ANNOTATION ##

$(eval LABELING_FROM_INTEGRATION := true)	# whether new labels are derived from integrated data only or specified by user for each reference

# Note: if LABELING_FROM_INTEGRATION is true, then user have to specify LABEL_INTEGRATED only.
# Otherwise, user have to specify LABEL_<REFERENCE> for each reference

## END ANNOTATION ##

## BEGIN SCVELO ##

$(eval DIM_MOMENT := 15)					# number of principal components taken into account for estimating moments
$(eval VELOCITY_ONLY_HVG := true)			# use only highly variable genes for estimating rna velocities
$(eval SMM_MODE := dynamical)				# mode used for estimating the steady-state model (deterministic, stochastic or dynamical)								

## END SCVELO ##

## BEGIN MACROSTATES ##

$(eval MACROSTATE_SIZE := 100)				# macrostate size (for cellrank and knnbs)
$(eval MACROSTATES_METHOD := cotan)			# macrostate method used (knnbs, stream, cotan or cellrank)

## END MACROSTATES ##

## BEGIN COTAN ##

$(eval COTAN_METHOD := strong-merging)		# method for computing cotan clusters (classic, soft-merging or strong-merging)
$(eval COTAN_ONLY_HVG := false)				# use only highly variable genes for estimating cotan macrostates
$(eval MAX_ITER := 25)						# maximum iteration number for merging clustering: soft-merging and strong-merging merge uniform clusters

## END COTAN ##

## BEGIN CELLRANK ##

$(eval CELLRANK_METHOD := stability)		# method used to select terminal states (stability, top_n, eigengap or eigengap_coarse)
$(eval STATES := 10)						# number of cellrank macrostates
$(eval INITIAL_STATES := 5)					# number of initial macrostates
$(eval TERMINAL_STATES := 5)				# number of terminal macrostates (used only if CELLRANK_METHOD = top_n)
$(eval CELLRANK_STABILITY := 0.96)			# minimum stability for a state to be selected as a final macrostate
$(eval CELLRANK_ALPHA := 1.0)				# weight given to the deviation of an eigenvalue from one (used only if CELLRANK_METHOD = eigengap or eigengap_coarse)

## END CELLRANK ##

## BEGIN STREAM ##

$(eval CLUSTER_NUMBER := 6)					# number of clusters for elastic principal graph
$(eval LAMBDA_EPG := 0.05)					# lambda parameter used for computing the elastic energy
$(eval MU_EPG := 0.05)						# mu parameter used for computing the elastic energy
$(eval ALPHA_EPG := 0.03)					# alpha parameter of the penalized elastic energy
$(eval EXTEND_EPG := true)					# extend leaves of elastic principal graph by attaching them new nodes
$(eval EXTEND_PARAMETER := 0.8)				# stream parameter used for extending the leaves (used only if EXTEND_EPG = true)
$(eval PRUNE_EPG := false)					# prune elastic principal graph by filtering out trivial branches
$(eval COLLAPSE_PARAMETER := false)			# stream parameter used for prunning the graph (used only if PRUNE_EPG = true)

## END STREAM ##

## BEGIN KNNBS ##

$(eval KNNBS_EMBEDDING := pca)				# embedding space used when calculating pairwise distances (pca or umap)
$(eval KNNBS_DIMENSION := )					# number of embedding dimensions used when calculating pairwise distances
$(eval KNNBS_NEIGHBORS := 20)				# number of closest neighbors for k-nearest neighbors graph

## END KNNBS ##

## BEGIN BIN-CELLS ##

$(eval BIN_ONLY_HVG := false)				# use only highly variable genes for binarizing cells
$(eval UNIMODAL_QUANTILE := 0.10)			# quantile classifying cells into inactive/active when learnt distribution is unimodal
$(eval ZEROES_ARE_ZEROES := true)			# binarize zero-values to zero instead of nan when learnt distribution is zero-inflated

## END BIN-CELLS ##

## BEGIN BIN-MACROSTATES ##

$(eval NANS_THRESHOLD := 0.3)				# maximum proportion of nan-values in a cluster required for a gene to be binarized
$(eval BIMODAL_THRESHOLD := 0.67)			# minimum proportion of zero- or one-values against binarized values in a cluster required for a bimodal gene to be binarized
$(eval ZEROINF_THRESHOLD := 0.5)			# minimum proportion of one-values against binarized values in a cluster required for a zero-inflated gene to be binarized to one, otherwise zero
$(eval UNIMODAL_THRESHOLD := 0.67)			# minimum proportion of zero- or one-values against binarized values in a cluster required for a unimodal gene to be binarized

## END BIN-MACROSTATES ##

## BEGIN MODELING ##

$(eval MODEL_SPECIFICATION := spec/spec.yml)	# file storing model specifications for bonesis

## END MODELING ##

## BEGIN BONESIS-FILTERING-TWO ##

$(eval FILTER_MIN_FEEDBACKS := true)		# minimize the number of length-one feedbacks at filtering stage

## END BONESIS-FILTERING-TWO ##

## BEGIN BONESIS-INFERENCE-MIN ##

$(eval MIN_FEEDBACKS := true)			# minimize the number of length-one feedbacks at inference stage

## END BONESIS-INFERENCE-MIN ##
