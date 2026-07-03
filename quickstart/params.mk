########################
### Project settings ###
########################

ORGANISM = mouse
CONDITIONS =
PROJECT_DIR = project
OLD_FILES = project/omics/annot/annot.h5ad
JOBS = 16
SEED = 10

##########################
### External resources ###
##########################

GENEINFO_VERSION = bundled
PRIOR_KNOWLEDGE = dorothea
OMNIPATH_VERSION = 2025-08-13
HCOP_VERSION = bundled
DOROTHEA_API = legacy
DOROTHEA_COMPATIBILITY = true
DOROTHEA_LEVELS = A

##############################
### Module-specific inputs ###
##############################

### general ###
REPRESENTATION = X_se

### macrostate ###
MACROSTATE_METHOD = stream
MACROSTATE_SIZE = 25
CLUSTER_NUMBER = 20
ALPHA_EPG = 0.01
MU_EPG = 0.02
LAMBDA_EPG = 0.01
EXTEND_EPG = true
EXTEND_PARAMETER = 0.8
PRUNE_EPG = false

### BN inference ###

BIN_HVG_TOP = 40
MAX_CLAUSE = 8
INFER_LIMIT = 100
