## computing resources ##

SHELL = /bin/bash
MEMORY = 50
JOBS = 16

## informations ##

$(eval METADATA_CTRL := sample_name=ctrl condition=control)			# Must contains condition
$(eval METADATA_TREATED := sample_name=treated condition=treated)	# Must contains condition
ORGANISM := mouse
CONDITIONS := ctrl treated

## clustering parameters ##

$(eval K_NEIGHBORS_CTRL := 20)					# K-closest neighbors
$(eval RESOLUTION_LEIDEN_CTRL := 0.4)			# coarseness of the clustering when using Leiden algorithm
$(eval DIM_PCA_CTRL := 50)						# number of principal components
$(eval DIM_CLUSTERING_CTRL := 15)				# number of principal components taken into account for clustering
$(eval DIM_UMAP_CTRL := 2)						# number of embedding dimensions
SEED_CLUSTER_CTRL = 0

$(eval K_NEIGHBORS_TREATED := 20)				# K-closest neighbors
$(eval RESOLUTION_LEIDEN_TREATED := 0.4)		# coarseness of the clustering when using Leiden algorithm
$(eval DIM_PCA_TREATED := 50)					# number of principal components
$(eval DIM_CLUSTERING_TREATED := 15)			# number of principal components taken into account for clustering
$(eval DIM_UMAP_TREATED := 2)					# number of embedding dimensions
SEED_CLUSTER_TREATED = 0

INTEGRATION_METHOD = bbknn
$(eval K_NEIGHBORS_INTEGRATED := $(K_NEIGHBORS_CTRL))	# K-closest neighbors
$(eval RESOLUTION_LEIDEN_INTEGRATED := 0.4)				# coarseness of the clustering when using Leiden algorithm
$(eval DIM_PCA_INTEGRATED := 50)						# number of principal components
$(eval DIM_CLUSTERING_INTEGRATED := 15)					# number of principal components taken into account for clustering
$(eval DIM_UMAP_INTEGRATED := 2)						# number of embedding dimensions
SEED_CLUSTER_INTEGRATED = 0

$(eval LABELING_FROM_INTEGRATION := true)		# true or false

## trajectory parameters ##

# scvelo #
$(eval SCVELO_K_NEIGHBORS_CTRL := 20)			# K-closest neighbors
$(eval SCVELO_DIM_CLUSTERING_CTRL := 15)		# number of principal components taken into account for clustering
$(eval SMM_MODE_CTRL := dynamical)				# mode used to estimate the steady-state model (deterministic, stochastic or dynamical)								
$(eval SCVELO_K_NEIGHBORS_TREATED := $(K_NEIGHBORS_TREATED))	# K-closest neighbors
$(eval SCVELO_DIM_CLUSTERING_TREATED := 15)						# number of principal components taken into account for clustering
$(eval SMM_MODE_TREATED := dynamical)							# mode used to estimate the steady-state model (deterministic, stochastic or dynamical)

# stream #
LAMBDA_CTRL := 0.05
MU_CTRL := 0.05
ALPHA_CTRL := 0.03
EXTEND_CTRL := 0.8
ROOT_CTRL := 0
IGNORED_NODES_CTRL :=
LAMBDA_TREATED := 0.05
MU_TREATED := 0.05
ALPHA_TREATED := 0.03
EXTEND_TREATED := 0.8
ROOT_TREATED := 0
IGNORED_NODES_TREATED :=

# macrostates #
$(eval MACROSTATES_FROM_CELLRANK := false)		# true or false
$(eval MACROSTATE_SIZE := 100)
$(eval CELLRANK_METHOD := stability)			# stability, top_n, eigengap or eigengap_coarse
$(eval INITIAL_STATES_CTRL := 1)				# number of initial states with cellrank
$(eval TERMINAL_STATES_CTRL := 4)				# number of terminal states with cellrank
$(eval INITIAL_STATES_TREATED := 1)				# number of initial states with cellrank
$(eval TERMINAL_STATES_TREATED := 4)			# number of terminal states with cellrank

## binarization parameters

$(eval INTEGRATED_BINARIZATION := merged)		# split or merged
$(eval BINARIZATION_ONLY_HVG := true)			# perform binarization with highly-variable genes only or with all genes
$(eval ZEROES_ARE_ZEROES := false)				# when zero-inflated is inferred for a gene-related distribution; if its counting with respect to a cell is equal to zero, binarize either to zero or nan

## inference parameters

$(eval MINIMIZE_AUTO_LOOPS := true)				# true or false