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
$(eval RESOLUTION := 0.4)					# parameter value controlling the coarseness of the clustering

## END CLUSTERING ##

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
EXTEND_LEAF_NODES := true
EXTEND := 0.8
PRUNE_GRAPH := false

# stream-trajectories #

# ROOT_<CONDITION> = 0						# specify which node is the starting point for condition <CONDITION>
# IGNORED_NODES_<CONDITION> =				# specify which nodes to ignore for deciphering trajectories in condition <CONDITION>

## END TRAJECTORY INFERENCE ##

## BEGIN MACROSTATE CHARACTERIZATION ##

$(eval MACROSTATES_METHOD := cotan)			# cellrank, center-extremity or cotan

# cellrank #

$(eval MACROSTATE_SIZE := 100)
$(eval CELLRANK_METHOD := stability)		# stability, top_n, eigengap or eigengap_coarse
# INITIAL_STATES_<CONDITION> =				# number of initial states with cellrank for condition <CONDITION>
# TERMINAL_STATES_<CONDITION> =				# number of terminal states with cellrank for condition <CONDITION>

# center-extremity #

# CENTER_<CONDITION> := <cluster...>		# clusters for which macrostates are deriving by keeping cells closest to the cluster-related barycenter
# EXTREMITY_<CONDITION> := <cluster...>		# clusters for which macrostates are deriving by keeping cells cells furthest from other cluster-related barycenters
EXCLUDE := true

## END MACROSTATE CHARACTERIZATION ##

## BEGIN BINARIZATION ##

# bin-cells #

$(eval INTEGRATED_BINARIZATION := merged)	# split or merged
$(eval BINARIZATION_ONLY_HVG := false)		# perform binarization with only highly-variable genes or with all genes
$(eval ZEROES_ARE_ZEROES := true)			# when zero-inflated is inferred for a gene-related distribution; if its counting with respect to a cell is equal to zero, binarize either to zero or nan

## END BINARIZATION ##

## BEGIN BOOLEAN NETWORK INFERENCE ##

# bonesis-inference #

$(eval MINIMIZE_AUTO_LOOPS := true)			# true or false (minimize the number of auto-loops for inferring Boolean networks)

## END BOOLEAN NETWORK INFERENCE ##
