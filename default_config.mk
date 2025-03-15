## BEGIN COMPUTING RESOURCES ##

MEMORY = 50
JOBS = 16

## END COMPUTING RESOURCES ##

## BEGIN INFORMATION ##

$(eval METADATA_CTRL := sample_name=ctrl condition=control)			# must contains condition
$(eval METADATA_TREATED := sample_name=treated condition=treated)	# must contains condition
ORGANISM := mouse
CONDITIONS := ctrl treated
SEED := 0

## END INFORMATION ##

## BEGIN CLUSTERING ##

# clustering #

$(eval HVG := 2000)							# top highly variables genes
$(eval K_NEIGHBORS := 20)					# K-closest neighbors
$(eval RESOLUTION := 0.4)					# coarseness of the clustering for Leiden algorithm
$(eval DIM_PCA := 50)						# number of principal components
$(eval DIM_CLUSTERING := 15)				# number of principal components taken into account for clustering
$(eval DIM_UMAP := 2)						# number of embedding dimensions
$(eval INTEGRATION_METHOD := bbknn)			# bbknn, ingest or scanorama

# annotation #

# $(eval CLUSTER_LABEL_INTEGRATED := 0=cluster0 1=cluster1 ...)
$(eval LABELING_FROM_INTEGRATION := true)	# true or false (if false, please define CLUSTER_LABEL_<CONDITION>)

## END CLUSTERING ##

## BEGIN TRAJECTORY INFERENCE ##

# scvelo #

$(eval SMM_MODE := dynamical)				# mode used to estimate the steady-state model (deterministic, stochastic or dynamical)								

# stream-pseudotime #

CLUSTER_NUMBER = 6
LAMBDA = 0.05
MU = 0.05
ALPHA = 0.03
EXTEND := 0.8
EXTEND_LEAF_NODES := true
PRUNE_GRAPH := false

# stream-trajectories #

# ROOT_<CONDITION> = 0						# specify which node is the starting point
# IGNORED_NODES_<CONDITION> =				# specify which nodes to ignore for deciphering trajectories

# macrostates #
$(eval MACROSTATES_METHOD := cotan)				# cellrank, center-extremity or cotan
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