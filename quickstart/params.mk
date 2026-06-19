########################
### Project settings ###
########################

ORGANISM = mouse
CONDITIONS =
PROJECT_DIR = project
RESOURCES_DIR = resources

#####################
### Input sources ###
#####################

COUNT_FILES = data/counts.h5ad
OLD_FILES = project/omics/annot/annot.h5ad

##########################
### External resources ###
##########################

GENEINFO_VERSION = bundled
PRIOR_KNOWLEDGE = collectri
OMNIPATH_VERSION = latest
HCOP_VERSION = bundled

##############################
### Module-specific inputs ###
##############################

### macrostates ###
USE_REP = X_se
MACROSTATE_METHOD = stream
MACROSTATE_SIZE = 25
CLUSTER_NUMBER = 20
ALPHA_EPG = 0.01
MU_EPG = 0.02
LAMBDA_EPG = 0.01
EXTEND_EPG = true
EXTEND_PARAMETER = 0.8
PRUNE_EPG = false

### binarization ###
BIN_HVG_FLAVOR = seurat_v3
BIN_HVG_TOP = 50
ZEROES_ARE_ZEROES = false

### specification ###
SPEC_FILE = spec.yml
SPEC_ONLY_HVG = true

### inference ###
MAX_CLAUSE = 6
TIMEOUT_SOFT = 5m
TIMEOUT_CONSTS = 5m
TIMEOUT_RELAXED = 5m
TIMEOUT_SEED = 10m
TIMEOUT_LOCK = 10m
INFER_LIMIT = 5
