## BEGIN PATHS ##

h5ads_for_conditions = $(foreach condition,$(running_conditions),$($(1)_$(condition)))
default_bin_input_h5ads = $(if $(multi_condition),$(annotation_integrated),$(annotation_$(conditions)))
macrostate_h5ad = $(if $(MACROSTATE_FILES),$(tmpdir)/bin/macrostates.h5ad)
macrostate_h5ads = $(if $(filter 1,$(words $(MACROSTATE_FILES))),\
	$(macrostate_h5ad),\
	$(foreach condition,$(conditions),$(macrostate_h5ad_$(condition))))
bin_input_h5ads = $(if $(MACROSTATE_FILES),$(macrostate_h5ad),$(default_bin_input_h5ads))

clustering_integrated = $(results)/integrated/clust/clust.h5ad
annotation_integrated = $(results)/integrated/annot/annot.h5ad

cc_markers  = $(resources_dir)/cycle/mouse_cycle_markers.rds
signatures  = $(resources_dir)/signatures/geiger.xls \
              $(resources_dir)/signatures/chambers.xls \
              $(resources_dir)/signatures/sig.json
go_basic    = $(resources_dir)/go/go_basic.obo
go_organism = $(resources_dir)/go/goslim_$(ORGANISM).obo
gene2go     = $(resources_dir)/go/gene2go
repeat_msk_table = $(resources_dir)/ref/rmsk.txt.gz
repeat_msk  = $(resources_dir)/ref/repeat_msk.gtf.gz

genome_ref_name = $(if $(strip $(genome_url)),$(notdir $(genome_url)),missing-genome-url)
genome_ref_archive = $(resources_dir)/ref/$(genome_ref_name)
$(eval genome_ref := $(tmpdir)/ref/$(genome_ref_name))
genome_ref := $(genome_ref:.tar.gz=)
star_index = $(genome_ref)/star/Genome

define find_paths_for_conditions

fastq_$(1) =                    $(results)/$(call condition_path,$(1))fastq
geo_dir_$(1) =                  $(results)/$(call condition_path,$(1))count/geo
geo_matrix_$(1) =               $$(geo_dir_$(1))/matrix.mtx.gz
geo_barcodes_$(1) =             $$(geo_dir_$(1))/barcodes.tsv.gz
geo_genes_$(1) =                $$(geo_dir_$(1))/genes.tsv.gz
geo_files_$(1) =                $$(geo_matrix_$(1)) $$(geo_barcodes_$(1)) $$(geo_genes_$(1))
count_file_$(1) =               $(call file_for_condition,$(1),$(COUNT_FILES))
load_matrix_$(1) =              $(results)/$(call condition_path,$(1))count/counts.h5ad
cellranger_$(1) =               $(results)/$(call condition_path,$(1))count/cellranger/$(call condition_name,$(1)).mri.tgz
star_$(1) =                     $(results)/$(call condition_path,$(1))count/star/Aligned.sortedByCoord.out.bam \
                                $(results)/$(call condition_path,$(1))count/star/Solo.out/matrix.mtx \
                                $(results)/$(call condition_path,$(1))count/star/Solo.out/barcodes.tsv
qc_$(1) =                       $(results)/$(call condition_path,$(1))count/star/star.velocyto.bam
velocyto_$(1) =                 $(results)/$(call condition_path,$(1))count/counts.h5ad
filtering_$(1) =                $(results)/$(call condition_path,$(1))prep/filter/counts.h5ad
normalization_$(1) =            $(results)/$(call condition_path,$(1))prep/norm/counts.h5ad
velocity_$(1) =                 $(results)/$(call condition_path,$(1))trajectories/velocity/velocity.h5ad
potency_$(1) =                  $(results)/$(call condition_path,$(1))trajectories/potency/potency.csv
cotan_$(1) =                    $(results)/$(call condition_path,$(1))mstates/cotan/mstates.h5ad \
                                $(results)/$(call condition_path,$(1))mstates/cotan/mstates.csv
cellrank_$(1) =                 $(results)/$(call condition_path,$(1))mstates/cellrank/mstates.h5ad \
                                $(results)/$(call condition_path,$(1))mstates/cellrank/mstates.csv
stream_$(1) =                   $(results)/$(call condition_path,$(1))mstates/stream/mstates.h5ad \
                                $(results)/$(call condition_path,$(1))mstates/stream/mstates.csv
knnsc_$(1) =                    $(results)/$(call condition_path,$(1))mstates/knnsc/mstates.h5ad \
                                $(results)/$(call condition_path,$(1))mstates/knnsc/mstates.csv

ifeq ($(MACROSTATE_METHOD),cotan)
macrostates_$(1) =              $$(cotan_$(1))
else ifeq ($(MACROSTATE_METHOD),cellrank)
macrostates_$(1) =              $$(cellrank_$(1))
else ifeq ($(MACROSTATE_METHOD),stream)
macrostates_$(1) =              $$(stream_$(1))
else ifeq ($(MACROSTATE_METHOD),knnsc)
macrostates_$(1) =              $$(knnsc_$(1))
else
macrostates_$(1) =              $(results)/$(call condition_path,$(1))mstates/invalid-method/.error
endif

ifeq ($(ALIGNMENT_TOOL),cellranger)
alignment_$(1) =                $$(cellranger_$(1))
else ifeq ($(ALIGNMENT_TOOL),star)
alignment_$(1) =                $$(star_$(1))
else
alignment_$(1) =                $(results)/$(call condition_path,$(1))count/invalid-alignment/.error
endif

macrostate_file_$(1) =          $(call file_for_condition,$(1),$(MACROSTATE_FILES))
macrostate_h5ad_$(1) =          $(tmpdir)/$(1)/bin/macrostates.h5ad
count_input_$(1) =              $(if $(filter true,$(count_files_mode)),$$(count_file_$(1)),\
                                $(if $(filter true,$(matrix_mode)),$$(load_matrix_$(1)),$$(velocyto_$(1))))

endef

define find_paths_for_references

clustering_$(1) =               $(results)/$(call condition_path,$(1))clust/clust.h5ad
dea_$(1) =                      $(results)/$(call condition_path,$(1))clust/dea/markers.csv \
                                $(results)/$(call condition_path,$(1))clust/dea/genes.xlsx
scoring_$(1) =                  $(results)/$(call condition_path,$(1))clust/sig.csv
goea_basic_$(1) =               $(results)/$(call condition_path,$(1))clust/goea/basic.xlsx
goea_organism_$(1) =            $(results)/$(call condition_path,$(1))clust/goea/$(ORGANISM).xlsx
annotation_$(1) =               $(results)/$(call condition_path,$(1))annot/annot.h5ad

endef

bin_cells =                     $(results)/bin/scboolseq/cell/cells_bin.h5ad \
                                $(results)/bin/scboolseq/cell/cells_stats.csv
bin_hvg =                       $(tmpdir)/bin/top_genes.txt
bin_mstates =               $(results)/bin/scboolseq/macro/$(MACROSTATE_METHOD)/mstates_bin.csv
bin_dea =                       $(results)/bin/dea/$(MACROSTATE_METHOD)/mstates_bin.csv
bin_consensus =                 $(results)/bin/consensus/$(MACROSTATE_METHOD)/mstates_bin.csv

bonesis_model =                 $(results)/infer/spec/model.bo \
                                $(results)/infer/spec/mstates.csv \
                                $(results)/infer/spec/important.txt \
                                $(results)/infer/spec/mandatory.txt
max_nodes_soft =                $(results)/infer/genes/soft/comps.txt
max_consts_soft =               $(results)/infer/genes/consts/comps.txt
max_nodes_relaxed =             $(results)/infer/genes/relaxed/comps.txt
max_nodes_seed =                $(results)/infer/genes/seed/comps.txt
max_nodes_lock =                $(results)/infer/genes/lock/comps.txt
bn_min =                        $(results)/infer/bn/min/model.bnet

bn_submin_dir = $(results)/infer/bn/submin
bn_files = $(foreach i,$(1),$(2)/$(i)/model.bnet $(2)/$(i)/state.cfg)
ifneq ($(filter-out 0,$(strip $(INFER_LIMIT))),)
bn_submin_indices := $(shell seq 0 $$(($(INFER_LIMIT)-1)))
bn_submin = $(call bn_files,$(bn_submin_indices),$(bn_submin_dir))
else
bn_submin = $(bn_submin_dir)/ensemble.pdf
endif

bn_diverse_dir = $(results)/infer/bn/diverse
ifneq ($(filter-out 0,$(strip $(INFER_LIMIT))),)
bn_diverse_indices := $(shell seq 0 $$(($(INFER_LIMIT)-1)))
bn_diverse = $(call bn_files,$(bn_diverse_indices),$(bn_diverse_dir))
else
bn_diverse = $(bn_diverse_dir)/ensemble.pdf
endif

$(foreach condition,$(conditions),$(eval $(call find_paths_for_conditions,$(condition))))
$(foreach reference,$(references_default),$(eval $(call find_paths_for_references,$(reference))))

## END PATHS ##

## BEGIN TARGETS ##

fastq_target :=
load_matrix_target :=
alignment_target :=
cellranger_target :=
star_target :=
qc_target :=
velocyto_target :=
filtering_target :=
normalization_target :=
clustering_target :=
dea_target :=
scoring_target :=
goea_target :=
annotation_target :=
velocity_target :=
potency_target :=
macrostates_target :=
stream_target :=
cellrank_target :=
knnsc_target :=
cotan_target :=

define find_targets_for_conditions

$(eval fastq_target := $(fastq_target) $(if $(filter true,$(matrix_mode)),,$(fastq_$(1))))
$(eval load_matrix_target := $(load_matrix_target) $(if $(filter true,$(matrix_mode)),$(load_matrix_$(1)) $(geo_files_$(1))))
$(eval alignment_target := $(alignment_target) $(alignment_$(1)))
$(eval cellranger_target := $(cellranger_target) $(cellranger_$(1)))
$(eval star_target := $(star_target) $(star_$(1)))
$(eval qc_target := $(qc_target) $(qc_$(1)))
$(eval velocyto_target := $(velocyto_target) $(if $(filter true,$(count_files_mode) $(matrix_mode)),,$(velocyto_$(1))))
$(eval filtering_target := $(filtering_target) $(filtering_$(1)))
$(eval normalization_target := $(normalization_target) $(normalization_$(1)))
$(eval velocity_target := $(velocity_target) $(velocity_$(1)))
$(eval potency_target := $(potency_target) $(potency_$(1)))
$(eval cotan_target := $(cotan_target) $(cotan_$(1)))
$(eval cellrank_target := $(cellrank_target) $(cellrank_$(1)))
$(eval stream_target := $(stream_target) $(stream_$(1)))
$(eval knnsc_target := $(knnsc_target) $(knnsc_$(1)))
$(eval macrostates_target := $(macrostates_target) $(macrostates_$(1)))

endef

define find_targets_for_references

$(eval clustering_target := $(clustering_target) $(clustering_$(1)))
$(eval dea_target := $(dea_target) $(dea_$(1)))
$(eval scoring_target := $(scoring_target) $(scoring_$(1)))
$(eval goea_target := $(goea_target) $(goea_basic_$(1)) $(goea_organism_$(1)))
$(eval annotation_target := $(annotation_target) $(annotation_$(1)))

endef

$(foreach condition,$(target_conditions),$(eval $(call find_targets_for_conditions,$(condition))))
$(foreach reference,$(running_references),$(eval $(call find_targets_for_references,$(reference))))

ifneq ($(strip $(MACROSTATE_FILES)),)
macrostates_target := $(macrostate_h5ad)
endif

## END TARGETS ##

ifeq ($(words $(conditions)),1)
batch =
else
batch = --batch condition
endif

## BEGIN PARAMETERS ##

ifeq ($(diagnostic_mode),)
ifneq ($(call is_positive_integer,$(MEMORY)),true)
$(error parameter MEMORY must be a positive integer (current: $(MEMORY)))
endif
ifneq ($(call is_positive_integer,$(JOBS)),true)
$(error parameter JOBS must be a positive integer (current: $(JOBS)))
endif
ifneq ($(call is_positive_integer,$(SEED)),true)
$(error parameter SEED must be a positive integer (current: $(SEED)))
endif
ifneq ($(filter $(LOGGING),true false),$(LOGGING))
$(error unsupported value for parameter LOGGING (supported values: true, false))
endif
ifneq ($(call is_creatable_path,$(PROJECT_DIR)),true)
$(error parameter PROJECT_DIR must be a valid output path (current: $(PROJECT_DIR)))
endif
ifneq ($(call is_creatable_path,$(RESOURCES_DIR)),true)
$(error parameter RESOURCES_DIR must be a valid output path (current: $(RESOURCES_DIR)))
endif
ifeq ($(strip $(REFERENCES)),)
$(error parameter REFERENCES not defined)
endif
ifneq ($(invalid_references),)
$(error unsupported value for parameter REFERENCES: $(invalid_references) \
	(supported values: $(subst $(space),$(comma) ,$(display_supported_references_label))))
endif
ifeq ($(words $(conditions)),1)
ifneq ($(filter integrated,$(running_references)),)
$(error unsupported value for parameter REFERENCES: integrated is not supported \
	for mono-condition projects)
endif
endif
endif

$(if $(filter true,$(call is_creatable_path,$(PROJECT_DIR))),$(shell mkdir -p "$(results)"))
$(if $(filter true,$(call is_creatable_path,$(RESOURCES_DIR))),$(shell mkdir -p "$(resources_dir)"))

check_mode := $(filter check,$(MAKECMDGOALS))$(__check_mode)

ifneq ($(check_mode),)
$(if $(strip $(JOBS)),,$(eval override JOBS := 1))
endif

ifndef JOBS
open_allocated_cpu := 1
else ifneq ($(call is_positive_integer,$(JOBS)),true)
open_allocated_cpu := 1
else
try_open_allocated_cpu := $(shell echo $$(($(JOBS) / 2)))
open_allocated_cpu := $(if $(findstring $(try_open_allocated_cpu),0),1,$(try_open_allocated_cpu))
endif

norm_mad = $(if $(filter true,$(NORM_MAD)),--consistent-mad)
cc_scores = $(if $(filter true,$(CC_CORRECTION)),--correction G2M_score S_score G1_score)
pca_only_hvg = $(if $(filter true,$(PCA_ONLY_HVG)),--only-hvg)
embedding_method_X_umap = umap
embedding_method_X_tsne = tsne
embedding_method = $(embedding_method_$(1))
embedding = $(call embedding_method,$(USE_REP))

label_ids = $(if $(LABEL),$(shell seq 0 1 $$(($(words $(LABEL))-1))))
label_map = $(join $(label_ids),$(addprefix :,$(LABEL)))

velocity_only_hvg = $(if $(filter true,$(VELOCITY_ONLY_HVG)),--only-hvg)
cotan_only_hvg = $(if $(filter true,$(COTAN_ONLY_HVG)),--only-hvg)
extend_epg = $(if $(filter true,$(EXTEND_EPG)),--extend-epg)
prune_epg = $(if $(filter true,$(PRUNE_EPG)),--prune-epg)

ifeq ($(KNNSC_DIMENSION),)
knnsc_dimension=
else
knnsc_dimension=--dimension $(KNNSC_DIMENSION)
endif

hvg_layer_name = $(if $(filter seurat_v3,$(1)),counts,log-norm)
hvg_layer = --layer $(call hvg_layer_name,$(1))
bin_hvg_layer = $(if $(filter seurat seurat_v3 cell_ranger,$(BIN_HVG_FLAVOR)),\
	$(call hvg_layer,$(BIN_HVG_FLAVOR)))
bin_scboolseq_hvg = $(if $(filter true,$(BIN_SCBOOLSEQ_ONLY_HVG)),--filter-genes $(bin_hvg))
bin_dea_hvg = $(if $(filter true,$(BIN_DEA_ONLY_HVG)),--filter-genes $(bin_hvg))
zeroes_are_zeroes = $(if $(filter true,$(ZEROES_ARE_ZEROES)),--zeroes-are-zeroes)
bin_method_error = $(results)/bin/invalid-method/.error
default_bin = $(if $(filter scboolseq,$(BIN_METHOD)),$(bin_mstates),\
	$(if $(filter dea,$(BIN_METHOD)),$(bin_dea),\
	$(if $(filter consensus,$(BIN_METHOD)),$(bin_consensus),$(bin_method_error))))
bin = $(if $(BINARIZATION_FILE),$(BINARIZATION_FILE),$(default_bin))

known_prior_knowledge = collectri dorothea
dorothea_apis = current legacy
dorothea_levels = A B C D

# Resolve the user-facing prior knowledge parameter to the actual domain passed
# to BoNesis scripts.
ifeq ($(PRIOR_KNOWLEDGE),collectri)
prior_knowledge = collectri
else ifeq ($(PRIOR_KNOWLEDGE),dorothea)
ifneq ($(filter $(strip $(DOROTHEA_API)),$(dorothea_apis)),)
prior_knowledge = dorothea
else
prior_knowledge =
endif
else ifneq ($(wildcard $(PRIOR_KNOWLEDGE)),)
prior_knowledge = $(PRIOR_KNOWLEDGE)
endif
dorothea_levels_arg = $(if $(filter dorothea,$(prior_knowledge)),\
	$(if $(strip $(DOROTHEA_LEVELS)),--dorothea-levels $(DOROTHEA_LEVELS)))
dorothea_api_arg = $(if $(filter dorothea,$(prior_knowledge)),\
	--dorothea-api $(DOROTHEA_API))
dorothea_compatibility_arg = $(if $(filter dorothea,$(prior_knowledge)),\
	--dorothea-compatibility $(DOROTHEA_COMPATIBILITY))
geneinfo_version_arg = --geneinfo-version $(GENEINFO_VERSION)
omnipath_version_arg = $(if $(filter collectri dorothea,$(prior_knowledge)),\
	--omnipath-version $(OMNIPATH_VERSION))
hcop_version_arg = $(if $(filter collectri dorothea,$(prior_knowledge)),\
	--hcop-version $(HCOP_VERSION))
prior_knowledge_args = \
	$(geneinfo_version_arg) \
	$(omnipath_version_arg) \
	$(hcop_version_arg) \
	$(dorothea_api_arg) \
	$(dorothea_compatibility_arg) \
	$(dorothea_levels_arg)
prior_knowledge_params = PRIOR_KNOWLEDGE \
	GENEINFO_VERSION \
	$(if $(filter collectri dorothea,$(PRIOR_KNOWLEDGE)),OMNIPATH_VERSION HCOP_VERSION) \
	$(if $(filter dorothea,$(PRIOR_KNOWLEDGE)),\
	DOROTHEA_API DOROTHEA_COMPATIBILITY DOROTHEA_LEVELS)

min_self_loop_consts = $(if $(filter true,$(MIN_SELF_LOOP_CONSTS)),--minimize-self-loops)
min_self_loop_infer = $(if $(filter true,$(MIN_SELF_LOOP_INFER)),--minimize-self-loops)

reset_stages = \
	load-fastq load-matrix alignment cellranger star qc velocyto \
	filtering normalization clustering dea scoring goea annotation \
	velocity potency cotan cellrank stream knnsc macrostates \
	bin-cells bin-macrostates bin-dea bin-consensus binarization \
	spec max-nodes-soft max-consts-soft max-nodes-relaxed \
	max-nodes-seed max-nodes-lock bn-min bn-submin bn-diverse
RESET_TARGET_load-fastq = $(fastq_target)
RESET_TARGET_load-matrix = $(load_matrix_target)
RESET_TARGET_alignment = $(alignment_target)
RESET_TARGET_cellranger = $(cellranger_target)
RESET_TARGET_star = $(star_target)
RESET_TARGET_qc = $(qc_target)
RESET_TARGET_velocyto = $(velocyto_target)
RESET_TARGET_filtering = $(filtering_target)
RESET_TARGET_normalization = $(normalization_target)
RESET_TARGET_clustering = $(clustering_target)
RESET_TARGET_dea = $(dea_target)
RESET_TARGET_scoring = $(scoring_target)
RESET_TARGET_goea = $(goea_target)
RESET_TARGET_annotation = $(annotation_target)
RESET_TARGET_velocity = $(velocity_target)
RESET_TARGET_potency = $(potency_target)
RESET_TARGET_cotan = $(cotan_target)
RESET_TARGET_cellrank = $(cellrank_target)
RESET_TARGET_stream = $(stream_target)
RESET_TARGET_knnsc = $(knnsc_target)
RESET_TARGET_macrostates = $(macrostates_target)
RESET_TARGET_bin-cells = $(bin_cells)
RESET_TARGET_bin-macrostates = $(bin_mstates)
RESET_TARGET_bin-dea = $(bin_dea)
RESET_TARGET_bin-consensus = $(bin_consensus)
RESET_TARGET_binarization = $(bin)
RESET_TARGET_spec = $(bonesis_model)
RESET_TARGET_max-nodes-soft = $(max_nodes_soft)
RESET_TARGET_max-consts-soft = $(max_consts_soft)
RESET_TARGET_max-nodes-relaxed = $(max_nodes_relaxed)
RESET_TARGET_max-nodes-seed = $(max_nodes_seed)
RESET_TARGET_max-nodes-lock = $(max_nodes_lock)
RESET_TARGET_bn-min = $(bn_min)
RESET_TARGET_bn-submin = $(bn_submin)
RESET_TARGET_bn-diverse = $(bn_diverse)

reset_modules := $(strip $(RESET_TARGET) $(CLI_RESET_TARGETS) $(RESET_FROM))
trust_modules := $(strip $(TRUST_TARGET) $(CLI_TRUST_TARGETS))
raw_clean_modules := $(strip $(CLEAN_TARGET))
clean_all := $(filter all,$(raw_clean_modules))
clean_modules := $(if $(filter all,$(raw_clean_modules)),$(reset_stages),$(raw_clean_modules))
reset_disabled_goals := help
reset_disabled := $(strip \
	$(filter $(reset_disabled_goals),$(MAKECMDGOALS)) \
	$(__reset_disabled) \
	$(if $(filter true,$(HELP)),help))
ifeq ($(reset_disabled),)
unknown_reset_targets := $(filter-out $(reset_stages),$(reset_modules))
unknown_trust_targets := $(filter-out $(reset_stages),$(trust_modules))
unknown_clean_targets := $(filter-out $(reset_stages) all,$(raw_clean_modules))
ifneq ($(clean_all),)
ifneq ($(filter-out all,$(raw_clean_modules)),)
$(error CLEAN_TARGET=all cannot be combined with modules: $(filter-out all,$(raw_clean_modules)))
endif
endif
ifneq ($(unknown_reset_targets),)
$(error unknown RESET_TARGET/RESET_FROM module: $(unknown_reset_targets) \
	(supported values: $(subst $(space),$(comma) ,$(reset_stages))))
endif
ifneq ($(unknown_trust_targets),)
$(error unknown TRUST_TARGET module: $(unknown_trust_targets) \
	(supported values: $(subst $(space),$(comma) ,$(reset_stages))))
endif
ifneq ($(unknown_clean_targets),)
$(error unknown CLEAN_TARGET module: $(unknown_clean_targets) \
	(supported values: $(subst $(space),$(comma) ,$(reset_stages))))
endif
reset_targets := $(strip $(foreach module,$(reset_modules),$(RESET_TARGET_$(module))))
trust_targets := $(strip $(foreach module,$(trust_modules),$(RESET_TARGET_$(module))))
known_scbolt_targets := $(call uniq,$(foreach module,$(reset_stages),$(RESET_TARGET_$(module))))
unknown_old_files := $(filter-out $(known_scbolt_targets),$(OLD_FILES))
missing_old_files := $(strip $(foreach path,$(OLD_FILES),$(if $(wildcard $(path)),,$(path))))
ifneq ($(reset_targets),)
.PHONY: $(reset_targets)
endif
trust_make_options := \
	$(foreach target,$(trust_targets),--old-file="$(target)") \
	$(foreach target,$(OLD_FILES),--old-file="$(target)")
ifeq ($(diagnostic_mode),)
ifneq ($(missing_old_files),)
$(error old file not found: $(missing_old_files))
endif
endif
endif

target_params_load-matrix = $(foreach condition,$(conditions),$(call gsm_var,$(condition)))
target_params_alignment = ALIGNMENT_TOOL MEMORY STAR_CB_LEN STAR_UMI_LEN STAR_WHITELIST
target_params_cellranger = MEMORY
target_params_star = MEMORY STAR_CB_LEN STAR_UMI_LEN STAR_WHITELIST
target_params_qc = STAR_BARCODE_FILTER STAR_MIN_UMI STAR_TOP_BARCODES
target_params_velocyto = ALIGNMENT_TOOL MEMORY STAR_BARCODE_FILTER STAR_MIN_UMI STAR_TOP_BARCODES
target_params_filtering = \
	COUNT_FILES \
	GENEINFO_VERSION \
	GENE_DROPOUT GENE_EXPRESSION GENE_COUNTS \
	CELL_DROPOUT CELL_EXPRESSION CELL_READS \
	MAD_DEVIATION NORM_MAD MT
target_params_normalization = CC_CORRECTION
target_params_clustering = \
	INTEGRATION ANALYSIS_HVG_FLAVOR ANALYSIS_HVG_TOP ANALYSIS_HVG_SPAN \
	ANALYSIS_HVG_BINS DIM_PCA DIM_CLUSTERING DIM_EMBEDDING PCA_ONLY_HVG \
	NEIGHBORS METRIC RESOLUTION MIN_DIST SPREAD
target_params_dea = LOGFC CORRECTION ALPHA
target_params_goea = GENEINFO_VERSION
target_params_annotation = LABEL
target_params_velocity = DIM_MOMENT VELOCITY_ONLY_HVG SMM_MODE
target_params_potency = BATCH_SIZE SMOOTH_BATCH_SIZE
target_params_cotan = MACROSTATE_SIZE COTAN_METHOD COTAN_ONLY_HVG MAX_ITER
target_params_cellrank = \
	MACROSTATE_SIZE CELLRANK_METHOD STATES INITIAL_STATES TERMINAL_STATES \
	CELLRANK_STABILITY CELLRANK_ALPHA
target_params_stream = \
	MACROSTATE_SIZE CLUSTERING_METHOD CLUSTER_NUMBER \
	ALPHA_EPG MU_EPG LAMBDA_EPG EXTEND_EPG EXTEND_MODE \
	EXTEND_PARAMETER PRUNE_EPG COLLAPSE_PARAMETER
target_params_knnsc = \
	MACROSTATE_SIZE KNNSC_EMBEDDING KNNSC_DIMENSION KNNSC_NEIGHBORS \
	KNNSC_MIN_CLUSTER_SIZE
target_params_macrostates = MACROSTATE_METHOD MACROSTATE_SIZE MACROSTATE_FILES
target_params_bin-cells = \
	MACROSTATE_FILES \
	BIN_SCBOOLSEQ_ONLY_HVG BIN_HVG_FLAVOR BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	UNIMODAL_QUANTILE ZEROES_ARE_ZEROES
target_params_bin-macrostates = \
	MACROSTATE_FILES NANS_THRESHOLD BIMODAL_THRESHOLD ZEROINF_THRESHOLD UNIMODAL_THRESHOLD
target_params_bin-dea = \
	MACROSTATE_FILES \
	BIN_DEA_ONLY_HVG BIN_HVG_FLAVOR BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	BIN_LOGFC BIN_CORRECTION BIN_ALPHA
target_params_bin-consensus = \
	MACROSTATE_FILES \
	NANS_THRESHOLD BIMODAL_THRESHOLD ZEROINF_THRESHOLD UNIMODAL_THRESHOLD \
	BIN_DEA_ONLY_HVG BIN_HVG_FLAVOR BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	BIN_LOGFC BIN_CORRECTION BIN_ALPHA
target_params_binarization = \
	BIN_METHOD BINARIZATION_FILE MACROSTATE_FILES \
	BIN_HVG_FLAVOR BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS
target_params_spec = \
	SPEC_FILE SPEC_ONLY_HVG \
	BIN_HVG_FLAVOR BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	$(prior_knowledge_params)
target_params_max-nodes-soft = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER \
	CLINGO_CONFIG_SOFT CLINGO_OPT_MODE_SOFT CLINGO_OPT_STRATEGY_SOFT \
	JOBS_SOFT TIMEOUT_SOFT
target_params_max-consts-soft = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER MIN_SELF_LOOP_CONSTS \
	CLINGO_CONFIG_CONSTS CLINGO_OPT_MODE_CONSTS CLINGO_OPT_STRATEGY_CONSTS \
	JOBS_CONSTS TIMEOUT_CONSTS
target_params_max-nodes-relaxed = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER \
	CLINGO_CONFIG_RELAXED CLINGO_OPT_MODE_RELAXED CLINGO_OPT_STRATEGY_RELAXED \
	JOBS_RELAXED TIMEOUT_RELAXED
target_params_max-nodes-seed = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER \
	CLINGO_CONFIG_SEED CLINGO_OPT_MODE_SEED CLINGO_OPT_STRATEGY_SEED \
	JOBS_SEED TIMEOUT_SEED
target_params_max-nodes-lock = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER \
	CLINGO_CONFIG_LOCK CLINGO_OPT_MODE_LOCK CLINGO_OPT_STRATEGY_LOCK \
	JOBS_LOCK TIMEOUT_LOCK
target_params_bn-min = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_INFER MIN_SELF_LOOP_INFER \
	CLINGO_OPT_MODE_MIN GRAPH_FORMATS
target_params_bn-submin = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_INFER \
	INFER_LIMIT CONFIG_FORMATS GRAPH_FORMATS
target_params_bn-diverse = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_INFER \
	INFER_LIMIT CONFIG_FORMATS GRAPH_FORMATS

sensitive_params_alignment =
sensitive_params_load-matrix = $(foreach condition,$(conditions),$(call gsm_var,$(condition)))
sensitive_params_cellranger = genome_url
sensitive_params_star = genome_url STAR_CB_LEN STAR_UMI_LEN STAR_WHITELIST
sensitive_params_qc = STAR_BARCODE_FILTER STAR_MIN_UMI STAR_TOP_BARCODES
sensitive_params_velocyto = ALIGNMENT_TOOL genome_url repeat_msk_url STAR_BARCODE_FILTER STAR_MIN_UMI STAR_TOP_BARCODES
sensitive_params_filtering = \
	COUNT_FILES ORGANISM GENEINFO_VERSION \
	GENE_DROPOUT GENE_EXPRESSION GENE_COUNTS \
	CELL_DROPOUT CELL_EXPRESSION CELL_READS \
	MAD_DEVIATION NORM_MAD MT
sensitive_params_normalization = ORGANISM CC_CORRECTION
sensitive_params_clustering = \
	INTEGRATION ANALYSIS_HVG_FLAVOR ANALYSIS_HVG_TOP ANALYSIS_HVG_SPAN \
	ANALYSIS_HVG_BINS DIM_PCA DIM_CLUSTERING DIM_EMBEDDING PCA_ONLY_HVG \
	NEIGHBORS METRIC RESOLUTION MIN_DIST SPREAD SEED USE_REP
sensitive_params_dea = LOGFC CORRECTION ALPHA
sensitive_params_scoring = LABEL_COL
sensitive_params_goea = ORGANISM GENEINFO_VERSION
sensitive_params_annotation = LABEL LABEL_COL USE_REP
sensitive_params_velocity = DIM_MOMENT VELOCITY_ONLY_HVG SMM_MODE USE_REP LABEL_COL
sensitive_params_potency = BATCH_SIZE SMOOTH_BATCH_SIZE ORGANISM USE_REP LABEL_COL SEED
sensitive_params_cotan = MACROSTATE_SIZE COTAN_METHOD COTAN_ONLY_HVG MAX_ITER USE_REP LABEL_COL
sensitive_params_cellrank = \
	MACROSTATE_SIZE CELLRANK_METHOD STATES INITIAL_STATES TERMINAL_STATES \
	CELLRANK_STABILITY CELLRANK_ALPHA SEED LABEL_COL
sensitive_params_stream = \
	MACROSTATE_SIZE CLUSTERING_METHOD CLUSTER_NUMBER \
	ALPHA_EPG MU_EPG LAMBDA_EPG EXTEND_EPG EXTEND_MODE \
	EXTEND_PARAMETER PRUNE_EPG COLLAPSE_PARAMETER USE_REP LABEL_COL
sensitive_params_knnsc = \
	MACROSTATE_SIZE KNNSC_EMBEDDING KNNSC_DIMENSION KNNSC_NEIGHBORS \
	KNNSC_MIN_CLUSTER_SIZE METRIC LABEL_COL USE_REP
sensitive_params_macrostates =
sensitive_params_bin-cells = \
	MACROSTATE_FILES USE_REP \
	BIN_SCBOOLSEQ_ONLY_HVG BIN_HVG_FLAVOR BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	UNIMODAL_QUANTILE ZEROES_ARE_ZEROES
sensitive_params_bin-macrostates = \
	MACROSTATE_FILES USE_REP \
	NANS_THRESHOLD BIMODAL_THRESHOLD ZEROINF_THRESHOLD UNIMODAL_THRESHOLD
sensitive_params_bin-dea = \
	MACROSTATE_FILES USE_REP \
	BIN_DEA_ONLY_HVG BIN_HVG_FLAVOR BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	BIN_LOGFC BIN_CORRECTION BIN_ALPHA
sensitive_params_bin-consensus = \
	MACROSTATE_FILES USE_REP \
	NANS_THRESHOLD BIMODAL_THRESHOLD ZEROINF_THRESHOLD UNIMODAL_THRESHOLD \
	BIN_DEA_ONLY_HVG BIN_HVG_FLAVOR BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	BIN_LOGFC BIN_CORRECTION BIN_ALPHA
sensitive_params_binarization =
sensitive_params_spec = \
	SPEC_FILE SPEC_ONLY_HVG \
	BIN_HVG_FLAVOR BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	$(prior_knowledge_params)
sensitive_params_max-nodes-soft = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER \
	CLINGO_CONFIG_SOFT CLINGO_OPT_MODE_SOFT CLINGO_OPT_STRATEGY_SOFT \
	JOBS_SOFT TIMEOUT_SOFT SEED
sensitive_params_max-consts-soft = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER MIN_SELF_LOOP_CONSTS \
	CLINGO_CONFIG_CONSTS CLINGO_OPT_MODE_CONSTS CLINGO_OPT_STRATEGY_CONSTS \
	JOBS_CONSTS TIMEOUT_CONSTS SEED
sensitive_params_max-nodes-relaxed = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER \
	CLINGO_CONFIG_RELAXED CLINGO_OPT_MODE_RELAXED CLINGO_OPT_STRATEGY_RELAXED \
	JOBS_RELAXED TIMEOUT_RELAXED SEED
sensitive_params_max-nodes-seed = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER \
	CLINGO_CONFIG_SEED CLINGO_OPT_MODE_SEED CLINGO_OPT_STRATEGY_SEED \
	JOBS_SEED TIMEOUT_SEED SEED
sensitive_params_max-nodes-lock = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER \
	CLINGO_CONFIG_LOCK CLINGO_OPT_MODE_LOCK CLINGO_OPT_STRATEGY_LOCK \
	JOBS_LOCK TIMEOUT_LOCK SEED
sensitive_params_bn-min = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_INFER MIN_SELF_LOOP_INFER \
	CLINGO_OPT_MODE_MIN GRAPH_FORMATS SEED
sensitive_params_bn-submin = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_INFER \
	INFER_LIMIT CONFIG_FORMATS GRAPH_FORMATS SEED
sensitive_params_bn-diverse = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_INFER \
	INFER_LIMIT CONFIG_FORMATS GRAPH_FORMATS SEED

use_rep_check_pattern = $(use_rep_check_pattern_1)$(use_rep_check_pattern_2)$(use_rep_check_pattern_3)
use_rep_check_pattern_1 = scripts/(clust/annotation|utils/pipe_its|traj/potency
use_rep_check_pattern_2 = |mstates/stream_mstates|bin/(bin_cells_scboolseq
use_rep_check_pattern_3 = |bin_clust_scboolseq|bin_dea)).py

label_col_check_pattern = $(label_col_check_pattern_1)$(label_col_check_pattern_2)
label_col_check_pattern_1 = scripts/(clust/annotation|utils/pipe_its|traj/velocity
label_col_check_pattern_2 = |traj/potency|mstates/(stream|knnsc)_mstates).py

project_config_param_set = \
	ORGANISM CONDITIONS \
	$(foreach condition,$(conditions),$(call sra_var,$(condition))) \
	$(foreach condition,$(conditions),$(call gsm_var,$(condition))) \
	LABEL SPEC_FILE
core_config_param_set = \
	PARAMS REFERENCES PROJECT_DIR RESOURCES_DIR MEMORY JOBS SEED LOGGING USE_REP LABEL_COL OLD_FILES
method_config_param_set = \
	ALIGNMENT_TOOL STAR_CB_LEN STAR_UMI_LEN \
	STAR_BARCODE_FILTER STAR_MIN_UMI STAR_TOP_BARCODES \
	GENE_DROPOUT GENE_EXPRESSION GENE_COUNTS \
	CELL_DROPOUT CELL_EXPRESSION CELL_READS \
	MAD_DEVIATION NORM_MAD MT \
	CC_CORRECTION \
	INTEGRATION ANALYSIS_HVG_FLAVOR ANALYSIS_HVG_TOP ANALYSIS_HVG_SPAN \
	ANALYSIS_HVG_BINS DIM_PCA DIM_CLUSTERING DIM_EMBEDDING PCA_ONLY_HVG \
	NEIGHBORS METRIC RESOLUTION MIN_DIST SPREAD \
	LOGFC CORRECTION ALPHA \
	DIM_MOMENT VELOCITY_ONLY_HVG SMM_MODE \
	BATCH_SIZE SMOOTH_BATCH_SIZE \
	MACROSTATE_SIZE MACROSTATE_METHOD \
	COTAN_METHOD COTAN_ONLY_HVG MAX_ITER \
	CELLRANK_METHOD STATES INITIAL_STATES TERMINAL_STATES \
	CELLRANK_STABILITY CELLRANK_ALPHA \
	CLUSTERING_METHOD CLUSTER_NUMBER ALPHA_EPG MU_EPG LAMBDA_EPG \
	EXTEND_EPG EXTEND_MODE EXTEND_PARAMETER PRUNE_EPG COLLAPSE_PARAMETER \
	KNNSC_EMBEDDING KNNSC_DIMENSION KNNSC_NEIGHBORS KNNSC_MIN_CLUSTER_SIZE \
	BIN_SCBOOLSEQ_ONLY_HVG BIN_HVG_FLAVOR BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	UNIMODAL_QUANTILE ZEROES_ARE_ZEROES \
	NANS_THRESHOLD BIMODAL_THRESHOLD ZEROINF_THRESHOLD UNIMODAL_THRESHOLD \
	BIN_DEA_ONLY_HVG BIN_HVG_FLAVOR BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	BIN_LOGFC BIN_CORRECTION BIN_ALPHA \
	BIN_METHOD \
	SPEC_ONLY_HVG \
	MAX_CLAUSE DOROTHEA_API DOROTHEA_COMPATIBILITY DOROTHEA_LEVELS \
	CANONIC_FILTER CANONIC_INFER \
	CLINGO_OPT_MODE_SOFT CLINGO_OPT_STRATEGY_SOFT JOBS_SOFT TIMEOUT_SOFT \
	CLINGO_OPT_MODE_CONSTS CLINGO_OPT_STRATEGY_CONSTS JOBS_CONSTS TIMEOUT_CONSTS \
	CLINGO_OPT_MODE_RELAXED CLINGO_OPT_STRATEGY_RELAXED JOBS_RELAXED TIMEOUT_RELAXED \
	CLINGO_OPT_MODE_SEED CLINGO_OPT_STRATEGY_SEED JOBS_SEED TIMEOUT_SEED \
	CLINGO_OPT_MODE_LOCK CLINGO_OPT_STRATEGY_LOCK JOBS_LOCK TIMEOUT_LOCK \
	CLINGO_OPT_MODE_MIN CONFIG_FORMATS GRAPH_FORMATS MIN_SELF_LOOP_CONSTS \
	MIN_SELF_LOOP_INFER INFER_LIMIT
external_resource_config_param_set = \
	STAR_WHITELIST COUNT_FILES BINARIZATION_FILE MACROSTATE_FILES PRIOR_KNOWLEDGE \
	GENEINFO_VERSION OMNIPATH_VERSION HCOP_VERSION \
	CLINGO_CONFIG_SOFT CLINGO_CONFIG_CONSTS CLINGO_CONFIG_RELAXED \
	CLINGO_CONFIG_SEED CLINGO_CONFIG_LOCK
config_all_modules = \
	load-genome load-fastq load-matrix load-signatures load-cc load-go \
	alignment cellranger star qc velocyto \
	filtering normalization clustering dea scoring goea annotation \
	velocity potency cotan cellrank stream knnsc macrostates \
	bin-cells bin-macrostates bin-dea bin-consensus binarization \
	spec max-nodes-soft max-consts-soft max-nodes-relaxed \
	max-nodes-seed max-nodes-lock bn-min bn-submin bn-diverse
config_workflow_modules = \
	load-fastq load-matrix alignment cellranger star qc velocyto \
	filtering normalization clustering dea annotation velocity potency \
	macrostates cotan cellrank stream knnsc bin-cells bin-macrostates \
	bin-dea bin-consensus binarization spec max-nodes-soft max-consts-soft \
	max-nodes-relaxed max-nodes-seed max-nodes-lock bn-min bn-submin bn-diverse
config_default_modules = $(if $(strip $(input_routes)),$(config_workflow_modules),$(config_all_modules))
config_base_params = \
	ORGANISM CONDITIONS \
	$(foreach condition,$(conditions),$(call sra_var,$(condition))) \
	$(foreach condition,$(conditions),$(call gsm_var,$(condition))) \
	PARAMS REFERENCES PROJECT_DIR RESOURCES_DIR MEMORY JOBS SEED LOGGING USE_REP LABEL_COL OLD_FILES
config_params_from_modules = $(strip $(foreach module,$(1),$(target_params_$(module))))
config_project_params = $(call uniq,$(filter $(project_config_param_set),$(1)))
config_core_params = $(call uniq,$(filter $(core_config_param_set),$(1)))
config_method_params = $(call uniq,$(filter $(method_config_param_set),$(1)))
config_external_resource_params = $(call uniq,$(filter $(external_resource_config_param_set),$(1)))
target_dry_run_modules = $(shell $(nested_make) --always-make --dry-run LOGGING=false \
	__check_mode=true __$(1) PARAMS="$(PARAMS)" LOGFILE="$(LOGFILE)" 2>/dev/null \
	| sed -n '/"RULE"/{s/.*"RULE" "//;s/ .*//;s/"//g;p;}' \
	| awk '$$0 != "bin-hvg" && !seen[$$0]++')
target_run_modules = $(shell $(nested_make) --dry-run LOGGING=false \
	__check_mode=true __$(1) PARAMS="$(PARAMS)" LOGFILE="$(LOGFILE)" 2>/dev/null \
	| sed -n '/"RULE"/{s/.*"RULE" "//;s/ .*//;s/"//g;p;}' \
	| awk '$$0 != "bin-hvg" && !seen[$$0]++')

## END PARAMETERS ##
