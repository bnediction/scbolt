## Test fixture parameters.
## This file is intentionally self-contained and must not depend on case studies.

ORGANISM = mouse
CONDITIONS = ctrl treated
RESULTS_DIR = ../../project

SRA_CTRL = SRR000001 SRR000002
SRA_TREATED = SRR000003 SRR000004
LABEL = Prom Rep
SPEC_FILE = spec.yml

PRIOR_KNOWLEDGE = dorothea
DOROTHEA_API = legacy
DOROTHEA_LEVELS = A

MACROSTATE_METHOD = knnsc
BIN_METHOD = consensus

KNNSC_CENTRALITY_CTRL = Prom
KNNSC_PERIPHERY_CTRL = Rep
KNNSC_CENTRALITY_TREATED = Prom
KNNSC_PERIPHERY_TREATED = Rep

TIMEOUT_SEED = 0
